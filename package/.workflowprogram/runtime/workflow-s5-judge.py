#!/usr/bin/env python3
"""Contract-aware S5 judge for WorkflowProgram OpenCode package runs."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import yaml


LOOP_EVENT_TYPES = {
    "LoopStart",
    "LoopIterationStart",
    "LoopFeedbackCommandCompleted",
    "LoopAgentCompleted",
    "LoopVerifierCompleted",
    "LoopStop",
}
DESIGN_REF_PATH_KEYS = (
    "requirements",
    "context_findings",
    "design_highlevel",
    "design_lowlevel",
    "implementation_plan",
    "acceptance_tests",
    "traceability_matrix",
)


def _load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    entries: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        try:
            payload = json.loads(stripped)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            entries.append(payload)
    return entries


def _safe_stage_ref(path_text: str, *, node_design: bool = False) -> bool:
    cleaned = path_text.strip().replace("\\", "/")
    if not cleaned or cleaned.startswith("/") or cleaned.startswith("~") or "//" in cleaned:
        return False
    if any(part in {"", ".", ".."} for part in cleaned.split("/")):
        return False
    prefix = "outputs/stages/node-designs/" if node_design else "outputs/stages/"
    return cleaned.startswith(prefix)


def _add_check(checks: list[dict[str, Any]], name: str, status: str, detail: str, source: str) -> None:
    checks.append({"name": name, "status": status, "detail": detail, "source": source})


def _requirement_ids(path: Path) -> list[str]:
    payload = _load_yaml(path)
    requirements = payload.get("requirements", []) if isinstance(payload, dict) else []
    if isinstance(requirements, dict):
        iterable = requirements.values()
    elif isinstance(requirements, list):
        iterable = requirements
    else:
        iterable = []
    ids: list[str] = []
    for item in iterable:
        if not isinstance(item, dict):
            continue
        req_id = str(item.get("id", "")).strip()
        if req_id and req_id not in ids:
            ids.append(req_id)
    return ids


def _node_ids(spec: dict[str, Any]) -> set[str]:
    nodes = spec.get("nodes", []) if isinstance(spec.get("nodes"), list) else []
    return {
        str(node.get("id", "")).strip()
        for node in nodes
        if isinstance(node, dict) and str(node.get("id", "")).strip()
    }


def _loop_enabled_nodes(spec: dict[str, Any]) -> list[dict[str, Any]]:
    nodes = spec.get("nodes", []) if isinstance(spec.get("nodes"), list) else []
    enabled: list[dict[str, Any]] = []
    for node in nodes:
        if not isinstance(node, dict):
            continue
        policy = node.get("loop_policy", {})
        if isinstance(policy, dict) and policy.get("enabled") is True:
            enabled.append(node)
    return enabled


def _add_design_lineage_checks(checks: list[dict[str, Any]], spec: dict[str, Any], run_root: Path) -> None:
    design_refs = spec.get("design_refs", {}) if isinstance(spec.get("design_refs"), dict) else {}
    if not design_refs:
        return
    resolved_paths: dict[str, Path] = {}
    for key in DESIGN_REF_PATH_KEYS:
        raw_value = design_refs.get(key)
        if raw_value is None:
            continue
        rel_path = str(raw_value).strip().replace("\\", "/")
        safe = _safe_stage_ref(rel_path)
        exists = safe and (run_root / rel_path).is_file()
        if safe:
            resolved_paths[key] = run_root / rel_path
        _add_check(
            checks,
            f"design_ref_{key}_exists",
            "PASS" if exists else "FAIL",
            f"{key}={rel_path or '<missing>'}; safe={safe}; exists={exists}",
            f"workflow-spec.yaml.design_refs.{key}",
        )

    declared_nodes = _node_ids(spec)
    node_designs = design_refs.get("node_designs", {})
    if isinstance(node_designs, dict):
        for node_id, raw_path in node_designs.items():
            node_key = str(node_id).strip()
            rel_path = str(raw_path).strip().replace("\\", "/")
            safe = _safe_stage_ref(rel_path, node_design=True)
            exists = safe and (run_root / rel_path).is_file()
            declared = node_key in declared_nodes
            _add_check(
                checks,
                f"design_ref_node_design_{node_key or 'missing'}",
                "PASS" if safe and exists and declared else "FAIL",
                f"node={node_key or '<missing>'}; declared={declared}; path={rel_path or '<missing>'}; safe={safe}; exists={exists}",
                f"workflow-spec.yaml.design_refs.node_designs.{node_key or '<missing>'}",
            )

    requirements_path = resolved_paths.get("requirements")
    traceability_path = resolved_paths.get("traceability_matrix")
    if requirements_path and traceability_path and requirements_path.is_file() and traceability_path.is_file():
        requirement_ids = _requirement_ids(requirements_path)
        traceability_text = traceability_path.read_text(encoding="utf-8")
        missing = [req_id for req_id in requirement_ids if req_id not in traceability_text]
        _add_check(
            checks,
            "design_lineage_requirement_traceability",
            "PASS" if requirement_ids and not missing else "FAIL",
            f"requirements={requirement_ids or ['<none>']}; missing_in_traceability={missing or ['<none>']}",
            "outputs/stages/traceability-matrix.json",
        )


def _add_loop_checks(checks: list[dict[str, Any]], spec: dict[str, Any], run_root: Path) -> None:
    loop_nodes = _loop_enabled_nodes(spec)
    if not loop_nodes:
        return
    events = _load_jsonl(run_root / "events.jsonl")
    event_types = {str(event.get("type", "")).strip() for event in events}
    event_types_present = LOOP_EVENT_TYPES.issubset(event_types)
    for node in loop_nodes:
        node_id = str(node.get("id", "")).strip()
        policy = node.get("loop_policy", {}) if isinstance(node.get("loop_policy"), dict) else {}
        loop_root = run_root / "outputs" / "stages" / "loops" / node_id
        loop_plan = _load_json(loop_root / "loop-plan.json")
        final_verdict = _load_json(loop_root / "final-verdict.json")
        iterations = _load_jsonl(loop_root / "iteration-summary.jsonl")
        structured = bool(loop_plan) and bool(final_verdict) and bool(iterations)
        _add_check(
            checks,
            "node_loop_evidence_present",
            "PASS" if structured and event_types_present else "FAIL",
            f"node={node_id}; structured={structured}; events={sorted(LOOP_EVENT_TYPES & event_types)}",
            f"nodes.{node_id}.loop_policy",
        )

        max_iterations = int(policy.get("max_iterations", 0) or 0)
        observed_iterations = len(iterations)
        _add_check(
            checks,
            "node_loop_iteration_limit_observed",
            "PASS" if not max_iterations or observed_iterations <= max_iterations else "FAIL",
            f"node={node_id}; observed_iterations={observed_iterations}; max_iterations={max_iterations}",
            f"nodes.{node_id}.loop_policy.max_iterations",
        )

        final_status = str(final_verdict.get("status", "")).strip().upper() if final_verdict else ""
        verifier_passed = bool(final_verdict.get("verifier_passed", False)) if final_verdict else False
        _add_check(
            checks,
            "node_loop_verifier_gate_observed",
            "PASS" if final_status != "PASS" or verifier_passed else "FAIL",
            f"node={node_id}; final_status={final_status or '<missing>'}; verifier_passed={verifier_passed}",
            f"outputs/stages/loops/{node_id}/final-verdict.json",
        )
        stop_reason = str(final_verdict.get("stop_reason", "")).strip() if final_verdict else ""
        _add_check(
            checks,
            "node_loop_stop_reason_valid",
            "PASS" if stop_reason else "FAIL",
            f"node={node_id}; stop_reason={stop_reason or '<missing>'}",
            f"outputs/stages/loops/{node_id}/final-verdict.json",
        )

        if str(policy.get("goal_source", "user")).strip() == "model_subgoal":
            parent_goal = str(loop_plan.get("parent_goal_ref", "")).strip() if loop_plan else ""
            _add_check(
                checks,
                "node_loop_model_subgoal_trace_present",
                "PASS" if parent_goal else "FAIL",
                f"node={node_id}; parent_goal_ref={parent_goal or '<missing>'}",
                f"nodes.{node_id}.loop_policy.parent_goal_ref",
            )

        tdd_policy = policy.get("tdd_policy", {}) if isinstance(policy.get("tdd_policy"), dict) else {}
        if tdd_policy.get("enabled") is True and tdd_policy.get("test_first_required") is True:
            test_first_observed = bool(loop_plan.get("test_first_observed", False)) if loop_plan else False
            _add_check(
                checks,
                "node_loop_tdd_trace_observed",
                "PASS" if test_first_observed else "FAIL",
                f"node={node_id}; test_first_observed={test_first_observed}",
                f"nodes.{node_id}.loop_policy.tdd_policy",
            )


def _first_clarification_path(run_root: Path, name: str) -> Path:
    for root in (run_root / "outputs" / "stages", run_root / "outputs" / "clarification"):
        path = root / name
        if path.is_file():
            return path
    return run_root / "outputs" / "stages" / name


def _add_requirement_logic_checks(checks: list[dict[str, Any]], run_root: Path, state: dict[str, Any]) -> None:
    if str(state.get("intent", "")).strip() != "develop":
        return
    required = (
        "clarification-record.json",
        "open-questions.json",
        "question-backlog.json",
        "requirement-logic-map.json",
        "design-readiness-report.json",
        "clarification-challenge-report.json",
        "clarification-handoff.json",
        "clarification-evidence.json",
        "assumption-log.md",
    )
    missing = [name for name in required if not _first_clarification_path(run_root, name).is_file()]
    _add_check(
        checks,
        "requirement_logic_artifacts_exist",
        "PASS" if not missing else "FAIL",
        f"missing={missing or ['<none>']}",
        "outputs/stages/*clarification*",
    )
    if missing:
        return
    record = _load_json(_first_clarification_path(run_root, "clarification-record.json"))
    questions = _load_json(_first_clarification_path(run_root, "open-questions.json"))
    backlog = _load_json(_first_clarification_path(run_root, "question-backlog.json"))
    logic_map = _load_json(_first_clarification_path(run_root, "requirement-logic-map.json"))
    readiness = _load_json(_first_clarification_path(run_root, "design-readiness-report.json"))
    challenge = _load_json(_first_clarification_path(run_root, "clarification-challenge-report.json"))
    handoff = _load_json(_first_clarification_path(run_root, "clarification-handoff.json"))
    evidence = _load_json(_first_clarification_path(run_root, "clarification-evidence.json"))
    required_lenses = {
        "purpose",
        "object_model",
        "process_model",
        "decision_model",
        "evidence_model",
        "acceptance_model",
        "boundary_model",
    }
    lens_names = (
        set(logic_map.get("logic_lenses", {}).keys())
        if isinstance(logic_map.get("logic_lenses"), dict)
        else set()
    )
    _add_check(
        checks,
        "requirement_logic_lenses_complete",
        "PASS" if required_lenses.issubset(lens_names) else "FAIL",
        f"lenses={sorted(lens_names)}",
        "outputs/stages/requirement-logic-map.json",
    )
    _add_check(
        checks,
        "requirement_logic_questions_design_consequential",
        "PASS"
        if questions.get("method") == "requirement-logic-interview"
        and isinstance(backlog.get("items"), list)
        and len(backlog.get("items", [])) >= 7
        else "FAIL",
        f"method={questions.get('method')}; backlog_size={len(backlog.get('items', [])) if isinstance(backlog.get('items'), list) else 0}",
        "outputs/stages/question-backlog.json",
    )
    review_roles = challenge.get("review_roles", []) if isinstance(challenge.get("review_roles"), list) else []
    _add_check(
        checks,
        "requirement_logic_review_roles_internal_only",
        "PASS"
        if record.get("lead_role") == "requirement-clarification-lead"
        and all(isinstance(role, dict) and role.get("direct_user_contact") is False for role in review_roles)
        else "FAIL",
        f"lead={record.get('lead_role')}; review_roles={review_roles}",
        "outputs/stages/clarification-challenge-report.json",
    )
    _add_check(
        checks,
        "requirement_logic_handoff_ready",
        "PASS"
        if isinstance(handoff.get("s2_inputs"), dict)
        and isinstance(handoff.get("s3_inputs"), dict)
        and bool(handoff.get("logic_map_path"))
        and bool(handoff.get("question_backlog_path"))
        and evidence.get("logic_map_ready") in {True, False}
        and evidence.get("s2_handoff_ready") in {True, False}
        and evidence.get("s3_handoff_ready") in {True, False}
        else "FAIL",
        f"ready={handoff.get('ready')}; evidence={{logic:{evidence.get('logic_map_ready')}, s2:{evidence.get('s2_handoff_ready')}, s3:{evidence.get('s3_handoff_ready')}}}",
        "outputs/stages/clarification-handoff.json",
    )
    if readiness.get("ready") is True:
        _add_check(
            checks,
            "requirement_logic_confirmed_ready",
            "PASS"
            if evidence.get("readback_confirmed") is True
            and evidence.get("logic_map_ready") is True
            and evidence.get("s2_handoff_ready") is True
            and evidence.get("s3_handoff_ready") is True
            else "FAIL",
            f"readback_confirmed={evidence.get('readback_confirmed')}",
            "outputs/stages/clarification-evidence.json",
        )


def _add_change_policy_checks(checks: list[dict[str, Any]], run_root: Path, state: dict[str, Any]) -> None:
    intent = str(state.get("intent", "")).strip()
    if intent not in {"hotfix", "iterate", "evolve"}:
        return
    context = _load_json(run_root / "outputs" / "change-policy" / "change-context.json")
    summary = _load_json(run_root / "outputs" / "change-policy" / "change-policy-summary.json")
    staged = _load_json(run_root / "outputs" / "stages" / "s3-change-policy.json")
    artifacts_present = bool(context) and bool(summary) and bool(staged)
    _add_check(
        checks,
        "change_policy_artifacts_exist",
        "PASS" if artifacts_present else "FAIL",
        f"context={bool(context)}; summary={bool(summary)}; staged={bool(staged)}",
        "outputs/change-policy/*",
    )
    if not artifacts_present:
        return
    _add_check(
        checks,
        "change_policy_context_authorized",
        "PASS"
        if context.get("intent") == intent
        and context.get("target_workflow_exists") is True
        and context.get("confirmed") is True
        and bool(context.get("change_request"))
        else "FAIL",
        f"intent={context.get('intent')}; exists={context.get('target_workflow_exists')}; confirmed={context.get('confirmed')}; request={context.get('change_request') or '<missing>'}",
        "outputs/change-policy/change-context.json",
    )
    _add_check(
        checks,
        "change_policy_validation_passed",
        "PASS" if summary.get("verdict") == "PASS" and staged.get("verdict") == "PASS" else "FAIL",
        f"summary={summary.get('verdict')}; staged={staged.get('verdict')}; failures={summary.get('failure_categories', [])}",
        "outputs/change-policy/change-policy-summary.json",
    )


def _failure_kind_from_layers(summary: dict[str, Any]) -> str | None:
    layers = summary.get("layers", {})
    for layer_name in ("package", "spec", "target", "run_state"):
        layer = layers.get(layer_name, {})
        if layer.get("verdict") != "FAIL":
            continue
        if layer_name in {"package", "spec"}:
            return "design"
        return "implementation"
    return None


def judge_run(run_root: Path, validation_summary: dict[str, Any] | None = None) -> dict[str, Any]:
    resolved = run_root.resolve()
    summary = validation_summary or _load_json(resolved / "validation-summary.json")
    state = _load_json(resolved / "state.json")
    spec = _load_yaml(resolved / "workflow-spec.yaml")
    layers = summary.get("layers", {})
    verdict = str(summary.get("verdict", "WARN")).strip() or "WARN"
    failure_kind = _failure_kind_from_layers(summary)
    first_failed_layer = next(
        (name for name in ("package", "spec", "target", "run_state") if layers.get(name, {}).get("verdict") == "FAIL"),
        None,
    )
    checks: list[dict[str, Any]] = []
    _add_design_lineage_checks(checks, spec, resolved)
    _add_loop_checks(checks, spec, resolved)
    _add_requirement_logic_checks(checks, resolved, state)
    _add_change_policy_checks(checks, resolved, state)
    contract_failed = any(check["status"] == "FAIL" for check in checks)
    contract_warned = any(check["status"] == "WARN" for check in checks)
    if contract_failed:
        verdict = "FAIL"
        failure_kind = failure_kind or "implementation"
    elif contract_warned and verdict == "PASS":
        verdict = "WARN"
    failure_code = f"S5_{str(first_failed_layer).upper()}_FAILED" if first_failed_layer else ""
    if contract_failed and not failure_code:
        failure_code = "S5_CONTRACT_EVIDENCE_FAILED"
    payload = {
        "run_root": str(resolved),
        "verdict": verdict,
        "failure_kind": failure_kind,
        "failure_code": failure_code,
        "state_verdict": state.get("verdict"),
        "first_failed_layer": first_failed_layer,
        "layers": {name: layer.get("verdict") for name, layer in layers.items()},
        "checks": checks,
    }

    report_lines = [
        "# S5 Judge Report",
        "",
        f"- Verdict: `{payload['verdict']}`",
        f"- Failure kind: `{payload['failure_kind']}`",
        f"- Failure code: `{payload['failure_code']}`",
        "",
    ]
    if first_failed_layer:
        report_lines.append(f"- First failed layer: `{first_failed_layer}`")
    else:
        report_lines.append("- First failed layer: `none`")
    report_lines.extend(["", "## Layer Verdicts", ""])
    for layer_name, layer_verdict in payload["layers"].items():
        report_lines.append(f"- `{layer_name}`: `{layer_verdict}`")
    if checks:
        report_lines.extend(["", "## Contract Evidence Checks", ""])
        for check in checks:
            report_lines.append(
                f"- `{check['status']}` `{check['name']}`: {check['detail']} ({check['source']})"
            )

    stage_payload_path = resolved / "outputs" / "stages" / "s5-judge-summary.json"
    report_path = resolved / "validation-runtime-report.md"
    stage_payload_path.parent.mkdir(parents=True, exist_ok=True)
    stage_payload_path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    report_path.write_text("\n".join(report_lines) + "\n", encoding="utf-8", newline="\n")
    return payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the WorkflowProgram S5 judge")
    parser.add_argument("--run-root", required=True)
    parser.add_argument("--json", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    result = judge_run(Path(args.run_root))
    if args.json:
        json.dump(result, sys.stdout, indent=2, ensure_ascii=True)
        sys.stdout.write("\n")
    else:
        sys.stdout.write(f"{result['verdict']} run_root={result['run_root']}\n")
    return 0 if result["verdict"] != "FAIL" else 1


if __name__ == "__main__":
    raise SystemExit(main())
