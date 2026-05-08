#!/usr/bin/env python3
"""Safe maintenance cleaner for WorkflowProgram OpenCode projects."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


RUNTIME_DIR = Path(__file__).resolve().parent
if str(RUNTIME_DIR) not in sys.path:
    sys.path.insert(0, str(RUNTIME_DIR))

from runtime_common import ensure_dir, iso_now, read_json, write_json, write_text  # noqa: E402


@dataclass
class Candidate:
    path: Path
    kind: str
    risk: str
    reason: str


def _size_bytes(path: Path) -> int:
    if path.is_file():
        return path.stat().st_size
    total = 0
    if path.is_dir():
        for child in path.rglob("*"):
            if child.is_file():
                try:
                    total += child.stat().st_size
                except OSError:
                    continue
    return total


def _mtime(path: Path) -> str:
    try:
        return datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat().replace("+00:00", "Z")
    except OSError:
        return ""


def _relative(root: Path, path: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def _is_under(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def _parse_age(value: str | None) -> timedelta | None:
    if not value:
        return None
    raw = value.strip().lower()
    if raw.endswith("d") and raw[:-1].isdigit():
        return timedelta(days=int(raw[:-1]))
    if raw.endswith("h") and raw[:-1].isdigit():
        return timedelta(hours=int(raw[:-1]))
    raise ValueError("--older-than must use Nd or Nh, for example 30d or 12h")


def _run_status(run_dir: Path) -> str:
    state = run_dir / "state.json"
    if not state.is_file():
        return "unknown"
    try:
        payload = read_json(state)
    except Exception:
        return "unknown"
    return str(payload.get("status") or payload.get("verdict") or "unknown").strip().lower()


def _run_verdict(run_dir: Path) -> str:
    state = run_dir / "state.json"
    if not state.is_file():
        return "unknown"
    try:
        payload = read_json(state)
    except Exception:
        return "unknown"
    return str(payload.get("verdict") or "unknown").strip().upper()


def _selected_run_candidates(
    target_root: Path,
    older_than: timedelta | None,
    keep_last: int | None,
    include_failed_runs: bool,
) -> list[Candidate]:
    runs_root = target_root / ".workflowprogram" / "runs"
    if not runs_root.is_dir():
        return []
    runs = sorted([path for path in runs_root.iterdir() if path.is_dir()], key=lambda p: p.stat().st_mtime, reverse=True)
    newest = runs[0] if runs else None
    keep_by_count = set(runs[: max(keep_last or 0, 0)]) if keep_last is not None else set()
    cutoff = datetime.now(timezone.utc) - older_than if older_than else None
    candidates: list[Candidate] = []
    for run in runs:
        status = _run_status(run)
        verdict = _run_verdict(run)
        protected_reasons: list[str] = []
        if run == newest:
            protected_reasons.append("newest run is retained")
        if run in keep_by_count:
            protected_reasons.append(f"within keep-last={keep_last}")
        if status == "running":
            protected_reasons.append("running run")
        if verdict not in {"PASS", "WARN", "ENVIRONMENT-SKIP", "UNKNOWN"} and not include_failed_runs:
            protected_reasons.append(f"non-pass verdict={verdict}")
        if protected_reasons:
            candidates.append(Candidate(run, "run", "protected", "; ".join(protected_reasons)))
            continue
        if cutoff is not None:
            run_mtime = datetime.fromtimestamp(run.stat().st_mtime, timezone.utc)
            if run_mtime >= cutoff:
                candidates.append(Candidate(run, "run", "protected", f"newer than older-than cutoff {older_than}"))
                continue
        if keep_last is None and older_than is None:
            candidates.append(Candidate(run, "run", "protected", "runs require --older-than or --keep-last"))
            continue
        candidates.append(Candidate(run, "run", "confirm", "historical run selected by pruning policy"))
    return candidates


def build_plan(args: argparse.Namespace) -> dict[str, Any]:
    target_root = Path(args.target_root).resolve()
    if not target_root.exists():
        raise FileNotFoundError(f"target root not found: {target_root}")
    selected_safe = args.all_safe or args.pycache or args.pytest_cache or not any(
        [args.pycache, args.pytest_cache, args.dist, args.node_modules, args.runs]
    )
    candidates: list[Candidate] = []
    if selected_safe or args.pycache:
        for pycache in sorted(target_root.rglob("__pycache__")):
            if ".git" not in pycache.parts:
                candidates.append(Candidate(pycache, "pycache", "safe", "Python bytecode cache"))
        for pyc in sorted(target_root.rglob("*.pyc")):
            if ".git" not in pyc.parts and not any(parent.name == "__pycache__" for parent in pyc.parents):
                candidates.append(Candidate(pyc, "pycache", "safe", "Python bytecode cache file"))
    if selected_safe or args.pytest_cache:
        pytest_cache = target_root / ".pytest_cache"
        if pytest_cache.exists():
            candidates.append(Candidate(pytest_cache, "pytest_cache", "safe", "pytest cache"))
    if args.dist and (target_root / "dist").exists():
        candidates.append(Candidate(target_root / "dist", "dist", "confirm", "build output"))
    if args.node_modules:
        for node_modules in sorted(target_root.rglob("node_modules")):
            if ".git" not in node_modules.parts:
                candidates.append(Candidate(node_modules, "node_modules", "confirm", "local JavaScript dependencies"))
    if args.runs:
        candidates.extend(
            _selected_run_candidates(
                target_root,
                older_than=_parse_age(args.older_than),
                keep_last=args.keep_last,
                include_failed_runs=args.include_failed_runs,
            )
        )

    protected_roots = [
        (target_root / ".workflowprogram" / "design", "target workflow design is the existence truth source"),
        (target_root / ".workflowprogram" / "package", "project-local package install is protected"),
        (target_root / ".workflowprogram" / "runtime", "target runtime wrapper is protected"),
        (target_root / ".workflowprogram" / "managed-files.json", "managed apply manifest is protected"),
        (target_root / ".workflowprogram" / "package" / "install-manifest.json", "install manifest is protected"),
    ]
    for path, reason in protected_roots:
        if path.exists():
            candidates.append(Candidate(path, "protected_state", "protected", reason))

    unique: dict[str, Candidate] = {}
    for candidate in candidates:
        if not _is_under(candidate.path, target_root):
            continue
        rel = _relative(target_root, candidate.path)
        existing = unique.get(rel)
        if existing is None or existing.risk != "protected":
            unique[rel] = candidate

    items: list[dict[str, Any]] = []
    for rel, candidate in sorted(unique.items()):
        items.append(
            {
                "path": rel,
                "absolute_path": str(candidate.path),
                "kind": candidate.kind,
                "risk": candidate.risk,
                "reason": candidate.reason,
                "size_bytes": _size_bytes(candidate.path),
                "last_modified": _mtime(candidate.path),
            }
        )
    return {
        "schema_version": "opencode-clean-v1",
        "action": "clean",
        "target_root": str(target_root),
        "dry_run": not args.yes,
        "generated_at": iso_now(),
        "candidates": items,
        "summary": {
            "safe_count": sum(1 for item in items if item["risk"] == "safe"),
            "confirm_count": sum(1 for item in items if item["risk"] == "confirm"),
            "protected_count": sum(1 for item in items if item["risk"] == "protected"),
            "total_size_bytes": sum(int(item["size_bytes"]) for item in items if item["risk"] in {"safe", "confirm"}),
        },
    }


def apply_plan(plan: dict[str, Any], yes: bool) -> dict[str, Any]:
    deleted: list[str] = []
    skipped: list[str] = []
    target_root = Path(str(plan["target_root"]))
    if yes:
        for item in plan["candidates"]:
            if item["risk"] not in {"safe", "confirm"}:
                skipped.append(item["path"])
                continue
            path = (target_root / item["path"]).resolve()
            if not _is_under(path, target_root):
                skipped.append(item["path"])
                continue
            if path.is_dir():
                shutil.rmtree(path, ignore_errors=True)
                deleted.append(item["path"])
            elif path.exists():
                path.unlink()
                deleted.append(item["path"])
    plan["deleted"] = deleted
    plan["skipped"] = skipped
    plan["verdict"] = "PASS"
    plan["summary"]["deleted_count"] = len(deleted)
    return plan


def report_markdown(plan: dict[str, Any]) -> str:
    lines = [
        "# WorkflowProgram Clean Report",
        "",
        f"- Target root: `{plan['target_root']}`",
        f"- Dry run: `{plan['dry_run']}`",
        f"- Generated at: `{plan['generated_at']}`",
        "",
        "## Summary",
        "",
    ]
    for key, value in plan["summary"].items():
        lines.append(f"- `{key}`: {value}")
    lines.extend(["", "## Candidates", ""])
    for item in plan["candidates"]:
        lines.append(f"- `{item['risk']}` `{item['kind']}` `{item['path']}`: {item['reason']}")
    if plan.get("deleted"):
        lines.extend(["", "## Deleted", ""])
        for path in plan["deleted"]:
            lines.append(f"- `{path}`")
    return "\n".join(lines).rstrip() + "\n"


def write_reports(plan: dict[str, Any]) -> None:
    maintenance = Path(str(plan["target_root"])) / ".workflowprogram" / "maintenance"
    ensure_dir(maintenance)
    write_json(maintenance / "clean-report.json", plan)
    write_text(maintenance / "clean-report.md", report_markdown(plan))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Clean WorkflowProgram local caches safely")
    parser.add_argument("--target-root", default=".")
    parser.add_argument("--package-root")
    parser.add_argument("--pycache", action="store_true")
    parser.add_argument("--pytest-cache", action="store_true")
    parser.add_argument("--dist", action="store_true")
    parser.add_argument("--node-modules", action="store_true")
    parser.add_argument("--runs", action="store_true")
    parser.add_argument("--older-than")
    parser.add_argument("--keep-last", type=int)
    parser.add_argument("--include-failed-runs", action="store_true")
    parser.add_argument("--all-safe", action="store_true")
    parser.add_argument("--yes", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    plan = build_plan(args)
    result = apply_plan(plan, yes=args.yes)
    write_reports(result)
    if args.json:
        json.dump(result, sys.stdout, indent=2, ensure_ascii=True)
        sys.stdout.write("\n")
    else:
        sys.stdout.write(f"[{result['verdict']}] dry_run={result['dry_run']} candidates={len(result['candidates'])}\n")
        sys.stdout.write(str(Path(result["target_root"]) / ".workflowprogram" / "maintenance" / "clean-report.md") + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
