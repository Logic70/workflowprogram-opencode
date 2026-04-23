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
    diagnostics_root = resolved / "outputs" / "diagnostics"
    clarification_root = resolved / "outputs" / "clarification"

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
    diagnostics_ok = False
    diagnostics_content_ok = False
    clarification_ok = True
    clarification_content_ok = True
    if context_path.is_file() and state_path.is_file() and events_path.is_file():
        context = read_json(context_path)
        state = read_json(state_path)
        events = read_jsonl(events_path)
        intent = str(context.get("intent", "")).strip()
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

        diagnostics_files = {
            "host_capabilities": diagnostics_root / "host-capabilities.json",
            "capability_probe": diagnostics_root / "capability-probe.json",
            "doctor_report": diagnostics_root / "doctor-report.json",
            "environment_remediation": diagnostics_root / "environment-remediation.md",
        }
        diagnostics_ok = all(path.is_file() for path in diagnostics_files.values())
        if diagnostics_ok:
            host_capabilities = read_json(diagnostics_files["host_capabilities"])
            capability_probe = read_json(diagnostics_files["capability_probe"])
            doctor_report = read_json(diagnostics_files["doctor_report"])
            remediation_text = diagnostics_files["environment_remediation"].read_text(encoding="utf-8").strip()
            diagnostics_content_ok = all(
                (
                    isinstance(host_capabilities.get("package_root"), str),
                    isinstance(host_capabilities.get("runtime_root"), str),
                    isinstance(capability_probe.get("probes"), list),
                    capability_probe.get("verdict") in {"PASS", "FAIL"},
                    isinstance(doctor_report.get("checks"), list),
                    doctor_report.get("verdict") in {"PASS", "WARN", "FAIL"},
                    remediation_text.startswith("# Environment Remediation"),
                )
            )

        if intent == "develop":
            clarification_files = {
                "clarification_record": clarification_root / "clarification-record.json",
                "open_questions": clarification_root / "open-questions.json",
                "design_readiness_report": clarification_root / "design-readiness-report.json",
                "assumption_log": clarification_root / "assumption-log.md",
            }
            clarification_ok = all(path.is_file() for path in clarification_files.values())
            if clarification_ok:
                clarification_record = read_json(clarification_files["clarification_record"])
                open_questions = read_json(clarification_files["open_questions"])
                design_readiness = read_json(clarification_files["design_readiness_report"])
                assumption_log = clarification_files["assumption_log"].read_text(encoding="utf-8").strip()
                clarification_content_ok = all(
                    (
                        clarification_record.get("intent") == "develop",
                        isinstance(open_questions.get("blocking"), list),
                        isinstance(open_questions.get("non_blocking"), list),
                        design_readiness.get("ready") is True,
                        assumption_log.startswith("# Assumption Log"),
                    )
                )

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
    checks.append(
        _check(
            "RUN-09",
            diagnostics_ok,
            f"diagnostics_root={diagnostics_root}",
            "evidence_missing",
        )
    )
    checks.append(
        _check(
            "RUN-10",
            diagnostics_content_ok,
            "diagnostic artifacts must contain package_root/runtime_root, probe list, doctor checks, and remediation markdown",
            "evidence_inconsistent",
        )
    )
    checks.append(
        _check(
            "RUN-11",
            clarification_ok,
            f"clarification_root={clarification_root}",
            "evidence_missing",
        )
    )
    checks.append(
        _check(
            "RUN-12",
            clarification_content_ok,
            "develop clarification package must include record, question lists, readiness report, and assumption log",
            "evidence_inconsistent",
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
