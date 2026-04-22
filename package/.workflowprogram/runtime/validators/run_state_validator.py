#!/usr/bin/env python3
"""Run-state validator for WorkflowProgram runtime evidence."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


RUNTIME_DIR = Path(__file__).resolve().parents[1]
if str(RUNTIME_DIR) not in sys.path:
    sys.path.insert(0, str(RUNTIME_DIR))

from runtime_common import FAILURE_KINDS, STAGE_SLOTS, read_json, read_jsonl  # noqa: E402


def _check(check_id: str, passed: bool, detail: str, category: str) -> dict[str, Any]:
    return {
        "id": check_id,
        "passed": passed,
        "detail": detail,
        "category": category,
    }


def validate_run_state(run_root: Path) -> dict[str, Any]:
    resolved = run_root.resolve()
    checks: list[dict[str, Any]] = []
    context_path = resolved / "context.json"
    state_path = resolved / "state.json"
    events_path = resolved / "events.jsonl"
    progress_root = resolved / "outputs" / "progress"
    stages_root = resolved / "outputs" / "stages"

    checks.append(_check("RUN-01", context_path.is_file(), f"context={context_path}", "evidence_missing"))
    checks.append(_check("RUN-02", state_path.is_file(), f"state={state_path}", "evidence_missing"))
    checks.append(_check("RUN-03", events_path.is_file(), f"events={events_path}", "evidence_missing"))

    stage_files = sorted(path.name for path in stages_root.glob("*.json")) if stages_root.exists() else []
    checks.append(
        _check(
            "RUN-04",
            bool(stage_files),
            f"stage_files={stage_files}",
            "evidence_missing",
        )
    )

    verdict_ok = False
    failure_kind_ok = False
    evidence_chain_ok = False
    progress_ok = False
    if context_path.is_file() and state_path.is_file() and events_path.is_file():
        context = read_json(context_path)
        state = read_json(state_path)
        events = read_jsonl(events_path)
        verdict_ok = state.get("verdict") in {"PASS", "WARN", "FAIL", "ENVIRONMENT-SKIP"}
        failure_kind = state.get("failure_kind")
        failure_kind_ok = failure_kind in list(FAILURE_KINDS) + [None]
        evidence_chain_ok = (
            context.get("run_root") == str(resolved)
            and state.get("run_root") == str(resolved)
            and bool(events)
        )
        current_progress = progress_root / "current-progress.json"
        milestones = progress_root / "milestones.jsonl"
        user_progress = progress_root / "user-progress.md"
        progress_ok = current_progress.is_file() and milestones.is_file() and user_progress.is_file()

    checks.append(_check("RUN-05", verdict_ok, "state.verdict must be valid", "state_invalid"))
    checks.append(
        _check(
            "RUN-06",
            failure_kind_ok,
            f"allowed_failure_kinds={list(FAILURE_KINDS) + [None]}",
            "state_invalid",
        )
    )
    checks.append(_check("RUN-07", evidence_chain_ok, "context/state/events must align on run_root", "evidence_inconsistent"))
    checks.append(
        _check(
            "RUN-08",
            progress_ok,
            f"required_progress_files={[str(progress_root / 'current-progress.json'), str(progress_root / 'milestones.jsonl'), str(progress_root / 'user-progress.md')]}",
            "evidence_missing",
        )
    )

    failed = [check for check in checks if not check["passed"]]
    verdict = "PASS" if not failed else "FAIL"
    return {
        "validator": "run_state_validator",
        "run_root": str(resolved),
        "verdict": verdict,
        "summary": "Run-state evidence validated" if verdict == "PASS" else "Run-state evidence validation failed",
        "checks": checks,
        "exit_code": 0 if verdict == "PASS" else 1,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate run-state evidence")
    parser.add_argument("--run-root", required=True)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = validate_run_state(Path(args.run_root))
    if args.json:
        json.dump(result, sys.stdout, indent=2, ensure_ascii=True)
        sys.stdout.write("\n")
    else:
        sys.stdout.write(f"{result['verdict']} run_root={result['run_root']}\n")
        for check in result["checks"]:
            status = "PASS" if check["passed"] else "FAIL"
            sys.stdout.write(f"{status} {check['id']} {check['detail']}\n")
    return result["exit_code"]


if __name__ == "__main__":
    raise SystemExit(main())
