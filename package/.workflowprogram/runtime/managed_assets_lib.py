#!/usr/bin/env python3
"""Managed apply helpers for WorkflowProgram target bundle delivery."""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from runtime_common import append_jsonl, iso_now, read_json, sha256_file, write_json, write_text


ALLOWED_MANAGED_PREFIXES = (
    ".workflowprogram/design/",
    ".workflowprogram/runtime/",
    ".opencode/commands/",
    ".opencode/plugins/",
)


@dataclass
class CandidateDecision:
    relative_path: str
    source_path: str
    target_path: str
    source_sha256: str
    target_exists: bool
    target_sha256: str | None
    decision: str
    reason: str
    manifest_entry: dict[str, Any] | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "relative_path": self.relative_path,
            "source_path": self.source_path,
            "target_path": self.target_path,
            "source_sha256": self.source_sha256,
            "target_exists": self.target_exists,
            "target_sha256": self.target_sha256,
            "decision": self.decision,
            "reason": self.reason,
            "manifest_entry": self.manifest_entry,
        }


def manifest_path_for(target_root: Path) -> Path:
    return target_root / ".workflowprogram" / "managed-files.json"


def load_manifest(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {
            "manifest_version": 1,
            "updated_at": None,
            "entries": [],
        }
    return read_json(path)


def save_manifest(path: Path, payload: dict[str, Any]) -> None:
    payload["updated_at"] = iso_now()
    write_json(path, payload)


def ensure_candidate_root(source_root: Path) -> None:
    if not source_root.exists():
        raise FileNotFoundError(f"Candidate source root not found: {source_root}")
    if not source_root.is_dir():
        raise NotADirectoryError(f"Candidate source root must be a directory: {source_root}")


def _iter_candidate_files(source_root: Path):
    for path in sorted(source_root.rglob("*")):
        if path.is_file():
            yield path


def _candidate_relative_path(source_root: Path, source_file: Path) -> str:
    relative_path = source_file.relative_to(source_root).as_posix()
    if not relative_path.startswith(ALLOWED_MANAGED_PREFIXES):
        raise RuntimeError(
            f"Candidate file must live under {ALLOWED_MANAGED_PREFIXES}, got: {relative_path}"
        )
    if relative_path == ".workflowprogram/managed-files.json":
        raise RuntimeError("Candidate root must not stage .workflowprogram/managed-files.json directly")
    return relative_path


def _entry_index(manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {entry["relative_path"]: entry for entry in manifest.get("entries", [])}


def _summarize(decisions: list[CandidateDecision]) -> dict[str, int]:
    summary = {
        "candidate_files": len(decisions),
        "create": 0,
        "update": 0,
        "noop": 0,
        "conflict": 0,
    }
    for item in decisions:
        if item.decision in summary:
            summary[item.decision] += 1
        else:
            summary["conflict"] += 1
    return summary


def _decide_candidates(target_root: Path, source_root: Path, manifest: dict[str, Any]) -> list[CandidateDecision]:
    manifest_entries = _entry_index(manifest)
    decisions: list[CandidateDecision] = []

    for source_file in _iter_candidate_files(source_root):
        relative_path = _candidate_relative_path(source_root, source_file)
        target_path = target_root / relative_path
        source_sha = sha256_file(source_file)
        target_exists = target_path.exists()
        target_sha = sha256_file(target_path) if target_exists else None
        manifest_entry = manifest_entries.get(relative_path)

        if not target_exists:
            decision = CandidateDecision(
                relative_path=relative_path,
                source_path=str(source_file),
                target_path=str(target_path),
                source_sha256=source_sha,
                target_exists=False,
                target_sha256=None,
                decision="create",
                reason="Target file does not exist.",
                manifest_entry=manifest_entry,
            )
        elif manifest_entry is None:
            decision = CandidateDecision(
                relative_path=relative_path,
                source_path=str(source_file),
                target_path=str(target_path),
                source_sha256=source_sha,
                target_exists=True,
                target_sha256=target_sha,
                decision="conflict",
                reason="Target file exists but is not registered as managed.",
                manifest_entry=None,
            )
        elif target_sha == source_sha:
            decision = CandidateDecision(
                relative_path=relative_path,
                source_path=str(source_file),
                target_path=str(target_path),
                source_sha256=source_sha,
                target_exists=True,
                target_sha256=target_sha,
                decision="noop",
                reason="Managed file already matches candidate content.",
                manifest_entry=manifest_entry,
            )
        elif target_sha == manifest_entry.get("last_applied_hash"):
            decision = CandidateDecision(
                relative_path=relative_path,
                source_path=str(source_file),
                target_path=str(target_path),
                source_sha256=source_sha,
                target_exists=True,
                target_sha256=target_sha,
                decision="update",
                reason="Managed file matches the last applied hash.",
                manifest_entry=manifest_entry,
            )
        else:
            decision = CandidateDecision(
                relative_path=relative_path,
                source_path=str(source_file),
                target_path=str(target_path),
                source_sha256=source_sha,
                target_exists=True,
                target_sha256=target_sha,
                decision="conflict",
                reason="Managed file drift detected after the last applied version.",
                manifest_entry=manifest_entry,
            )
        decisions.append(decision)

    return decisions


def plan_payload(target_root: Path, source_root: Path, run_root: Path, producer_version: str) -> dict[str, Any]:
    manifest = load_manifest(manifest_path_for(target_root))
    decisions = _decide_candidates(target_root, source_root, manifest)
    summary = _summarize(decisions)
    return {
        "generated_at": iso_now(),
        "target_root": str(target_root),
        "source_root": str(source_root),
        "run_root": str(run_root),
        "producer_version": producer_version,
        "summary": summary,
        "status": "conflict" if summary["conflict"] else "ready",
        "entries": [item.to_dict() for item in decisions],
    }


def _copy_conflict(run_root: Path, relative_path: str, source_path: Path) -> str:
    conflict_path = run_root / "outputs" / "conflicts" / relative_path
    conflict_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_path, conflict_path)
    return str(conflict_path)


def _update_manifest(manifest: dict[str, Any], applied: list[dict[str, Any]], run_root: Path, producer_version: str) -> dict[str, Any]:
    entries = _entry_index(manifest)
    for item in applied:
        entries[item["relative_path"]] = {
            "relative_path": item["relative_path"],
            "ownership": "managed",
            "producer_version": producer_version,
            "last_applied_hash": item["applied_sha256"],
            "last_applied_at": iso_now(),
            "last_run_id": run_root.name,
        }
    manifest["entries"] = [entries[key] for key in sorted(entries.keys())]
    return manifest


def _write_markdown_summary(path: Path, result: dict[str, Any]) -> None:
    lines = [
        "# Managed Apply Summary",
        "",
        f"- Status: `{result['status']}`",
        f"- Target root: `{result['target_root']}`",
        f"- Source root: `{result['source_root']}`",
        f"- Applied: `{len(result['applied'])}`",
        f"- Conflicts: `{len(result['conflicts'])}`",
        "",
        "## Applied",
        "",
    ]
    if result["applied"]:
        lines.extend(f"- `{item['relative_path']}` ({item['action']})" for item in result["applied"])
    else:
        lines.append("- None")
    lines.extend(["", "## Conflicts", ""])
    if result["conflicts"]:
        lines.extend(
            f"- `{item['relative_path']}`: {item['reason']}" for item in result["conflicts"]
        )
    else:
        lines.append("- None")
    write_text(path, "\n".join(lines) + "\n")


def _emit_event(run_root: Path, event_type: str, status: str, message: str, **extra: Any) -> None:
    append_jsonl(
        run_root / "events.jsonl",
        {
            "ts": iso_now(),
            "type": event_type,
            "stage": "managed-apply",
            "status": status,
            "message": message,
            **extra,
        },
    )


def apply_staged(target_root: Path, source_root: Path, run_root: Path, producer_version: str) -> tuple[dict[str, Any], dict[str, Any]]:
    ensure_candidate_root(source_root)
    plan = plan_payload(target_root, source_root, run_root, producer_version)
    manifest = load_manifest(manifest_path_for(target_root))

    applied: list[dict[str, Any]] = []
    conflicts: list[dict[str, Any]] = []

    for item in plan["entries"]:
        source_path = Path(item["source_path"])
        target_path = Path(item["target_path"])
        if item["decision"] in {"create", "update"}:
            target_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_path, target_path)
            applied_item = {
                "relative_path": item["relative_path"],
                "action": item["decision"],
                "target_path": item["target_path"],
                "applied_sha256": sha256_file(target_path),
            }
            applied.append(applied_item)
            _emit_event(run_root, "ManagedAssetApplied", "ok", f"Applied {item['relative_path']}")
        elif item["decision"] == "noop":
            _emit_event(run_root, "ManagedAssetNoop", "ok", f"No change for {item['relative_path']}")
        else:
            conflict_copy = _copy_conflict(run_root, item["relative_path"], source_path)
            conflict_item = {**item, "conflict_copy": conflict_copy}
            conflicts.append(conflict_item)
            _emit_event(run_root, "ManagedAssetConflict", "warn", f"Conflict on {item['relative_path']}")

    manifest = _update_manifest(manifest, applied, run_root, producer_version)
    save_manifest(manifest_path_for(target_root), manifest)

    result = {
        "generated_at": iso_now(),
        "target_root": str(target_root),
        "source_root": str(source_root),
        "run_root": str(run_root),
        "producer_version": producer_version,
        "status": "conflict" if conflicts else "applied",
        "summary": plan["summary"],
        "applied": applied,
        "conflicts": conflicts,
        "manifest_path": str(manifest_path_for(target_root)),
    }

    write_json(run_root / "outputs" / "managed-change-plan.json", plan)
    write_json(run_root / "outputs" / "managed-change-result.json", result)
    _write_markdown_summary(run_root / "outputs" / "managed-change-summary.md", result)
    return plan, result
