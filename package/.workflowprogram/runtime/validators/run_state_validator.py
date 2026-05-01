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

from runtime_common import FAILURE_KINDS, MUTATING_PACKAGE_INTENTS, SCHEMA_VERSION, read_json, read_jsonl, sha256_file  # noqa: E402
from error_codes import code_for, remediation_for  # noqa: E402


def _check(check_id: str, passed: bool, detail: str, category: str) -> dict[str, Any]:
    return {
        "id": check_id,
        "passed": passed,
        "detail": detail,
        "category": category,
        "error_code": None if passed else code_for(category, check_id),
        "remediation": None if passed else remediation_for(category),
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
    team_plan_path = resolved / "outputs" / "team-plan.json"
    managed_result_path = resolved / "outputs" / "managed-change-result.json"

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
    team_plan_ok = True
    ai_collaboration_ok = True
    run_design_artifacts_ok = True
    target_design_match_ok = True
    apply_recovery_ok = True
    schema_version_ok = True
    if context_path.is_file() and state_path.is_file() and events_path.is_file():
        context = read_json(context_path)
        state = read_json(state_path)
        events = read_jsonl(events_path)
        intent = str(context.get("intent", "")).strip()
        schema_version_ok = state.get("schema_version") in {SCHEMA_VERSION, None}
        verdict_ok = state.get("verdict") in {"PASS", "WARN", "FAIL", "ENVIRONMENT-SKIP"}
        failure_kind = state.get("failure_kind")
        failure_kind_ok = failure_kind in list(FAILURE_KINDS) + [None]
        evidence_chain_ok = (
            context.get("run_root") == str(resolved)
            and state.get("run_root") == str(resolved)
            and bool(events)
        )
        ai_collaboration = state.get("ai_collaboration")
        if ai_collaboration is not None:
            ai_collaboration_ok = (
                isinstance(ai_collaboration, dict)
                and isinstance(ai_collaboration.get("evidence_supplied"), bool)
                and ai_collaboration.get("success_gate") is False
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
                "clarification_challenge_report": clarification_root / "clarification-challenge-report.json",
                "clarification_handoff": clarification_root / "clarification-handoff.json",
                "clarification_evidence": clarification_root / "clarification-evidence.json",
                "assumption_log": clarification_root / "assumption-log.md",
            }
            clarification_ok = all(path.is_file() for path in clarification_files.values())
            if clarification_ok:
                clarification_record = read_json(clarification_files["clarification_record"])
                open_questions = read_json(clarification_files["open_questions"])
                design_readiness = read_json(clarification_files["design_readiness_report"])
                challenge_report = read_json(clarification_files["clarification_challenge_report"])
                handoff = read_json(clarification_files["clarification_handoff"])
                evidence = read_json(clarification_files["clarification_evidence"])
                assumption_log = clarification_files["assumption_log"].read_text(encoding="utf-8").strip()
                clarification_content_ok = all(
                    (
                        clarification_record.get("intent") == "develop",
                        isinstance(open_questions.get("blocking"), list),
                        isinstance(open_questions.get("non_blocking"), list),
                        isinstance(design_readiness.get("ready"), bool),
                        isinstance(challenge_report.get("challenge_rounds"), int),
                        isinstance(handoff.get("s3_inputs"), dict),
                        evidence.get("legacy_ai_evidence_success_gate") is False,
                        assumption_log.startswith("# Assumption Log"),
                    )
                )

        if team_plan_path.is_file():
            team_plan = read_json(team_plan_path)
            team_plan_ok = (
                team_plan.get("planner") == "workflowprogram-agent-team-planner"
                and team_plan.get("intent") == intent
                and isinstance(team_plan.get("selected_agents"), list)
                and isinstance(team_plan.get("fan_in"), dict)
            )

        if intent in MUTATING_PACKAGE_INTENTS:
            apply_recovery_ok = False
            if managed_result_path.is_file():
                managed_result = read_json(managed_result_path)
                rollback_path = managed_result.get("rollback_manifest")
                apply_recovery_ok = (
                    managed_result.get("schema_version") in {SCHEMA_VERSION, None}
                    and isinstance(managed_result.get("lock"), dict)
                    and isinstance(rollback_path, str)
                    and Path(rollback_path).is_file()
                )
                target_root = Path(str(context.get("target", {}).get("target_root", "")))
                run_design_files = [
                    resolved / "workflow-spec.yaml",
                    resolved / "workflow-view.md",
                    resolved / "workflow-lowlevel.md",
                ]
                target_design_files = [
                    target_root / ".workflowprogram" / "design" / "workflow-spec.yaml",
                    target_root / ".workflowprogram" / "design" / "workflow-view.md",
                    target_root / ".workflowprogram" / "design" / "workflow-lowlevel.md",
                ]
                run_design_artifacts_ok = all(path.is_file() for path in run_design_files)
                target_design_match_ok = (
                    run_design_artifacts_ok
                    and all(path.is_file() for path in target_design_files)
                    and all(
                        sha256_file(run_file) == sha256_file(target_file)
                        for run_file, target_file in zip(run_design_files, target_design_files)
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
            "develop clarification package must include record, questions, challenge report, handoff, evidence, readiness, and assumptions",
            "evidence_inconsistent",
        )
    )
    checks.append(
        _check(
            "AGT-02",
            team_plan_ok,
            f"optional_team_plan={team_plan_path}",
            "orchestration",
        )
    )
    checks.append(
        _check(
            "AGT-03",
            ai_collaboration_ok,
            "legacy ai evidence is optional and must not be a success gate when present",
            "orchestration",
        )
    )
    checks.append(
        _check(
            "RUN-13",
            run_design_artifacts_ok,
            "mutating run must retain workflow-spec.yaml, workflow-view.md, and workflow-lowlevel.md in RUN_ROOT after managed apply",
            "evidence_missing",
        )
    )
    checks.append(
        _check(
            "RUN-14",
            target_design_match_ok,
            "target design artifacts must match the accepted RUN_ROOT design artifacts",
            "bundle_mismatch",
        )
    )
    checks.append(
        _check(
            "MIG-01",
            schema_version_ok,
            f"schema_version={SCHEMA_VERSION}",
            "schema_contract",
        )
    )
    checks.append(
        _check(
            "APP-01",
            apply_recovery_ok,
            f"managed_result={managed_result_path}",
            "apply_recovery",
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
