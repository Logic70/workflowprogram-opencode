#!/usr/bin/env python3
"""Validate semantic mutation authorization before managed apply."""

from __future__ import annotations

import argparse
import fnmatch
import json
import sys
from pathlib import Path
from typing import Any


RUNTIME_DIR = Path(__file__).resolve().parent
if str(RUNTIME_DIR) not in sys.path:
    sys.path.insert(0, str(RUNTIME_DIR))

from managed_assets_lib import ALLOWED_MANAGED_PREFIXES  # noqa: E402
from runtime_common import SCHEMA_VERSION, ensure_dir, iso_now, read_json, sha256_file, write_json  # noqa: E402


CHANGE_POLICY_INTENTS = {"evolve", "iterate", "hotfix"}
VALID_CHANGE_MODES = {"incremental", "redesign", "repair"}


def _check(check_id: str, passed: bool, detail: str, failure_category: str | None = None) -> dict[str, Any]:
    return {
        "id": check_id,
        "passed": passed,
        "detail": detail,
        "failure_category": None if passed else failure_category,
    }


def _safe_relative(path_text: str) -> bool:
    cleaned = path_text.replace("\\", "/").strip()
    if not cleaned or cleaned.startswith("/") or cleaned.startswith("~") or "//" in cleaned:
        return False
    return all(part not in {"", ".", ".."} for part in cleaned.split("/"))


def _allowed_managed_path(relative_path: str) -> bool:
    return any(relative_path.startswith(prefix) for prefix in ALLOWED_MANAGED_PREFIXES)


def _covered_by_scope(relative_path: str, scopes: list[str]) -> bool:
    for scope in scopes:
        pattern = scope.replace("\\", "/").strip()
        if pattern.endswith("/**"):
            if relative_path.startswith(pattern[:-2]):
                return True
        if fnmatch.fnmatch(relative_path, pattern):
            return True
    return False


def _candidate_files(candidate_root: Path | None) -> list[str]:
    if candidate_root is None or not candidate_root.is_dir():
        return []
    return [
        path.relative_to(candidate_root).as_posix()
        for path in sorted(candidate_root.rglob("*"))
        if path.is_file()
    ]


def validate_change_policy(
    context: dict[str, Any],
    *,
    target_root: Path | None = None,
    candidate_root: Path | None = None,
    run_root: Path | None = None,
) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    intent = str(context.get("intent", "")).strip()
    target = Path(str(context.get("target_root") or target_root or ".")).resolve()
    base_spec_path = target / ".workflowprogram" / "design" / "workflow-spec.yaml"
    candidate_rel_files = _candidate_files(candidate_root) or [
        str(path).replace("\\", "/").strip()
        for path in context.get("allowed_target_files", [])
        if str(path).strip()
    ]
    declared_scope = [
        str(item).replace("\\", "/").strip()
        for item in context.get("declared_write_scope", [])
        if str(item).strip()
    ]

    checks.append(_check("CHG-01", intent in CHANGE_POLICY_INTENTS, f"intent={intent}", "missing_change_context"))
    checks.append(
        _check(
            "CHG-02",
            context.get("target_workflow_exists") is True and base_spec_path.is_file(),
            f"base_spec={base_spec_path}",
            "missing_change_context",
        )
    )
    change_request = str(context.get("change_request", "")).strip()
    checks.append(
        _check(
            "CHG-03",
            len(change_request.split()) >= 2,
            f"change_request={change_request or '<missing>'}",
            "missing_change_request",
        )
    )
    change_mode = str(context.get("change_mode", "")).strip()
    checks.append(
        _check(
            "CHG-04",
            change_mode in VALID_CHANGE_MODES,
            f"change_mode={change_mode}",
            "missing_change_context",
        )
    )
    checks.append(
        _check(
            "CHG-05",
            context.get("confirmed") is True,
            f"confirmed={context.get('confirmed')}",
            "unconfirmed_change",
        )
    )
    expected_hash = context.get("base_spec_sha256")
    current_hash = sha256_file(base_spec_path) if base_spec_path.is_file() else None
    checks.append(
        _check(
            "CHG-06",
            bool(expected_hash) and expected_hash == current_hash,
            f"expected={expected_hash}; current={current_hash}",
            "stale_change_context",
        )
    )
    unsafe_files = [path for path in candidate_rel_files if not _safe_relative(path) or not _allowed_managed_path(path)]
    checks.append(
        _check(
            "CHG-07",
            not unsafe_files,
            f"unsafe_files={unsafe_files or ['<none>']}",
            "undeclared_write",
        )
    )
    uncovered = [path for path in candidate_rel_files if not _covered_by_scope(path, declared_scope)]
    checks.append(
        _check(
            "CHG-08",
            bool(declared_scope) and not uncovered,
            f"declared_scope={declared_scope}; uncovered={uncovered or ['<none>']}",
            "undeclared_write",
        )
    )

    failed = [check for check in checks if not check["passed"]]
    verdict = "PASS" if not failed else "FAIL"
    summary = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": iso_now(),
        "validator": "validate-change-policy",
        "verdict": verdict,
        "failure_categories": sorted(
            {
                str(check.get("failure_category"))
                for check in failed
                if check.get("failure_category")
            }
        ),
        "checks": checks,
        "context": context,
        "candidate_files": candidate_rel_files,
        "exit_code": 0 if verdict == "PASS" else 1,
    }
    if run_root is not None:
        policy_root = ensure_dir(run_root / "outputs" / "change-policy")
        write_json(policy_root / "change-policy-summary.json", summary)
        write_json(run_root / "outputs" / "stages" / "s3-change-policy.json", summary)
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate WorkflowProgram change policy")
    parser.add_argument("--context", required=True)
    parser.add_argument("--target-root", default="")
    parser.add_argument("--candidate-root", default="")
    parser.add_argument("--run-root", default="")
    parser.add_argument("--json", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    context = read_json(Path(args.context))
    result = validate_change_policy(
        context,
        target_root=Path(args.target_root) if args.target_root else None,
        candidate_root=Path(args.candidate_root) if args.candidate_root else None,
        run_root=Path(args.run_root) if args.run_root else None,
    )
    if args.json:
        json.dump(result, sys.stdout, indent=2, ensure_ascii=True)
        sys.stdout.write("\n")
    else:
        sys.stdout.write(f"{result['verdict']} change_policy\n")
        for check in result["checks"]:
            status = "PASS" if check["passed"] else "FAIL"
            sys.stdout.write(f"{status} {check['id']} {check['detail']}\n")
    return result["exit_code"]


if __name__ == "__main__":
    raise SystemExit(main())
