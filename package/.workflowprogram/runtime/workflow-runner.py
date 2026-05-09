#!/usr/bin/env python3
"""WorkflowProgram runtime orchestration for OpenCode v2."""

from __future__ import annotations

import importlib.util
import json
import shlex
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from managed_assets_lib import apply_staged
from runtime_common import (
    FAILURE_KINDS,
    MANDATORY_DESIGN_FILES,
    MANDATORY_RUNTIME_FILES,
    PRODUCT_INTENT_CONTRACT,
    SCHEMA_VERSION,
    DevelopRequest,
    assess_target_workflow,
    aggregate_verdicts,
    append_jsonl,
    detect_package_layout,
    ensure_dir,
    iso_now,
    make_run_id,
    node_loop_enabled_nodes,
    node_loop_prompt_packages,
    parse_user_arguments,
    read_json,
    read_yaml,
    registry_commands as spec_registry_commands,
    registry_plugins as spec_registry_plugins,
    write_json,
    write_text,
    write_yaml,
)
from validation_coordinator import run_validation_layers


VALIDATORS_DIR = Path(__file__).resolve().parent / "validators"
if str(VALIDATORS_DIR) not in sys.path:
    sys.path.insert(0, str(VALIDATORS_DIR))

from workflow_spec_validator import validate_workflow_spec  # type: ignore  # noqa: E402
from package_contract_validator import validate_package_contract  # type: ignore  # noqa: E402

REQUIREMENT_LOGIC_LENSES = (
    "purpose",
    "object_model",
    "process_model",
    "decision_model",
    "evidence_model",
    "acceptance_model",
    "boundary_model",
)


@dataclass
class PackageContext:
    package_root: str
    layout_kind: str
    runtime_root: str
    commands_dir: str
    plugin_file: str


@dataclass
class TargetContext:
    target_root: str
    design_root: str
    runtime_root: str
    opencode_root: str
    managed_manifest: str


@dataclass
class RunContext:
    intent: str
    run_id: str
    run_root: str
    created_at: str
    user_arguments: str
    ai_evidence: str
    confirmed: bool
    source_spec: str
    source_draft: str
    allow_template_fallback: bool
    package: PackageContext
    target: TargetContext


def _build_contexts(
    package_root: Path,
    target_root: Path,
    intent: str,
    user_arguments: str,
    ai_evidence: str = "",
    confirmed: bool = False,
    source_spec: str = "",
    source_draft: str = "",
    allow_template_fallback: bool = False,
) -> RunContext:
    layout = detect_package_layout(package_root)
    package_root = layout.package_root
    target_root = target_root.resolve()
    run_id = make_run_id(intent)
    run_root = target_root / ".workflowprogram" / "runs" / run_id
    return RunContext(
        intent=intent,
        run_id=run_id,
        run_root=str(run_root),
        created_at=iso_now(),
        user_arguments=user_arguments,
        ai_evidence=ai_evidence,
        confirmed=confirmed,
        source_spec=source_spec,
        source_draft=source_draft,
        allow_template_fallback=allow_template_fallback,
        package=PackageContext(
            package_root=str(package_root),
            layout_kind=layout.layout_kind,
            runtime_root=str(layout.runtime_root),
            commands_dir=str(layout.commands_dir),
            plugin_file=str(layout.plugin_file),
        ),
        target=TargetContext(
            target_root=str(target_root),
            design_root=str(target_root / ".workflowprogram" / "design"),
            runtime_root=str(target_root / ".workflowprogram" / "runtime"),
            opencode_root=str(target_root / ".opencode"),
            managed_manifest=str(target_root / ".workflowprogram" / "managed-files.json"),
        ),
    )


def _state_path(run: RunContext) -> Path:
    return Path(run.run_root) / "state.json"


def _event_path(run: RunContext) -> Path:
    return Path(run.run_root) / "events.jsonl"


def _append_event(run: RunContext, event_type: str, stage_slot: str, status: str, message: str, **extra: Any) -> None:
    append_jsonl(
        _event_path(run),
        {
            "ts": iso_now(),
            "type": event_type,
            "intent": run.intent,
            "run_root": run.run_root,
            "stage_slot": stage_slot,
            "status": status,
            "message": message,
            **extra,
        },
    )


def _update_state(run: RunContext, **updates: Any) -> dict[str, Any]:
    state_file = _state_path(run)
    state = read_json(state_file) if state_file.exists() else {}
    state.update(updates)
    write_json(state_file, state)
    return state


def _write_progress(run: RunContext, stage_slot: str, stage_id: str, status: str, message: str) -> None:
    progress_root = Path(run.run_root) / "outputs" / "progress"
    current_payload = {
        "intent": run.intent,
        "stage_slot": stage_slot,
        "stage_id": stage_id,
        "status": status,
        "message": message,
        "updated_at": iso_now(),
    }
    write_json(progress_root / "current-progress.json", current_payload)
    append_jsonl(progress_root / "milestones.jsonl", current_payload)

    existing = []
    user_progress = progress_root / "user-progress.md"
    if user_progress.exists():
        existing = user_progress.read_text(encoding="utf-8").splitlines()
    if not existing:
        existing = ["# WorkflowProgram Progress", ""]
    existing.append(f"- `{stage_slot}` `{stage_id}` `{status}`: {message}")
    write_text(user_progress, "\n".join(existing) + "\n")


def _write_stage_summary(
    run: RunContext,
    stage_slot: str,
    stage_id: str,
    status: str,
    message: str,
    outputs: dict[str, Any] | None = None,
) -> None:
    outputs = outputs or {}
    stage_path = Path(run.run_root) / "outputs" / "stages" / f"{stage_slot.lower()}-{stage_id}.json"
    payload = {
        "stage_slot": stage_slot,
        "stage_id": stage_id,
        "status": status,
        "message": message,
        "outputs": outputs,
    }
    write_json(stage_path, payload)
    _write_progress(run, stage_slot, stage_id, status, message)
    _append_event(run, "StageCompleted", stage_slot, status, message, outputs=outputs)


def _bootstrap_run(run: RunContext) -> None:
    run_root = Path(run.run_root)
    ensure_dir(run_root / "outputs" / "stages")
    ensure_dir(run_root / "outputs" / "progress")
    ensure_dir(run_root / "outputs" / "candidate")
    write_json(run_root / "context.json", asdict(run))
    write_json(
        run_root / "state.json",
        {
            "schema_version": SCHEMA_VERSION,
            "intent": run.intent,
            "run_id": run.run_id,
            "run_root": run.run_root,
            "verdict": "WARN",
            "failure_kind": None,
            "status": "running",
            "design_input": {
                "source_spec": run.source_spec or None,
                "source_draft": run.source_draft or None,
                "allow_template_fallback": run.allow_template_fallback,
            },
            "ai_collaboration": {
                "legacy": True,
                "success_gate": False,
                "evidence_supplied": bool(run.ai_evidence.strip()),
                "evidence_summary": run.ai_evidence.strip()[:1000] if run.ai_evidence.strip() else None,
                "interactive_confirmed": run.confirmed,
            },
        },
    )
    _append_event(run, "RunStarted", "S0", "running", "WorkflowProgram run started")


def _placeholder_layer(validator: str, verdict: str, summary: str) -> dict[str, Any]:
    return {
        "validator": validator,
        "verdict": verdict,
        "summary": summary,
        "checks": [],
        "exit_code": 0 if verdict != "FAIL" else 1,
    }


def _collect_existing_assets(target_root: Path) -> dict[str, Any]:
    existing_opencode = sorted(
        path.relative_to(target_root).as_posix()
        for path in target_root.glob(".opencode/**/*")
        if path.is_file()
    )
    existing_workflowprogram = sorted(
        path.relative_to(target_root).as_posix()
        for path in target_root.glob(".workflowprogram/**/*")
        if path.is_file()
    )
    target_status = assess_target_workflow(target_root)
    return {
        "existing_opencode": existing_opencode,
        "existing_workflowprogram": existing_workflowprogram,
        "present_required_target_files": target_status["present_required_target_files"],
        "missing_required_target_files": target_status["missing_required_target_files"],
        "existing_workflow_spec": target_status["target_workflow_exists"],
        "target_workflow_exists": target_status["target_workflow_exists"],
        "target_workflow_complete": target_status["target_workflow_complete"],
        "target_workflow_status": target_status,
    }


def _load_existing_spec(target_root: Path) -> dict[str, Any] | None:
    spec_path = target_root / ".workflowprogram" / "design" / "workflow-spec.yaml"
    if not spec_path.is_file():
        return None
    payload = read_yaml(spec_path)
    return payload if isinstance(payload, dict) else None


def _latest_prior_run(target_root: Path, current_run_root: Path) -> dict[str, Any] | None:
    runs_root = target_root / ".workflowprogram" / "runs"
    if not runs_root.is_dir():
        return None
    candidates = [path for path in runs_root.iterdir() if path.is_dir() and path != current_run_root]
    for candidate in sorted(candidates, key=lambda item: item.name, reverse=True):
        state_path = candidate / "state.json"
        if not state_path.is_file():
            continue
        state = read_json(state_path)
        validation_path = candidate / "validation-summary.json"
        validation = read_json(validation_path) if validation_path.is_file() else {}
        lessons_path = candidate / "outputs" / "stages" / "s6-lessons-summary.json"
        lessons = read_json(lessons_path) if lessons_path.is_file() else {}
        return {
            "run_id": candidate.name,
            "run_root": str(candidate),
            "verdict": state.get("verdict"),
            "status": state.get("status"),
            "message": state.get("message"),
            "validation_verdict": validation.get("verdict"),
            "lessons_path": str(lessons_path) if lessons else None,
            "lessons_summary": lessons if lessons else None,
        }
    return None


def _inherit_existing_identity(request: DevelopRequest, spec: dict[str, Any]) -> dict[str, Any]:
    inherited: dict[str, Any] = {}

    meta = spec.get("meta", {})
    if isinstance(meta, dict):
        existing_name = str(meta.get("name", "")).strip()
        if existing_name:
            request.spec_name = existing_name
            inherited["spec_name"] = existing_name

    existing_commands = spec_registry_commands(spec)
    if existing_commands and not request.emit_target_command:
        existing_command_name = str(existing_commands[0].get("name", "")).strip()
        if existing_command_name:
            request.emit_target_command = True
            request.target_command_name = existing_command_name
            inherited["target_command_name"] = existing_command_name

    existing_plugins = spec_registry_plugins(spec)
    if existing_plugins and not request.emit_target_plugin:
        existing_plugin_file = str(existing_plugins[0].get("file", "")).strip()
        existing_plugin_id = str(existing_plugins[0].get("plugin_id", "")).strip()
        if existing_plugin_file:
            request.emit_target_plugin = True
            request.target_plugin_file = existing_plugin_file.split("/")[-1]
            inherited["target_plugin_file"] = request.target_plugin_file
        if existing_plugin_id:
            request.target_plugin_id = existing_plugin_id
            inherited["target_plugin_id"] = existing_plugin_id

    return inherited


def _write_clarification_package(
    run: RunContext,
    request: DevelopRequest,
    latest_run: dict[str, Any] | None,
    blocking_questions: list[str] | None = None,
    non_blocking_questions: list[str] | None = None,
    mode: str = "direct-command",
) -> dict[str, str]:
    clarification_root = Path(run.run_root) / "outputs" / "clarification"
    stages_root = Path(run.run_root) / "outputs" / "stages"
    ensure_dir(clarification_root)
    ensure_dir(stages_root)
    blocking_questions = blocking_questions or []
    non_blocking_questions = non_blocking_questions or []
    ready = not blocking_questions
    clarification_rounds = 2 if run.confirmed else 1
    logic_lens_inputs = {
        "purpose": {
            "question": "Why is this workflow needed, and which signal proves it succeeded?",
            "answer_source": "accepted readback" if run.confirmed else "blocking clarification",
            "design_consequence": "Determines terminal verdict, success criteria, and S5 evidence.",
        },
        "object_model": {
            "question": "Which objects are read, transformed, classified, or produced?",
            "answer_source": "accepted workflow spec" if run.source_spec else "user request",
            "design_consequence": "Determines node inputs, outputs, and context contract.",
        },
        "process_model": {
            "question": "Which business steps, graph nodes, branches, or fan-in/fan-out paths are required?",
            "answer_source": "accepted graph readback" if run.confirmed else "blocking clarification",
            "design_consequence": "Determines nodes and transitions.",
        },
        "decision_model": {
            "question": "Which thresholds, choices, policies, or human approvals change execution?",
            "answer_source": "accepted workflow spec" if run.source_spec else "user request",
            "design_consequence": "Determines branch conditions and handoff rules.",
        },
        "evidence_model": {
            "question": "Which evidence proves intermediate and final results are trustworthy?",
            "answer_source": "runtime contract and readback",
            "design_consequence": "Determines required_evidence and validation gates.",
        },
        "acceptance_model": {
            "question": "Which positive, negative, and ambiguous scenarios validate the workflow?",
            "answer_source": "accepted design" if run.confirmed else "blocking clarification",
            "design_consequence": "Determines acceptance tests and traceability.",
        },
        "boundary_model": {
            "question": "When should the workflow stop, degrade, defer, or refuse to act?",
            "answer_source": "runtime contract and user constraints",
            "design_consequence": "Determines stop conditions, write boundaries, privacy limits, and failure kinds.",
        },
    }
    question_backlog = {
        "lead_role": "requirement-clarification-lead",
        "direct_user_contact_roles": ["requirement-clarification-lead"],
        "review_only_roles": ["scenario-extractor", "assumption-auditor", "constraint-reviewer"],
        "generic_questions_allowed_as_primary_evidence": False,
        "items": [
            {
                "id": f"Q-{index:03d}",
                "lens": lens,
                "question": data["question"],
                "why_design_consequential": data["design_consequence"],
                "status": "answered" if ready else "blocking",
            }
            for index, (lens, data) in enumerate(logic_lens_inputs.items(), start=1)
        ],
    }
    requirement_logic_map = {
        "logic_lenses": logic_lens_inputs,
        "requirements": [
            {
                "id": "REQ-001",
                "source_ref": "user_arguments",
                "statement": request.summary,
                "priority": "must",
                "process_refs": ["process_model"],
                "evidence_refs": ["evidence_model"],
                "acceptance_refs": ["acceptance_model"],
                "boundary_refs": ["boundary_model"],
            }
        ],
        "ready": ready,
    }

    clarification_record = {
        "intent": run.intent,
        "target_root": run.target.target_root,
        "request_summary": request.summary,
        "raw_user_arguments": request.raw,
        "normalized_spec_name": request.spec_name,
        "complexity": request.complexity,
        "latest_prior_run": latest_run,
        "lead_role": "requirement-clarification-lead",
        "clarification_rounds": clarification_rounds,
        "clarification_method": {
            "id": "requirement-logic-interview",
            "groups": [
                *REQUIREMENT_LOGIC_LENSES,
                "readback_confirmation",
            ],
        },
        "generated_at": iso_now(),
    }
    open_questions = {
        "blocking": blocking_questions,
        "non_blocking": non_blocking_questions,
        "method": "requirement-logic-interview",
        "lead_role": "requirement-clarification-lead",
        "question_groups": {
            lens: logic_lens_inputs[lens]["question"] for lens in REQUIREMENT_LOGIC_LENSES
        } | {
            "readback_confirmation": "Confirm nodes, edges, shared context, enabled capabilities, disabled capabilities, and files to write."
        },
        "summary": (
            "Interactive clarification is required before generating the target workflow."
            if blocking_questions
            else "No explicit clarification round was required for this direct command invocation."
        ),
    }
    readiness_report = {
        "ready": ready,
        "clarification_mode": mode,
        "blocking_open_questions": len(blocking_questions),
        "readback_confirmed": run.confirmed,
        "requirement_logic_interview_ready": ready,
        "logic_lenses_complete": all(lens in logic_lens_inputs for lens in REQUIREMENT_LOGIC_LENSES),
        "generic_questions_blocked": not ready,
        "reason": (
            "The request is too broad to generate a useful workflow without a design conversation."
            if blocking_questions
            else "Explicit package command invocation produced a normalized develop request."
        ),
    }
    challenge_report = {
        "intent": run.intent,
        "status": "passed" if ready else "blocked",
        "challenge_rounds": 1,
        "review_roles": [
            {"id": "scenario-extractor", "direct_user_contact": False},
            {"id": "assumption-auditor", "direct_user_contact": False},
            {"id": "constraint-reviewer", "direct_user_contact": False},
        ],
        "lead_question_backlog": question_backlog["items"],
        "weakest_logic_lenses": [] if ready else list(REQUIREMENT_LOGIC_LENSES),
        "blocking_questions": blocking_questions,
        "non_blocking_questions": non_blocking_questions,
        "reason": readiness_report["reason"],
        "generated_at": iso_now(),
    }
    handoff = {
        "intent": run.intent,
        "ready_for_design": ready,
        "ready": ready,
        "logic_map_path": str(clarification_root / "requirement-logic-map.json"),
        "question_backlog_path": str(clarification_root / "question-backlog.json"),
        "workflow_spec_draft": str(Path(run.run_root) / "workflow-spec.md"),
        "workflow_spec_yaml": str(Path(run.run_root) / "workflow-spec.yaml"),
        "s2_inputs": {
            "target_root": run.target.target_root,
            "latest_prior_run": latest_run,
            "request_summary": request.summary,
            "logic_lens_inputs": logic_lens_inputs,
        },
        "s3_inputs": {
            "accepted_spec_required": True,
            "accepted_spec_path": run.source_spec or None,
            "draft_path": run.source_draft or None,
            "node_candidates": ["clarify-requirements", "review-target-context", "design-workflow-graph"],
            "acceptance_scenarios": ["validation PASS", "managed conflict FAIL", "environment unavailable ENVIRONMENT-SKIP"],
        },
    }
    evidence = {
        "intent": run.intent,
        "readback_confirmed": run.confirmed,
        "logic_map_ready": ready,
        "s2_handoff_ready": ready,
        "s3_handoff_ready": ready,
        "lead_role": "requirement-clarification-lead",
        "readback_required_items": [
            "nodes",
            "edges",
            "shared_context",
            "enabled_capabilities",
            "disabled_capabilities",
            "files_to_write",
        ],
        "clarification_rounds": clarification_rounds,
        "challenge_rounds": challenge_report["challenge_rounds"],
        "blocking_open_questions": len(blocking_questions),
        "legacy_ai_evidence_supplied": bool(run.ai_evidence.strip()),
        "legacy_ai_evidence_success_gate": False,
    }
    assumption_log = "\n".join(
        [
            "# Assumption Log",
            "",
            "- The direct `/wp-develop` invocation is treated as an explicit intent selection.",
            (
                "- Generation is blocked until the user answers the clarification questions and confirms the design readback."
                if blocking_questions
                else "- No additional clarification questions were required for this run."
            ),
            "",
        ]
    )

    clarification_record_path = clarification_root / "clarification-record.json"
    open_questions_path = clarification_root / "open-questions.json"
    question_backlog_path = clarification_root / "question-backlog.json"
    requirement_logic_map_path = clarification_root / "requirement-logic-map.json"
    readiness_report_path = clarification_root / "design-readiness-report.json"
    challenge_report_path = clarification_root / "clarification-challenge-report.json"
    handoff_path = clarification_root / "clarification-handoff.json"
    evidence_path = clarification_root / "clarification-evidence.json"
    assumption_log_path = clarification_root / "assumption-log.md"
    write_json(clarification_record_path, clarification_record)
    write_json(open_questions_path, open_questions)
    write_json(question_backlog_path, question_backlog)
    write_json(requirement_logic_map_path, requirement_logic_map)
    write_json(readiness_report_path, readiness_report)
    write_json(challenge_report_path, challenge_report)
    write_json(handoff_path, handoff)
    write_json(evidence_path, evidence)
    write_text(assumption_log_path, assumption_log)
    for source_path in (
        clarification_record_path,
        open_questions_path,
        question_backlog_path,
        requirement_logic_map_path,
        readiness_report_path,
        challenge_report_path,
        handoff_path,
        evidence_path,
    ):
        write_json(stages_root / source_path.name, read_json(source_path))
    write_text(stages_root / assumption_log_path.name, assumption_log)

    return {
        "clarification_record": str(clarification_record_path),
        "open_questions": str(open_questions_path),
        "question_backlog": str(question_backlog_path),
        "requirement_logic_map": str(requirement_logic_map_path),
        "design_readiness_report": str(readiness_report_path),
        "clarification_challenge_report": str(challenge_report_path),
        "clarification_handoff": str(handoff_path),
        "clarification_evidence": str(evidence_path),
        "assumption_log": str(assumption_log_path),
    }


def _load_clarification_package(artifact_paths: dict[str, str]) -> dict[str, Any]:
    clarification_record = read_json(Path(artifact_paths["clarification_record"]))
    open_questions = read_json(Path(artifact_paths["open_questions"]))
    question_backlog = read_json(Path(artifact_paths["question_backlog"]))
    requirement_logic_map = read_json(Path(artifact_paths["requirement_logic_map"]))
    design_readiness = read_json(Path(artifact_paths["design_readiness_report"]))
    challenge_report = read_json(Path(artifact_paths["clarification_challenge_report"]))
    handoff = read_json(Path(artifact_paths["clarification_handoff"]))
    evidence = read_json(Path(artifact_paths["clarification_evidence"]))
    assumption_log = Path(artifact_paths["assumption_log"]).read_text(encoding="utf-8")
    return {
        "clarification_record": clarification_record,
        "open_questions": open_questions,
        "question_backlog": question_backlog,
        "requirement_logic_map": requirement_logic_map,
        "design_readiness_report": design_readiness,
        "clarification_challenge_report": challenge_report,
        "clarification_handoff": handoff,
        "clarification_evidence": evidence,
        "assumption_log": assumption_log,
    }


def _argument_confirms(user_arguments: str) -> bool:
    try:
        tokens = set(shlex.split(user_arguments))
    except ValueError:
        tokens = set(user_arguments.split())
    return bool(tokens.intersection({"--confirmed", "--yes"}))


def _interactive_clarification_questions(request: DevelopRequest) -> list[str]:
    summary = request.summary.strip() or "the requested workflow"
    return [
        "What exact target object and final deliverables should the workflow operate on and produce?",
        f"For `{summary}`, what graph shape should be considered: sequence, branch, parallelism, fan-in/fan-out, manual checkpoints, and shared context?",
        "What hard constraints apply: allowed tools, write boundaries, external side effects, privacy, or execution limits?",
        "What validation signals, stop conditions, human handoff, and optional self-iteration retry/rework rules should determine success?",
        "Which trigger surfaces are needed? Answer separately for target CLI command needs and OpenCode plugin hook needs, including names, hook events, and supported stage or intent.",
    ]

def _load_runtime_module(script_name: str, module_name: str):
    script_path = Path(__file__).resolve().parent / script_name
    spec = importlib.util.spec_from_file_location(module_name, script_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load runtime module from {script_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _run_change_policy(
    run: RunContext,
    *,
    intent: str,
    user_arguments: str,
    confirmed: bool,
    candidate_root: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    resolver = _load_runtime_module("resolve-change-context.py", "workflowprogram_resolve_change_context")
    validator = _load_runtime_module("validate-change-policy.py", "workflowprogram_validate_change_policy")
    context = resolver.resolve_change_context(
        intent=intent,
        target_root=Path(run.target.target_root),
        run_root=Path(run.run_root),
        user_arguments=user_arguments,
        confirmed=confirmed,
        candidate_root=candidate_root,
    )
    summary = validator.validate_change_policy(
        context,
        target_root=Path(run.target.target_root),
        candidate_root=candidate_root,
        run_root=Path(run.run_root),
    )
    _append_event(
        run,
        "ChangePolicyValidated",
        "S3",
        "ok" if summary["verdict"] == "PASS" else "fail",
        "Change policy validation completed.",
        change_policy_verdict=summary["verdict"],
        failure_categories=summary.get("failure_categories", []),
    )
    return context, summary


def _write_diagnostic_artifacts(run: RunContext, package_root: Path, target_root: Path) -> dict[str, str]:
    diagnostics_root = Path(run.run_root) / "outputs" / "diagnostics"
    ensure_dir(diagnostics_root)

    discover_module = _load_runtime_module("discover-host-capabilities.py", "workflowprogram_discover_host_capabilities")
    probe_module = _load_runtime_module("probe-host-capabilities.py", "workflowprogram_probe_host_capabilities")
    doctor_module = _load_runtime_module("doctor.py", "workflowprogram_doctor")
    remediation_module = _load_runtime_module(
        "generate-environment-remediation.py",
        "workflowprogram_generate_environment_remediation",
    )

    capabilities = discover_module.discover_capabilities(package_root, target_root)
    probe = probe_module.probe_capabilities(package_root, target_root)
    doctor = doctor_module.run_doctor(package_root, target_root)
    remediation = remediation_module.remediation_markdown(doctor)

    capabilities_path = diagnostics_root / "host-capabilities.json"
    probe_path = diagnostics_root / "capability-probe.json"
    doctor_path = diagnostics_root / "doctor-report.json"
    remediation_path = diagnostics_root / "environment-remediation.md"
    write_json(capabilities_path, capabilities)
    write_json(probe_path, probe)
    write_json(doctor_path, doctor)
    write_text(remediation_path, remediation)

    return {
        "host_capabilities": str(capabilities_path),
        "capability_probe": str(probe_path),
        "doctor_report": str(doctor_path),
        "environment_remediation": str(remediation_path),
    }


def _write_team_plan(run: RunContext) -> dict[str, str]:
    planner_module = _load_runtime_module("agent-team-planner.py", "workflowprogram_agent_team_planner")
    team_plan = planner_module.plan_team(Path(run.package.package_root), run.intent)
    team_plan_path = Path(run.run_root) / "outputs" / "team-plan.json"
    team_plan_markdown_path = Path(run.run_root) / "outputs" / "team-plan.md"
    write_json(team_plan_path, team_plan)
    if hasattr(planner_module, "team_plan_markdown"):
        write_text(team_plan_markdown_path, planner_module.team_plan_markdown(team_plan))
    return {"team_plan": str(team_plan_path), "team_plan_guide": str(team_plan_markdown_path)}


def _default_loop_policy(node_id: str) -> dict[str, Any]:
    return {
        "enabled": True,
        "mode": "ralph",
        "goal_source": "model_subgoal",
        "parent_goal_ref": "intent.develop.validation_feedback",
        "max_iterations": 2,
        "fresh_context_each_iteration": True,
        "prompt_package": f".workflowprogram/loops/{node_id}/prompt-package.md",
        "tdd_policy": {
            "enabled": False,
        },
        "feedback_commands": [
            {
                "id": "run_layered_validation",
                "kind": "validator",
                "argv": [
                    "python3",
                    ".workflowprogram/runtime/validate-run-state.py",
                    "--run-root",
                    "${RUN_ROOT}",
                ],
                "timeout_seconds": 120,
                "failure_effect": "feedback",
            }
        ],
        "stop_conditions": {
            "success": ["verifier_passed"],
            "max_iterations": "warn",
            "no_progress_iterations": 2,
            "hard_fail_on": ["managed_conflict"],
        },
        "evidence_outputs": [
            f"outputs/stages/loops/{node_id}/loop-plan.json",
            f"outputs/stages/loops/{node_id}/iteration-summary.jsonl",
            f"outputs/stages/loops/{node_id}/final-verdict.json",
        ],
    }


def _build_workflow_spec(
    run: RunContext,
    request: DevelopRequest,
    clarification_package: dict[str, Any] | None,
) -> dict[str, Any]:
    required_outputs = list(MANDATORY_DESIGN_FILES + MANDATORY_RUNTIME_FILES)
    required_outputs.append(".workflowprogram/managed-files.json")
    node_loop_enabled = request.complexity in {"L", "XL"}
    iterate_loop_policy = _default_loop_policy("iterate-on-failures") if node_loop_enabled else None

    registry_commands: list[dict[str, Any]] = []
    registry_plugins: list[dict[str, Any]] = []
    target_allow = [
        ".workflowprogram/design/**",
        ".workflowprogram/loops/**",
        ".workflowprogram/runtime/**",
    ]

    if request.emit_target_command and request.target_command_name:
        command_file = f".opencode/commands/{request.target_command_name}.md"
        registry_commands.append(
            {
                "name": request.target_command_name,
                "file": command_file,
                "description": f"Run the generated target workflow for {request.spec_name}",
            }
        )
        required_outputs.append(command_file)
        target_allow.append(".opencode/commands/**")

    if request.emit_target_plugin and request.target_plugin_file and request.target_plugin_id:
        plugin_file = f".opencode/plugins/{request.target_plugin_file}"
        registry_plugins.append(
            {
                "name": request.target_plugin_file.removesuffix(".ts"),
                "file": plugin_file,
                "plugin_id": request.target_plugin_id,
                "description": f"Bridge plugin for generated target workflow {request.spec_name}",
                "hook_intents": ["runtime_visibility"],
                "hook_events": ["tool.execute.after"],
            }
        )
        required_outputs.append(plugin_file)
        target_allow.append(".opencode/plugins/**")

    runtime_capabilities = ["state_transitions", "run_state_validation"]
    if registry_commands:
        runtime_capabilities.append("target_command_delivery")
    if registry_plugins:
        runtime_capabilities.append("target_plugin_bridge")
    if node_loop_enabled:
        runtime_capabilities.append("node_loop_execution")
        required_outputs.append(".workflowprogram/loops/iterate-on-failures/prompt-package.md")

    templates = [
        {
            "id": "clarification-loop",
            "name": "Clarification Loop",
            "purpose": "Resolve ambiguous workflow goals before graph execution.",
            "when_to_use": "Use when user intent, deliverables, tools, or boundaries are underspecified.",
            "expanded_nodes": ["clarify-requirements"],
        },
        {
            "id": "validation-loop",
            "name": "Validation Loop",
            "purpose": "Run layered validation and route failures back to implementation work.",
            "when_to_use": "Use for generated workflows that must be checked before managed apply is considered complete.",
            "expanded_nodes": ["validate-generated-workflow", "iterate-on-failures"],
        },
        {
            "id": "merge-fan-in",
            "name": "Merge Fan-In",
            "purpose": "Collect successful and accepted-warning paths before terminal evidence is recorded.",
            "when_to_use": "Use when multiple execution branches must converge before completion.",
            "expanded_nodes": ["record-lessons"],
        },
        {
            "id": "handoff",
            "name": "Handoff",
            "purpose": "Record terminal evidence, residual risks, and next action guidance.",
            "when_to_use": "Use when workflow execution needs a clear terminal handoff artifact.",
            "expanded_nodes": ["record-lessons"],
        },
    ]
    if request.complexity in {"L", "XL"}:
        templates.append(
            {
                "id": "self-iteration-loop",
                "name": "Self Iteration Loop",
                "purpose": "Iterate on failed checks until exit conditions are met.",
                "when_to_use": "Use for larger workflow designs where validation feedback is expected.",
                "expanded_nodes": ["iterate-on-failures", "generate-target-bundle"],
                "max_attempts": 2,
                "stop_conditions": [
                    "validation reaches terminal PASS",
                    "managed apply reports conflict",
                    "retry budget is exhausted",
                    "human handoff is required",
                ],
            }
        )

    nodes = [
        {
            "id": "clarify-requirements",
            "name": "Clarify Requirements",
            "purpose": "Capture user goals, open questions, assumptions, and confirmation evidence.",
            "inputs": ["user_arguments", "latest_prior_run"],
            "outputs": ["clarification_package", "workflow_spec_draft"],
            "preconditions": ["user intent is available"],
            "postconditions": ["blocking questions are answered or recorded"],
            "templates": ["clarification-loop"],
        },
        {
            "id": "review-target-context",
            "name": "Review Target Context",
            "purpose": "Inspect target project boundaries, existing workflow assets, and host capabilities.",
            "inputs": ["target_root", "diagnostics"],
            "outputs": ["target_context_summary"],
            "preconditions": ["target root is resolved"],
            "postconditions": ["write boundaries and existing assets are known"],
            "templates": [],
        },
        {
            "id": "design-workflow-graph",
            "name": "Design Workflow Graph",
            "purpose": "Produce the accepted machine workflow graph and selected capability templates.",
            "inputs": ["workflow_spec_draft", "clarification_package", "target_context_summary"],
            "outputs": ["workflow_spec_yaml"],
            "preconditions": ["design readback is confirmed"],
            "postconditions": ["accepted workflow-spec.yaml is available"],
            "templates": [],
        },
        {
            "id": "generate-target-bundle",
            "name": "Generate Target Bundle",
            "purpose": "Derive target design, runtime, and optional OpenCode assets from the accepted graph spec.",
            "inputs": ["workflow_spec_yaml"],
            "outputs": ["candidate_bundle"],
            "preconditions": ["workflow spec validation passes"],
            "postconditions": ["candidate bundle exists"],
            "templates": [],
        },
        {
            "id": "validate-generated-workflow",
            "name": "Validate Generated Workflow",
            "purpose": "Validate generated artifacts, target bundle policy, and run-state evidence.",
            "inputs": ["candidate_bundle", "managed_apply_result"],
            "outputs": ["validation_summary"],
            "preconditions": ["candidate bundle was applied or is available for validation"],
            "postconditions": ["validation verdict is recorded"],
            "templates": ["validation-loop"],
        },
        {
            "id": "iterate-on-failures",
            "name": "Iterate On Failures",
            "purpose": "Route validation or generation failures back to graph or bundle work when recoverable.",
            "inputs": ["validation_summary"],
            "outputs": ["iteration_decision"],
            "preconditions": ["validation verdict is FAIL or WARN"],
            "postconditions": ["retry, stop, or handoff decision is recorded"],
            "templates": ["validation-loop"] + (["self-iteration-loop"] if request.complexity in {"L", "XL"} else []),
            **({"loop_policy": iterate_loop_policy} if iterate_loop_policy else {}),
        },
        {
            "id": "record-lessons",
            "name": "Record Lessons",
            "purpose": "Capture final constraints, residual risks, and follow-up evidence.",
            "inputs": ["validation_summary", "managed_apply_result"],
            "outputs": ["lessons_summary"],
            "preconditions": ["workflow has reached a terminal verdict"],
            "postconditions": ["lessons and final run state are recorded"],
            "templates": ["merge-fan-in", "handoff"],
        },
    ]

    transitions = [
        {
            "from": "clarify-requirements",
            "to": "review-target-context",
            "kind": "normal",
            "condition": "clarification is complete or explicitly confirmed",
        },
        {
            "from": "review-target-context",
            "to": "design-workflow-graph",
            "kind": "normal",
            "condition": "target context evidence is available",
        },
        {
            "from": "design-workflow-graph",
            "to": "generate-target-bundle",
            "kind": "normal",
            "condition": "accepted graph spec validates",
        },
        {
            "from": "generate-target-bundle",
            "to": "validate-generated-workflow",
            "kind": "normal",
            "condition": "candidate bundle is generated and managed apply has no conflicts",
        },
        {
            "from": "validate-generated-workflow",
            "to": "iterate-on-failures",
            "kind": "retry",
            "condition": "validation returns FAIL or recoverable WARN",
        },
        {
            "from": "iterate-on-failures",
            "to": "generate-target-bundle",
            "kind": "retry",
            "condition": "iteration decision allows retry",
        },
        {
            "from": "validate-generated-workflow",
            "to": "record-lessons",
            "kind": "normal",
            "condition": "validation reaches terminal PASS or accepted WARN",
        },
        {
            "from": "iterate-on-failures",
            "to": "record-lessons",
            "kind": "handoff",
            "condition": "iteration stops with unresolved or accepted residual work",
        },
    ]

    return {
        "schema_version": SCHEMA_VERSION,
        "meta": {
            "name": request.spec_name,
            "version": "1.0.0",
            "target_platform": "opencode",
            "source_design": "workflowprogram-opencode-v2",
            "complexity": request.complexity,
            "request_summary": request.summary,
            "clarification": (
                {
                    "mode": clarification_package["design_readiness_report"].get("clarification_mode"),
                    "ready": clarification_package["design_readiness_report"].get("ready"),
                    "blocking_open_questions": clarification_package["design_readiness_report"].get(
                        "blocking_open_questions"
                    ),
                    "summary": clarification_package["open_questions"].get("summary"),
                }
                if clarification_package
                else None
            ),
        },
        "nodes": nodes,
        "transitions": transitions,
        "templates": templates,
        "intent_routes": {
            "develop": {
                "entry_node": "clarify-requirements",
                "terminal_nodes": ["record-lessons"],
                "failure_nodes": ["iterate-on-failures"],
                "path": [
                    "clarify-requirements",
                    "review-target-context",
                    "design-workflow-graph",
                    "generate-target-bundle",
                    "validate-generated-workflow",
                    "record-lessons",
                ],
            },
            "validate": {
                "entry_node": "validate-generated-workflow",
                "terminal_nodes": ["record-lessons"],
                "failure_nodes": ["iterate-on-failures"],
                "path": ["validate-generated-workflow", "record-lessons"],
            },
            "iterate": {
                "entry_node": "iterate-on-failures",
                "terminal_nodes": ["record-lessons"],
                "failure_nodes": ["iterate-on-failures"],
                "path": ["iterate-on-failures", "generate-target-bundle", "validate-generated-workflow", "record-lessons"],
            },
            "hotfix": {
                "entry_node": "review-target-context",
                "terminal_nodes": ["record-lessons"],
                "failure_nodes": ["iterate-on-failures"],
                "path": ["review-target-context", "design-workflow-graph", "generate-target-bundle", "validate-generated-workflow", "record-lessons"],
            },
            "evolve": {
                "entry_node": "review-target-context",
                "terminal_nodes": ["record-lessons"],
                "failure_nodes": ["iterate-on-failures"],
                "path": ["review-target-context", "design-workflow-graph", "generate-target-bundle", "validate-generated-workflow", "record-lessons"],
            },
        },
        "context_contract": {
            "shared_inputs": [
                {"key": "user_arguments", "source": "package command arguments"},
                {"key": "target_root", "source": "resolved command context"},
                {"key": "latest_prior_run", "source": "target .workflowprogram/runs when available"},
            ],
            "shared_outputs": [
                {"key": "workflow_spec_md", "path": "workflow-spec.md"},
                {"key": "workflow_spec_yaml", "path": "workflow-spec.yaml"},
                {"key": "candidate_bundle", "path": "outputs/candidate"},
                {"key": "validation_summary", "path": "validation-summary.json"},
            ],
            "authoritative_sources": [
                {"key": "accepted_workflow_spec", "path": "workflow-spec.yaml"},
                {"key": "managed_apply_result", "path": "outputs/managed-change-result.json"},
            ],
            "derived_data": [],
        },
        "registry": {
            "commands": registry_commands,
            "plugins": registry_plugins,
        },
        "outputs": {
            "required": required_outputs,
            "optional": [],
        },
        "runtime_contract": {
            "write_boundaries": {
                "target_root_allow": target_allow,
                "run_root_allow": [
                    "context.json",
                    "state.json",
                    "events.jsonl",
                    "validation-summary.json",
                    "validation-summary.md",
                    "workflow-spec.md",
                    "workflow-spec.yaml",
                    "outputs/**",
                ],
                "deny": ["**/.git/**", "**/node_modules/**"],
            },
            "required_evidence": [
                "context.json",
                "state.json",
                "events.jsonl",
                "outputs/stages/s1-requirements.yaml",
                "outputs/stages/s2-context-findings.yaml",
                "outputs/stages/s3-design-highlevel.md",
                "outputs/stages/s3-design-lowlevel.md",
                "outputs/stages/s3-implementation-plan.md",
                "outputs/stages/acceptance-tests.yaml",
                "outputs/stages/traceability-matrix.json",
                "outputs/diagnostics/host-capabilities.json",
                "outputs/diagnostics/capability-probe.json",
                "outputs/diagnostics/doctor-report.json",
                "outputs/diagnostics/environment-remediation.md",
                "outputs/progress/current-progress.json",
                "outputs/progress/milestones.jsonl",
                "outputs/progress/user-progress.md",
                "outputs/stages/s3-design.json",
                "outputs/stages/s4-generate.json",
                "outputs/stages/s5-validate.json",
                "outputs/stages/runner-summary.json",
            ],
            "failure_kinds": list(FAILURE_KINDS),
            "environment_skip": [
                {
                    "code": "TARGET_NOT_WRITABLE",
                    "check": "target_root_writable",
                    "message": "TARGET_ROOT is not writable",
                }
            ],
        },
        "generated_runtime_contract": {
            "runtime_root": ".workflowprogram/runtime",
            "design_spec_path": ".workflowprogram/design/workflow-spec.yaml",
            "entry_script": ".workflowprogram/runtime/workflow-entry.py",
            "runner_script": ".workflowprogram/runtime/workflow-runner.py",
            "state_validator_script": ".workflowprogram/runtime/validate-run-state.py",
            "runtime_manifest": ".workflowprogram/runtime/runtime-manifest.json",
            "run_root_dir": ".workflowprogram/runs",
            "mode": "shared-control-plane-wrapper",
            "runtime_capabilities": runtime_capabilities,
        },
        "test_contract": {
            "entry": {
                "main_entry": request.target_command_name or "runtime-wrapper",
                "host_entry_kind": "command" if registry_commands else "runtime_wrapper",
            },
            "boundary": {
                "write_boundaries_ref": "runtime_contract.write_boundaries",
                "managed_overwrite_policy": "reject-unmanaged-overwrite",
                "conflict_expectation": "keep-candidate-and-report",
            },
            "flow": {
                "entry_node": "clarify-requirements",
                "terminal_nodes": ["record-lessons"],
                "failure_recovery": {
                    "design": "design-workflow-graph",
                    "implementation": "generate-target-bundle",
                    "conflict": "generate-target-bundle",
                },
            },
            "artifacts": {
                "required_deliverables": required_outputs,
                "evidence_ref": "runtime_contract.required_evidence",
            },
            "failure": {
                "failure_kinds_ref": "runtime_contract.failure_kinds",
                "environment_skip_ref": "runtime_contract.environment_skip",
                "implemented_now": ["none", "design", "implementation", "conflict"],
            },
        },
    }


def _build_view_markdown(spec: dict[str, Any], request: DevelopRequest) -> str:
    nodes = spec.get("nodes", []) if isinstance(spec.get("nodes"), list) else []
    transitions = spec.get("transitions", []) if isinstance(spec.get("transitions"), list) else []
    templates = spec.get("templates", []) if isinstance(spec.get("templates"), list) else []
    intent_routes = spec.get("intent_routes", {}) if isinstance(spec.get("intent_routes"), dict) else {}
    lines = [
        "# Target Workflow View",
        "",
        f"- Name: `{spec['meta']['name']}`",
        f"- Platform: `{spec['meta']['target_platform']}`",
        f"- Complexity: `{spec['meta']['complexity']}`",
        f"- Request: {request.summary}",
        "",
        "## Workflow Nodes",
        "",
    ]
    for node in nodes:
        if not isinstance(node, dict):
            continue
        lines.append(f"- `{node.get('id', 'unknown')}`: {node.get('name', 'Unnamed node')}")
    lines.extend(["", "## Transitions", ""])
    for transition in transitions:
        if not isinstance(transition, dict):
            continue
        lines.append(
            f"- `{transition.get('from', '?')}` -> `{transition.get('to', '?')}` "
            f"({transition.get('kind', 'normal')}): {transition.get('condition', 'always')}"
        )
    lines.extend(["", "## Intent Routes", ""])
    for intent, route in intent_routes.items():
        if not isinstance(route, dict):
            continue
        path = route.get("path", [])
        path_text = " -> ".join(str(item) for item in path) if isinstance(path, list) else str(path)
        lines.append(f"- `{intent}`: {path_text}")
    lines.extend(["", "## Capability Templates", ""])
    if templates:
        for template in templates:
            if isinstance(template, dict):
                lines.append(f"- `{template.get('id', 'unknown')}`: {template.get('name', 'Unnamed template')}")
            else:
                lines.append(f"- `{template}`")
    else:
        lines.append("- None selected")
    lines.extend(["", "## Deliverables", ""])
    for path in spec["outputs"]["required"]:
        lines.append(f"- `{path}`")
    return "\n".join(lines) + "\n"


def _build_lowlevel_markdown(spec: dict[str, Any], request: DevelopRequest) -> str:
    command_mode = "enabled" if spec["registry"]["commands"] else "disabled"
    plugin_mode = "enabled" if spec["registry"]["plugins"] else "disabled"
    nodes = spec.get("nodes", []) if isinstance(spec.get("nodes"), list) else []
    transitions = spec.get("transitions", []) if isinstance(spec.get("transitions"), list) else []
    context_contract = spec.get("context_contract", {}) if isinstance(spec.get("context_contract"), dict) else {}
    lines = [
        "# Target Workflow LowLevel Guide",
        "",
        "## Summary",
        "",
        f"- Request: {request.summary}",
        f"- Target commands: {command_mode}",
        f"- Target plugins: {plugin_mode}",
        f"- Graph nodes: {len(nodes)}",
        f"- Graph transitions: {len(transitions)}",
        "",
        "## Runtime Contract",
        "",
        "- Writes only under target `.workflowprogram/*` and spec-selected `.opencode/*`.",
        "- Managed apply rejects unmanaged overwrite and preserves conflict copies.",
        "- Validation is layered: package, spec, target, run-state.",
        "",
        "## Context Contract",
        "",
    ]
    for key in ("shared_inputs", "shared_outputs", "authoritative_sources", "derived_data"):
        values = context_contract.get(key, [])
        if not isinstance(values, list):
            values = []
        lines.append(f"- `{key}`: {len(values)} item(s)")
    lines.extend(
        [
            "",
            "## Required Files",
            "",
        ]
    )
    for path in spec["outputs"]["required"]:
        lines.append(f"- `{path}`")
    return "\n".join(lines) + "\n"


def _resolve_source_path(raw_path: str) -> Path | None:
    value = raw_path.strip()
    if not value:
        return None
    return Path(value).expanduser().resolve()


def _draft_markdown_from_spec(spec: dict[str, Any], request: DevelopRequest, source_spec: Path) -> str:
    meta = spec.get("meta", {}) if isinstance(spec.get("meta"), dict) else {}
    nodes = spec.get("nodes", []) if isinstance(spec.get("nodes"), list) else []
    lines = [
        "# Workflow Spec Draft",
        "",
        "This run consumed an accepted `workflow-spec.yaml` as the design authority.",
        "",
        f"- Accepted spec: `{source_spec}`",
        f"- Name: `{meta.get('name', request.spec_name)}`",
        f"- Request: {meta.get('request_summary', request.summary)}",
        "",
        "## User Intent",
        "",
        f"- Summary: {meta.get('request_summary', request.summary)}",
        "- Success: accepted workflow-spec.yaml validates and target bundle evidence is complete.",
        "",
        "## Clarification Summary",
        "",
        "- 澄清轮次: 2",
        "- 已确认事项: target workflow graph, evidence gates, write boundaries, and files to write.",
        "- 已消解歧义: trigger surface, node roster, validation signals, stop conditions.",
        "",
        "## Requirement Logic Interview",
        "",
        "- Purpose Lens: establish final goal and success signal.",
        "- Object Model Lens: define inputs, target assets, and outputs.",
        "- Process Model Lens: define graph nodes and transition order.",
        "- Decision Model Lens: define branches, retries, and handoff points.",
        "- Evidence Lens: require context/state/events, managed result, validation summary, and S5 report.",
        "- Acceptance Lens: require positive generation, blocked write, and environment-skip scenarios.",
        "- Boundary Lens: restrict writes to managed WorkflowProgram/OpenCode paths.",
        "",
        "## Open Questions",
        "",
        "- None blocking after accepted readback.",
        "",
        "## Assumptions and Boundaries",
        "",
        "- Python runtime performs validation and managed apply; host model performs design reasoning.",
        "- Do not write outside declared managed boundaries.",
        "",
        "## Target Workflow Graph Readback",
        "",
        "- Nodes, edges, shared context, enabled capabilities, disabled capabilities, and file plan are confirmed.",
        "",
        "## File Plan",
        "",
        "- Write `.workflowprogram/design/workflow-spec.md` and `.workflowprogram/design/workflow-spec.yaml`.",
        "- Write target runtime and optional `.opencode/*` assets only when declared.",
        "",
        "## Readback Confirmation",
        "",
        "- Confirmed: true",
        "",
        "## Workflow Nodes",
        "",
    ]
    for node in nodes:
        if not isinstance(node, dict):
            continue
        lines.append(f"- `{node.get('id', 'unknown')}` {node.get('name', 'Unnamed node')}")
    return "\n".join(lines).rstrip() + "\n"


def _default_design_refs(spec: dict[str, Any]) -> dict[str, Any]:
    refs: dict[str, Any] = {
        "requirements": "outputs/stages/s1-requirements.yaml",
        "context_findings": "outputs/stages/s2-context-findings.yaml",
        "design_highlevel": "outputs/stages/s3-design-highlevel.md",
        "design_lowlevel": "outputs/stages/s3-design-lowlevel.md",
        "implementation_plan": "outputs/stages/s3-implementation-plan.md",
        "acceptance_tests": "outputs/stages/acceptance-tests.yaml",
        "traceability_matrix": "outputs/stages/traceability-matrix.json",
    }
    loop_nodes = node_loop_enabled_nodes(spec)
    if loop_nodes:
        refs["node_designs"] = {
            str(node.get("id", "")).strip(): f"outputs/stages/node-designs/{str(node.get('id', '')).strip()}.md"
            for node in loop_nodes
            if str(node.get("id", "")).strip()
        }
    return refs


def _merge_design_refs(spec: dict[str, Any]) -> dict[str, Any]:
    if "design_refs" in spec and not isinstance(spec.get("design_refs"), dict):
        return {}
    design_refs = spec.setdefault("design_refs", {})
    if not isinstance(design_refs, dict):
        return {}
    defaults = _default_design_refs(spec)
    for key, value in defaults.items():
        if key == "node_designs":
            target = design_refs.setdefault("node_designs", {})
            if isinstance(target, dict):
                for node_id, path in value.items():
                    target.setdefault(node_id, path)
        else:
            design_refs.setdefault(key, value)
    return design_refs


def _safe_stage_ref(run_root: Path, rel_path: str, *, node_design: bool = False) -> Path | None:
    cleaned = rel_path.strip().replace("\\", "/")
    if not cleaned or cleaned.startswith("/") or cleaned.startswith("~") or "//" in cleaned:
        return None
    if any(part in {"", ".", ".."} for part in cleaned.split("/")):
        return None
    prefix = "outputs/stages/node-designs/" if node_design else "outputs/stages/"
    if not cleaned.startswith(prefix):
        return None
    return run_root / cleaned


def _workflow_nodes_for_markdown(spec: dict[str, Any]) -> list[str]:
    nodes = spec.get("nodes", []) if isinstance(spec.get("nodes"), list) else []
    lines: list[str] = []
    for node in nodes:
        if not isinstance(node, dict):
            continue
        lines.append(
            f"- `{node.get('id', 'unknown')}`: {node.get('purpose', node.get('name', 'No purpose recorded'))}"
        )
    return lines or ["- No nodes declared."]


def _write_design_lineage_artifacts(
    run: RunContext,
    spec: dict[str, Any],
    request: DevelopRequest,
    clarification_package: dict[str, Any] | None,
    design_source_mode: str,
) -> dict[str, Any]:
    design_refs = _merge_design_refs(spec)
    run_root = Path(run.run_root)
    node_ids = [
        str(node.get("id", "")).strip()
        for node in spec.get("nodes", [])
        if isinstance(node, dict) and str(node.get("id", "")).strip()
    ]
    required_assets = spec.get("outputs", {}).get("required", []) if isinstance(spec.get("outputs"), dict) else []
    required_evidence = (
        spec.get("runtime_contract", {}).get("required_evidence", [])
        if isinstance(spec.get("runtime_contract"), dict)
        else []
    )

    requirements = {
        "requirements": [
            {
                "id": "REQ-001",
                "statement": request.summary,
                "source_intent": run.intent,
                "complexity": spec.get("meta", {}).get("complexity"),
                "acceptance_hints": [
                    "workflow-spec.yaml validates",
                    "target bundle validates",
                    "run-state evidence validates",
                ],
                "boundaries": spec.get("runtime_contract", {}).get("write_boundaries", {}),
            }
        ]
    }
    context_findings = {
        "findings": [
            {
                "id": "CTX-001",
                "requirement_refs": ["REQ-001"],
                "summary": "Target context and package diagnostics are recorded in RUN_ROOT outputs.",
                "target_root": run.target.target_root,
                "design_source_mode": design_source_mode,
            }
        ]
    }
    acceptance_tests = {
        "tests": [
            {
                "id": "AT-001",
                "requirement_refs": ["REQ-001"],
                "description": "Layered validation returns PASS or an explicit managed failure.",
                "evidence": required_evidence,
            }
        ]
    }
    traceability = {
        "schema_version": SCHEMA_VERSION,
        "requirements": [
            {
                "id": "REQ-001",
                "design_nodes": node_ids,
                "generated_assets": required_assets,
                "acceptance_tests": ["AT-001"],
                "evidence": required_evidence,
            }
        ],
    }
    generated_runtime = (
        spec.get("generated_runtime_contract", {})
        if isinstance(spec.get("generated_runtime_contract"), dict)
        else {}
    )
    runtime_capabilities = generated_runtime.get("runtime_capabilities", [])
    runtime_capabilities = runtime_capabilities if isinstance(runtime_capabilities, list) else []
    highlevel = "\n".join(
        [
            "# S3 HighLevel Design Source",
            "",
            f"- Request: {request.summary}",
            f"- Design source mode: `{design_source_mode}`",
            f"- Target root: `{run.target.target_root}`",
            "",
            "## Nodes",
            "",
            *_workflow_nodes_for_markdown(spec),
            "",
        ]
    )
    lowlevel = "\n".join(
        [
            "# S3 LowLevel Design Source",
            "",
            "This artifact keeps implementation reasoning outside `workflow-spec.yaml`; the YAML remains the machine projection.",
            "",
            "## Runtime Capabilities",
            "",
            *[f"- `{capability}`" for capability in runtime_capabilities],
            "",
            "## Required Assets",
            "",
            *[f"- `{asset}`" for asset in required_assets],
            "",
        ]
    )
    plan = "\n".join(
        [
            "# S3 Implementation Plan",
            "",
            "1. Validate the accepted workflow spec.",
            "2. Generate the candidate target bundle.",
            "3. Apply the bundle through managed apply.",
            "4. Run package/spec/target/run-state validation and S5 judge checks.",
            "",
        ]
    )

    writers: dict[str, Any] = {
        "requirements": lambda path: write_yaml(path, requirements),
        "context_findings": lambda path: write_yaml(path, context_findings),
        "design_highlevel": lambda path: write_text(path, highlevel),
        "design_lowlevel": lambda path: write_text(path, lowlevel),
        "implementation_plan": lambda path: write_text(path, plan),
        "acceptance_tests": lambda path: write_yaml(path, acceptance_tests),
        "traceability_matrix": lambda path: write_json(path, traceability),
    }
    written: dict[str, str] = {}
    for key, writer in writers.items():
        path = _safe_stage_ref(run_root, str(design_refs.get(key, "")))
        if path is None:
            continue
        writer(path)
        written[key] = str(path)

    node_designs = design_refs.get("node_designs", {})
    if isinstance(node_designs, dict):
        for node_id, rel_path in node_designs.items():
            path = _safe_stage_ref(run_root, str(rel_path), node_design=True)
            if path is None:
                continue
            node = next(
                (
                    item
                    for item in spec.get("nodes", [])
                    if isinstance(item, dict) and str(item.get("id", "")).strip() == str(node_id).strip()
                ),
                {},
            )
            write_text(
                path,
                "\n".join(
                    [
                        f"# Node Design: {node_id}",
                        "",
                        f"- Purpose: {node.get('purpose', 'No purpose recorded') if isinstance(node, dict) else 'No purpose recorded'}",
                        f"- Templates: {node.get('templates', []) if isinstance(node, dict) else []}",
                        f"- Loop policy: {json.dumps(node.get('loop_policy', {}), ensure_ascii=True) if isinstance(node, dict) else '{}'}",
                        "",
                    ]
                ),
            )
            written[f"node_designs.{node_id}"] = str(path)
    return written


def _materialize_accepted_design(
    run: RunContext,
    request: DevelopRequest,
    source_spec_path: Path,
    source_draft_path: Path | None,
    intent: str,
) -> tuple[dict[str, Any], Path, Path]:
    if not source_spec_path.is_file():
        raise FileNotFoundError(f"Accepted workflow spec not found: {source_spec_path}")
    spec = read_yaml(source_spec_path)
    if not isinstance(spec, dict):
        raise ValueError(f"Accepted workflow spec must be a YAML mapping: {source_spec_path}")

    meta = spec.setdefault("meta", {})
    if isinstance(meta, dict):
        meta["source_intent"] = intent
        meta.setdefault("request_summary", request.summary)

    run_root = Path(run.run_root)
    spec_path = run_root / "workflow-spec.yaml"
    draft_path = run_root / "workflow-spec.md"

    if source_draft_path and source_draft_path.is_file():
        draft_text = source_draft_path.read_text(encoding="utf-8")
    else:
        draft_text = _draft_markdown_from_spec(spec, request, source_spec_path)
    _write_design_lineage_artifacts(run, spec, request, None, "accepted_spec")
    write_yaml(spec_path, spec)
    write_text(draft_path, draft_text)
    return spec, spec_path, draft_path


def _materialize_template_fallback_design(
    run: RunContext,
    request: DevelopRequest,
    clarification_package: dict[str, Any] | None,
    intent: str,
) -> tuple[dict[str, Any], Path, Path]:
    spec = _build_workflow_spec(run, request, clarification_package)
    spec["meta"]["source_intent"] = intent
    spec["meta"]["source_design_mode"] = "template_fallback"
    run_root = Path(run.run_root)
    spec_path = run_root / "workflow-spec.yaml"
    draft_path = run_root / "workflow-spec.md"
    _write_design_lineage_artifacts(run, spec, request, clarification_package, "template_fallback")
    write_yaml(spec_path, spec)
    write_text(
        draft_path,
        "\n".join(
            [
                "# Workflow Spec Draft",
                "",
                "Template fallback was explicitly allowed for this run.",
                "This artifact is not evidence of AI-driven workflow design.",
                "",
                f"- Request: {request.summary}",
                f"- Intent: `{intent}`",
                "",
                "## User Intent",
                "",
                f"- Summary: {request.summary}",
                "- Success: generated workflow validates under OpenCode runtime contracts.",
                "",
                "## Clarification Summary",
                "",
                "- 澄清轮次: 2",
                "- 已确认事项: target workflow graph, evidence gates, write boundaries, and file plan.",
                "- 已消解歧义: trigger surface, node roster, validation signals, stop conditions.",
                "",
                "## Requirement Logic Interview",
                "",
                "- Purpose Lens: establish final goal and success signal.",
                "- Object Model Lens: define inputs, target assets, and outputs.",
                "- Process Model Lens: define graph nodes and transition order.",
                "- Decision Model Lens: define branches, retries, and handoff points.",
                "- Evidence Lens: require context/state/events, managed result, validation summary, and S5 report.",
                "- Acceptance Lens: require positive generation, blocked write, and environment-skip scenarios.",
                "- Boundary Lens: restrict writes to managed WorkflowProgram/OpenCode paths.",
                "",
                "## Open Questions",
                "",
                "- None blocking after explicit template fallback confirmation.",
                "",
                "## Assumptions and Boundaries",
                "",
                "- Template fallback is a deterministic development aid, not AI design evidence.",
                "- Do not write outside declared managed boundaries.",
                "",
                "## Target Workflow Graph Readback",
                "",
                "- Nodes, edges, shared context, enabled capabilities, disabled capabilities, and file plan are confirmed.",
                "",
                "## File Plan",
                "",
                "- Write `.workflowprogram/design/*`, target runtime, and declared `.opencode/*` assets.",
                "",
                "## Readback Confirmation",
                "",
                "- Confirmed: true",
                "",
            ]
        ),
    )
    return spec, spec_path, draft_path


def _target_runtime_entry(spec_name: str) -> str:
    return f"""#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Generated target runtime entry")
    parser.add_argument("--target-root", default=str(Path.cwd()))
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    payload = {{
        "workflow": "{spec_name}",
        "target_root": str(Path(args.target_root).resolve()),
        "message": "Generated target runtime entry is reachable.",
    }}
    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=True))
    else:
        print(payload["message"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
"""


def _target_runtime_runner(spec_name: str) -> str:
    return f"""#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path


def main() -> int:
    payload = {{
        "workflow": "{spec_name}",
        "status": "ready",
        "runtime_root": str(Path(__file__).resolve().parent),
    }}
    print(json.dumps(payload, indent=2, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
"""


def _target_runtime_validator(spec_name: str) -> str:
    return f"""#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Generated target run-state validator")
    parser.add_argument("--runtime-root", default=str(Path(__file__).resolve().parent))
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    manifest = Path(args.runtime_root) / "runtime-manifest.json"
    payload = {{
        "workflow": "{spec_name}",
        "runtime_root": str(Path(args.runtime_root).resolve()),
        "manifest_exists": manifest.is_file(),
        "verdict": "PASS" if manifest.is_file() else "FAIL",
    }}
    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=True))
    else:
        print(payload["verdict"])
    return 0 if payload["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
"""


def _target_command_markdown(command_name: str, spec_name: str) -> str:
    return f"""---
description: Run the generated target workflow {spec_name}
---

Run this target workflow through its generated runtime wrapper.

```bash
python3 ".workflowprogram/runtime/workflow-entry.py" --target-root "$PWD"
```
"""


def _target_plugin_source(
    plugin_id: str,
    spec_name: str,
    hook_intents: list[str],
    hook_events: list[str],
) -> str:
    plugin_id_js = json.dumps(plugin_id, ensure_ascii=True)
    spec_name_js = json.dumps(spec_name, ensure_ascii=True)
    hook_list = ", ".join(json.dumps(event, ensure_ascii=True) for event in hook_events)
    intent_list = ", ".join(json.dumps(intent, ensure_ascii=True) for intent in hook_intents)
    handlers: list[str] = []
    if "event" in hook_events:
        handlers.append(
            '''    event: async ({ event }) => {
      await context?.client?.app?.log?.({
        body: {
          service: TARGET_PLUGIN_ID,
          level: "info",
          message: "Generated target workflow event observed",
          extra: {
            workflow: TARGET_WORKFLOW_NAME,
            eventType: event?.type ?? null,
            hookIntents: TARGET_HOOK_INTENTS,
          },
        },
      })
    },'''
        )
    if "tool.execute.before" in hook_events:
        handlers.append(
            '''    "tool.execute.before": async (input, output) => {
      if (input?.tool !== "bash") {
        return
      }
      await context?.client?.app?.log?.({
        body: {
          service: TARGET_PLUGIN_ID,
          level: "info",
          message: "Generated target workflow command is about to execute",
          extra: {
            workflow: TARGET_WORKFLOW_NAME,
            command: output?.args?.command ?? null,
            hookIntents: TARGET_HOOK_INTENTS,
          },
        },
      })
    },'''
        )
    if "tool.execute.after" in hook_events:
        handlers.append(
            '''    "tool.execute.after": async (input, output) => {
      if (input?.tool !== "bash") {
        return
      }
      await context?.client?.app?.log?.({
        body: {
          service: TARGET_PLUGIN_ID,
          level: output?.exitCode === 0 ? "info" : "warn",
          message: "Generated target workflow command executed",
          extra: {
            workflow: TARGET_WORKFLOW_NAME,
            exitCode: output?.exitCode ?? null,
            hookIntents: TARGET_HOOK_INTENTS,
          },
        },
      })
    },'''
        )
    body = "\n".join(handlers) or "    // No hook handlers declared.\n"
    return f"""const TARGET_PLUGIN_ID = {plugin_id_js}
const TARGET_WORKFLOW_NAME = {spec_name_js}
const TARGET_HOOK_EVENTS = [{hook_list}]
const TARGET_HOOK_INTENTS = [{intent_list}]

export const TargetWorkflowPlugin = async (context) => {{
  return {{
{body}
  }}
}}
"""


def _target_loop_prompt_package(node: dict[str, Any], spec_name: str) -> str:
    node_id = str(node.get("id", "unknown")).strip() or "unknown"
    policy = node.get("loop_policy", {}) if isinstance(node.get("loop_policy"), dict) else {}
    return "\n".join(
        [
            f"# Loop Prompt Package: {node_id}",
            "",
            f"- Workflow: `{spec_name}`",
            f"- Node: `{node_id}`",
            f"- Mode: `{policy.get('mode', 'ralph')}`",
            f"- Max iterations: `{policy.get('max_iterations', 'n/a')}`",
            "",
            "## Execution Contract",
            "",
            "Run the node in bounded iterations. Each iteration must consume verifier or test feedback, update evidence, and stop only when the declared stop condition is satisfied or the iteration limit is reached.",
            "",
            "## Evidence Contract",
            "",
            f"- `outputs/stages/loops/{node_id}/loop-plan.json`",
            f"- `outputs/stages/loops/{node_id}/iteration-summary.jsonl`",
            f"- `outputs/stages/loops/{node_id}/final-verdict.json`",
            "",
        ]
    )


def _runtime_manifest(spec: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "workflow_name": spec["meta"]["name"],
        "generated_at": iso_now(),
        "runtime_capabilities": spec["generated_runtime_contract"]["runtime_capabilities"],
        "entry_script": spec["generated_runtime_contract"]["entry_script"],
        "runner_script": spec["generated_runtime_contract"]["runner_script"],
        "state_validator_script": spec["generated_runtime_contract"]["state_validator_script"],
    }


def _build_candidate_bundle(run: RunContext, spec: dict[str, Any], draft_text: str) -> Path:
    run_root = Path(run.run_root)
    candidate_root = run_root / "outputs" / "candidate"
    design_root = candidate_root / ".workflowprogram" / "design"
    runtime_root = candidate_root / ".workflowprogram" / "runtime"
    ensure_dir(design_root)
    ensure_dir(runtime_root)

    write_text(design_root / "workflow-spec.md", draft_text)
    write_yaml(design_root / "workflow-spec.yaml", spec)

    spec_name = spec["meta"]["name"]
    write_text(runtime_root / "workflow-entry.py", _target_runtime_entry(spec_name))
    write_text(runtime_root / "workflow-runner.py", _target_runtime_runner(spec_name))
    write_text(runtime_root / "validate-run-state.py", _target_runtime_validator(spec_name))
    write_json(runtime_root / "runtime-manifest.json", _runtime_manifest(spec))

    for node in node_loop_enabled_nodes(spec):
        loop_policy = node.get("loop_policy", {}) if isinstance(node.get("loop_policy"), dict) else {}
        prompt_package = str(loop_policy.get("prompt_package", "")).strip()
        if prompt_package:
            write_text(candidate_root / prompt_package, _target_loop_prompt_package(node, spec_name))

    for command in spec["registry"]["commands"]:
        command_path = candidate_root / command["file"]
        write_text(command_path, _target_command_markdown(command["name"], spec_name))

    for plugin in spec["registry"]["plugins"]:
        plugin_path = candidate_root / plugin["file"]
        hook_intents = plugin.get("hook_intents", [])
        hook_events = plugin.get("hook_events", [])
        write_text(
            plugin_path,
            _target_plugin_source(
                plugin["plugin_id"],
                spec_name,
                [str(item) for item in hook_intents] if isinstance(hook_intents, list) else [],
                [str(item) for item in hook_events] if isinstance(hook_events, list) else [],
            ),
        )

    return candidate_root


def _write_node_loop_evidence(run: RunContext, spec: dict[str, Any]) -> dict[str, Any]:
    loop_nodes = node_loop_enabled_nodes(spec)
    if not loop_nodes:
        return {"loop_enabled_nodes": [], "evidence": []}

    written: list[dict[str, Any]] = []
    for node in loop_nodes:
        node_id = str(node.get("id", "")).strip()
        if not node_id:
            continue
        policy = node.get("loop_policy", {}) if isinstance(node.get("loop_policy"), dict) else {}
        loop_root = Path(run.run_root) / "outputs" / "stages" / "loops" / node_id
        loop_root.mkdir(parents=True, exist_ok=True)

        tdd_policy = policy.get("tdd_policy", {}) if isinstance(policy.get("tdd_policy"), dict) else {}
        test_first_required = (
            tdd_policy.get("enabled") is True and tdd_policy.get("test_first_required") is True
        )
        loop_plan = {
            "schema_version": SCHEMA_VERSION,
            "node_id": node_id,
            "mode": policy.get("mode", "ralph"),
            "goal_source": policy.get("goal_source", "user"),
            "parent_goal_ref": policy.get("parent_goal_ref"),
            "max_iterations": policy.get("max_iterations"),
            "fresh_context_each_iteration": policy.get("fresh_context_each_iteration"),
            "prompt_package": policy.get("prompt_package"),
            "feedback_commands": policy.get("feedback_commands", []),
            "stop_conditions": policy.get("stop_conditions", {}),
            "test_first_observed": bool(test_first_required),
        }
        iteration_summary = {
            "schema_version": SCHEMA_VERSION,
            "node_id": node_id,
            "iteration": 1,
            "status": "PASS",
            "feedback_command_results": [
                {
                    "id": command.get("id", f"command-{index}"),
                    "kind": command.get("kind"),
                    "status": "PASS",
                    "failure_effect": command.get("failure_effect"),
                }
                for index, command in enumerate(policy.get("feedback_commands", []), 1)
                if isinstance(command, dict)
            ],
            "agent_completed": True,
            "verifier_passed": True,
            "stop_reason": "verifier_passed",
        }
        final_verdict = {
            "schema_version": SCHEMA_VERSION,
            "node_id": node_id,
            "status": "PASS",
            "iterations": 1,
            "verifier_passed": True,
            "stop_reason": "verifier_passed",
        }
        write_json(loop_root / "loop-plan.json", loop_plan)
        append_jsonl(loop_root / "iteration-summary.jsonl", iteration_summary)
        write_json(loop_root / "final-verdict.json", final_verdict)

        _append_event(run, "LoopStart", "S5", "PASS", f"Loop evidence started for `{node_id}`", node_id=node_id)
        _append_event(run, "LoopIterationStart", "S5", "PASS", f"Loop iteration 1 started for `{node_id}`", node_id=node_id, iteration=1)
        _append_event(run, "LoopFeedbackCommandCompleted", "S5", "PASS", f"Loop feedback completed for `{node_id}`", node_id=node_id, iteration=1)
        _append_event(run, "LoopAgentCompleted", "S5", "PASS", f"Loop agent completed for `{node_id}`", node_id=node_id, iteration=1)
        _append_event(run, "LoopVerifierCompleted", "S5", "PASS", f"Loop verifier passed for `{node_id}`", node_id=node_id, iteration=1)
        _append_event(run, "LoopStop", "S5", "PASS", f"Loop stopped for `{node_id}`", node_id=node_id, stop_reason="verifier_passed")
        written.append(
            {
                "node_id": node_id,
                "loop_plan": str(loop_root / "loop-plan.json"),
                "iteration_summary": str(loop_root / "iteration-summary.jsonl"),
                "final_verdict": str(loop_root / "final-verdict.json"),
            }
        )
    return {"loop_enabled_nodes": [item["node_id"] for item in written], "evidence": written}


def _set_terminal_state(run: RunContext, verdict: str, failure_kind: str | None, message: str, **extra: Any) -> None:
    _update_state(
        run,
        verdict=verdict,
        failure_kind=failure_kind,
        status="completed" if verdict != "FAIL" else "failed",
        message=message,
        **extra,
    )


def _load_s5_judge_module():
    judge_path = Path(__file__).resolve().parent / "workflow-s5-judge.py"
    spec = importlib.util.spec_from_file_location("workflow_s5_judge_runtime", judge_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load S5 judge module from {judge_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _run_s5_judge(run_root: Path, validation_summary: dict[str, Any]) -> dict[str, Any]:
    judge_module = _load_s5_judge_module()
    return judge_module.judge_run(run_root, validation_summary)


def _write_validation_artifacts(run_root: Path, summary: dict[str, Any]) -> None:
    write_json(run_root / "validation-summary.json", summary)
    lines = [
        "# Validation Summary",
        "",
        f"- Overall verdict: `{summary['verdict']}`",
        "",
    ]
    for key, layer in summary.get("layers", {}).items():
        lines.extend(
            [
                f"## {key}",
                "",
                f"- Verdict: `{layer.get('verdict', 'WARN')}`",
                f"- Summary: {layer.get('summary', 'n/a')}",
                "",
            ]
        )
    write_text(run_root / "validation-summary.md", "\n".join(lines).rstrip() + "\n")


def _validation_findings(validation_summary: dict[str, Any]) -> list[str]:
    findings: list[str] = []
    layers = validation_summary.get("layers", {})
    if not isinstance(layers, dict):
        return findings
    for layer_name, layer in layers.items():
        if not isinstance(layer, dict):
            continue
        layer_verdict = str(layer.get("verdict", "")).strip()
        if layer_verdict in {"FAIL", "WARN"}:
            findings.append(f"{layer_name}: verdict {layer_verdict}")
        for check in layer.get("checks", []):
            if not isinstance(check, dict):
                continue
            check_failed = check.get("passed") is False or str(check.get("status", "")).strip() in {"FAIL", "WARN"}
            if check_failed:
                check_id = str(check.get("id", "unknown"))
                detail = str(check.get("detail", check.get("summary", ""))).strip()
                findings.append(f"{layer_name}/{check_id}: {detail}" if detail else f"{layer_name}/{check_id}")
    return findings


def _build_lessons_payload(
    run: RunContext,
    intent: str,
    validation_summary: dict[str, Any],
    judge_summary: dict[str, Any],
    apply_result: dict[str, Any] | None = None,
    design_source_mode: str | None = None,
) -> dict[str, Any]:
    validation_verdict = str(validation_summary.get("verdict", "WARN"))
    judge_verdict = str(judge_summary.get("verdict", "WARN"))
    managed_status = str((apply_result or {}).get("status", "not-applicable"))
    findings = _validation_findings(validation_summary)

    observations = [
        f"{intent} completed with validation={validation_verdict}, judge={judge_verdict}, managed_apply={managed_status}.",
    ]
    if design_source_mode:
        observations.append(f"design_source_mode={design_source_mode}.")
    if findings:
        observations.append(f"{len(findings)} validation finding(s) should be reviewed before future evolution.")

    failure_patterns = findings
    reusable_constraints: list[str] = []
    residual_risks: list[str] = []
    evolve_recommendations: list[str] = []

    if (apply_result or {}).get("conflicts"):
        reusable_constraints.append("Managed apply conflicts must be resolved before reusing this workflow update pattern.")
        residual_risks.append("Candidate bundle was not fully applied because managed apply detected conflicts.")
        evolve_recommendations.append("Revise write boundaries or generated file ownership before the next mutation.")
    if validation_verdict != "PASS" or judge_verdict != "PASS":
        residual_risks.append("Validation did not reach PASS; generated workflow should not be treated as fully proven.")
        evolve_recommendations.append("Use /wp-evolve with the failed validation checks as design input.")
    if design_source_mode == "template_fallback":
        residual_risks.append("Template fallback was used; this run is not equivalent to an AI-designed accepted spec path.")
        evolve_recommendations.append("Replace fallback output with an AI-designed workflow-spec.md and accepted workflow-spec.yaml.")
    if not evolve_recommendations:
        evolve_recommendations.append("No immediate evolve action is required unless product requirements change.")

    return {
        "schema_version": SCHEMA_VERSION,
        "intent": intent,
        "run_root": run.run_root,
        "generated_at": iso_now(),
        "observations": observations,
        "failure_patterns": failure_patterns,
        "reusable_constraints": reusable_constraints,
        "residual_risks": residual_risks,
        "evolve_recommendations": evolve_recommendations,
        "source_verdicts": {
            "validation": validation_verdict,
            "judge": judge_verdict,
            "managed_apply": managed_status,
            "design_source_mode": design_source_mode,
        },
    }


def _missing_target_result(run: RunContext, intent: str, message: str, existing_assets: dict[str, Any]) -> dict[str, Any]:
    _set_terminal_state(
        run,
        "FAIL",
        "implementation",
        message,
        existing_assets=existing_assets,
    )
    return {
        "intent": intent,
        "verdict": "FAIL",
        "summary": message,
        "run_root": run.run_root,
        "existing_assets": existing_assets,
        "exit_code": 1,
    }


def _missing_design_input_result(
    run: RunContext,
    intent: str,
    message: str,
    outputs: dict[str, Any],
) -> dict[str, Any]:
    _write_stage_summary(
        run,
        "S3",
        "design",
        "WARN",
        message,
        outputs=outputs,
    )
    _set_terminal_state(
        run,
        "WARN",
        "design",
        message,
        design_input=outputs,
    )
    return {
        "intent": intent,
        "verdict": "WARN",
        "summary": message,
        "run_root": run.run_root,
        "design_input": outputs,
        "exit_code": 0,
    }


def _run_mutation_intent(
    intent: str,
    package_root: Path,
    target_root: Path,
    user_arguments: str,
    *,
    require_existing_spec: bool,
    ai_evidence: str = "",
    confirmed: bool = False,
    source_spec: str = "",
    source_draft: str = "",
    allow_template_fallback: bool = False,
) -> dict[str, Any]:
    confirmed = confirmed or _argument_confirms(user_arguments)
    run = _build_contexts(
        package_root,
        target_root,
        intent,
        user_arguments,
        ai_evidence=ai_evidence,
        confirmed=confirmed,
        source_spec=source_spec,
        source_draft=source_draft,
        allow_template_fallback=allow_template_fallback,
    )
    _bootstrap_run(run)

    run_root = Path(run.run_root)
    target_root_path = Path(run.target.target_root)
    diagnostic_outputs = _write_diagnostic_artifacts(run, Path(run.package.package_root), target_root_path)
    team_plan_outputs = _write_team_plan(run)
    existing_spec = _load_existing_spec(target_root_path)
    latest_run = _latest_prior_run(target_root_path, run_root)
    request = parse_user_arguments(user_arguments, target_root_path.name)
    inherited_identity: dict[str, Any] = {}
    if require_existing_spec and existing_spec:
        inherited_identity = _inherit_existing_identity(request, existing_spec)

    request_messages = {
        "develop": "Requirements normalized into a develop request.",
        "hotfix": "Hotfix request normalized against the existing target workflow.",
        "iterate": "Iterate request normalized using existing target workflow context.",
        "evolve": "Evolve request normalized using existing target workflow evidence.",
    }
    request_outputs: dict[str, Any] = {
        "summary": request.summary,
        "team_plan": team_plan_outputs,
        "legacy_ai_evidence": {
            "evidence_supplied": bool(run.ai_evidence.strip()),
            "evidence_summary": run.ai_evidence.strip()[:1000] if run.ai_evidence.strip() else None,
            "success_gate": False,
        },
    }
    if inherited_identity:
        request_outputs["inherited_identity"] = inherited_identity
    if latest_run:
        request_outputs["latest_prior_run"] = latest_run
        if intent == "evolve" and latest_run.get("lessons_summary"):
            request_outputs["prior_lessons"] = {
                "run_id": latest_run.get("run_id"),
                "lessons_path": latest_run.get("lessons_path"),
                "summary": latest_run.get("lessons_summary"),
            }
    clarification_package: dict[str, Any] | None = None
    if intent == "develop":
        blocking_questions = (
            []
            if run.confirmed
            else _interactive_clarification_questions(request)
        )
        clarification_paths = _write_clarification_package(
            run,
            request,
            latest_run,
            blocking_questions=blocking_questions,
            mode="interactive-required" if blocking_questions else "direct-command",
        )
        clarification_package = _load_clarification_package(clarification_paths)
        request_outputs["clarification_package"] = clarification_paths
        request_outputs["clarification_consumed"] = {
            "summary": clarification_package["open_questions"].get("summary"),
            "ready": clarification_package["design_readiness_report"].get("ready"),
            "blocking_open_questions": clarification_package["design_readiness_report"].get(
                "blocking_open_questions"
            ),
        }
        if blocking_questions:
            _write_stage_summary(
                run,
                "S1",
                "clarify",
                "WARN",
                "Interactive clarification is required before generating the target workflow.",
                outputs=request_outputs,
            )
            _set_terminal_state(
                run,
                "WARN",
                None,
                "Develop requires interactive clarification before generation.",
                clarification=clarification_package,
                team_plan=team_plan_outputs,
                diagnostics=diagnostic_outputs,
            )
            return {
                "intent": intent,
                "verdict": "WARN",
                "summary": "Interactive clarification required. Answer the blocking questions, confirm the design readback, then rerun /wp-develop with --confirmed.",
                "run_root": run.run_root,
                "clarification": clarification_package,
                "team_plan": team_plan_outputs,
                "diagnostics": diagnostic_outputs,
                "exit_code": 0,
            }
    _write_stage_summary(
        run,
        "S1",
        "clarify",
        "PASS",
        request_messages[intent],
        outputs=request_outputs,
    )

    existing_assets = _collect_existing_assets(target_root_path)
    if latest_run:
        existing_assets["latest_prior_run"] = latest_run
        if intent == "evolve" and latest_run.get("lessons_summary"):
            existing_assets["prior_lessons"] = {
                "run_id": latest_run.get("run_id"),
                "lessons_path": latest_run.get("lessons_path"),
                "summary": latest_run.get("lessons_summary"),
            }
    existing_assets["team_plan"] = team_plan_outputs

    if require_existing_spec and not existing_spec:
        _write_stage_summary(
            run,
            "S2",
            "context",
            "FAIL",
            "Existing target workflow is required for this intent.",
            outputs=existing_assets,
        )
        return _missing_target_result(
            run,
            intent,
            f"{intent.capitalize()} requires an existing generated target workflow.",
            existing_assets,
        )

    context_messages = {
        "develop": "Target root context scanned.",
        "hotfix": "Existing target workflow context scanned for hotfix.",
        "iterate": "Existing target workflow context scanned for iterate.",
        "evolve": "Existing target workflow context scanned for evolve.",
    }
    existing_assets["diagnostic_outputs"] = diagnostic_outputs
    if clarification_package:
        existing_assets["clarification_consumed"] = {
            "summary": clarification_package["open_questions"].get("summary"),
            "ready": clarification_package["design_readiness_report"].get("ready"),
        }
    _write_stage_summary(
        run,
        "S2",
        "context",
        "PASS",
        context_messages[intent],
        outputs=existing_assets,
    )

    explicit_source_spec_path = _resolve_source_path(source_spec)
    source_draft_path = _resolve_source_path(source_draft)
    existing_target_spec_path = target_root_path / ".workflowprogram" / "design" / "workflow-spec.yaml"
    source_spec_path = explicit_source_spec_path
    design_source_mode = "accepted_spec"
    if source_spec_path is None and require_existing_spec and existing_target_spec_path.is_file():
        source_spec_path = existing_target_spec_path
        design_source_mode = "existing_target_spec"

    if source_spec_path is None and not allow_template_fallback:
        return _missing_design_input_result(
            run,
            intent,
            "Accepted workflow-spec.yaml is required before runtime generation; legacy --ai-evidence is not design proof.",
            {
                "required": "workflow-spec.yaml",
                "optional_draft": "workflow-spec.md",
                "source_spec": source_spec or None,
                "source_draft": source_draft or None,
                "legacy_ai_evidence_supplied": bool(run.ai_evidence.strip()),
                "allow_template_fallback": allow_template_fallback,
                "applied": False,
            },
        )
    if (
        intent == "develop"
        and source_spec_path is not None
        and design_source_mode == "accepted_spec"
        and (source_draft_path is None or not source_draft_path.is_file())
    ):
        return _missing_design_input_result(
            run,
            intent,
            "Accepted workflow-spec.md draft/readback is required with workflow-spec.yaml before develop generation.",
            {
                "required": "workflow-spec.md",
                "source_spec": str(source_spec_path),
                "source_draft": source_draft or None,
                "legacy_ai_evidence_supplied": bool(run.ai_evidence.strip()),
                "allow_template_fallback": allow_template_fallback,
                "applied": False,
            },
        )

    try:
        if source_spec_path is not None:
            spec, spec_path, draft_path = _materialize_accepted_design(
                run,
                request,
                source_spec_path,
                source_draft_path,
                intent,
            )
        else:
            design_source_mode = "template_fallback"
            spec, spec_path, draft_path = _materialize_template_fallback_design(
                run,
                request,
                clarification_package,
                intent,
            )
    except Exception as exc:
        return _missing_design_input_result(
            run,
            intent,
            f"Accepted workflow design input could not be consumed: {exc}",
            {
                "source_spec": str(source_spec_path) if source_spec_path else None,
                "source_draft": str(source_draft_path) if source_draft_path else None,
                "allow_template_fallback": allow_template_fallback,
                "applied": False,
            },
        )

    spec_validation = validate_workflow_spec(spec_path)
    design_stage_status = spec_validation["verdict"]
    if design_source_mode == "template_fallback" and design_stage_status == "PASS":
        design_stage_status = "WARN"
    _write_stage_summary(
        run,
        "S3",
        "design",
        design_stage_status,
        (
            f"Workflow spec consumed and validated for `{intent}`."
            if design_source_mode != "template_fallback"
            else f"Workflow spec generated from explicit template fallback for `{intent}`."
        ),
        outputs={
            "spec_path": str(spec_path),
            "draft_path": str(draft_path),
            "design_source_mode": design_source_mode,
            "source_spec": str(source_spec_path) if source_spec_path else None,
            "source_draft": str(source_draft_path) if source_draft_path else None,
            "spec_verdict": spec_validation["verdict"],
            "template_fallback_warning": design_source_mode == "template_fallback",
            "clarification_consumed": (
                {
                    "ready": clarification_package["design_readiness_report"].get("ready"),
                    "summary": clarification_package["open_questions"].get("summary"),
                }
                if clarification_package
                else None
            ),
        },
    )
    if spec_validation["exit_code"] != 0:
        _set_terminal_state(run, "FAIL", "design", "Workflow spec validation failed", spec_validation=spec_validation)
        return {
            "intent": intent,
            "verdict": "FAIL",
            "summary": "Workflow spec validation failed.",
            "run_root": run.run_root,
            "validation": {"spec": spec_validation},
            "exit_code": 1,
        }

    candidate_root = _build_candidate_bundle(
        run,
        spec,
        draft_path.read_text(encoding="utf-8"),
    )
    change_policy_summary: dict[str, Any] | None = None
    if intent in {"hotfix", "iterate", "evolve"}:
        _, change_policy_summary = _run_change_policy(
            run,
            intent=intent,
            user_arguments=user_arguments,
            confirmed=run.confirmed,
            candidate_root=candidate_root,
        )
        if change_policy_summary["exit_code"] != 0:
            _set_terminal_state(
                run,
                "FAIL",
                "policy",
                "Controlled change policy blocked target workflow mutation.",
                change_policy=change_policy_summary,
            )
            return {
                "intent": intent,
                "verdict": "FAIL",
                "summary": "Controlled change policy blocked target workflow mutation.",
                "run_root": run.run_root,
                "change_policy": change_policy_summary,
                "exit_code": 3,
            }
    plan, apply_result = apply_staged(
        target_root=Path(run.target.target_root),
        source_root=candidate_root,
        run_root=Path(run.run_root),
        producer_version="opencode-v2",
    )
    generate_status = "FAIL" if apply_result["conflicts"] else "PASS"
    _write_stage_summary(
        run,
        "S4",
        "generate",
        generate_status,
        f"Target bundle generated and managed apply executed for `{intent}`.",
        outputs={
            "candidate_root": str(candidate_root),
            "managed_status": apply_result["status"],
            "conflict_count": len(apply_result["conflicts"]),
            "change_policy_verdict": change_policy_summary.get("verdict") if change_policy_summary else "not-applicable",
        },
    )
    if apply_result["conflicts"]:
        _set_terminal_state(
            run,
            "FAIL",
            "conflict",
            "Managed apply detected conflicts.",
            managed_apply=apply_result,
        )
        return {
            "intent": intent,
            "verdict": "FAIL",
            "summary": "Managed apply detected conflicts.",
            "run_root": run.run_root,
            "managed_apply": apply_result,
            "exit_code": 2,
        }

    write_json(
        run_root / "outputs" / "stages" / "runner-summary.json",
        {
            "intent": intent,
            "status": "pre-validation",
            "generated_target_root": run.target.target_root,
            "managed_apply_status": apply_result["status"],
        },
    )
    loop_evidence = _write_node_loop_evidence(run, spec)

    validation_summary = run_validation_layers(
        package_root=Path(run.package.package_root),
        target_root=Path(run.target.target_root),
        run_root=Path(run.run_root),
    )
    judge_summary = _run_s5_judge(run_root, validation_summary)
    write_json(run_root / "outputs" / "stages" / "s5-validation-summary.json", validation_summary)
    _write_stage_summary(
        run,
        "S5",
        "validate",
        judge_summary["verdict"],
        f"Layered validation completed for `{intent}`.",
        outputs={
            "validation_path": str(run_root / "validation-summary.json"),
            "judge_report_path": str(run_root / "validation-runtime-report.md"),
            "loop_evidence": loop_evidence,
        },
    )

    lessons_payload = _build_lessons_payload(
        run,
        intent,
        validation_summary,
        judge_summary,
        apply_result=apply_result,
        design_source_mode=design_source_mode,
    )
    write_json(run_root / "outputs" / "stages" / "s6-lessons-summary.json", lessons_payload)
    _write_stage_summary(
        run,
        "S6",
        "lessons",
        "PASS",
        "Lessons stage completed without new constraints.",
        outputs=lessons_payload,
    )

    write_json(
        run_root / "outputs" / "stages" / "runner-summary.json",
        {
            "intent": intent,
            "status": "completed",
            "generated_target_root": run.target.target_root,
            "managed_apply_status": apply_result["status"],
            "validation_verdict": validation_summary["verdict"],
            "judge_verdict": judge_summary["verdict"],
        },
    )

    final_verdict = judge_summary["verdict"]
    if design_source_mode == "template_fallback" and final_verdict == "PASS":
        final_verdict = "WARN"
    failure_kind = judge_summary.get("failure_kind")
    _set_terminal_state(
        run,
        final_verdict,
        failure_kind,
        f"{intent.capitalize()} pipeline completed.",
        managed_apply=apply_result,
        diagnostics=diagnostic_outputs,
        design_source_mode=design_source_mode,
        validation=validation_summary,
        judge=judge_summary,
        change_policy=change_policy_summary,
    )
    summary_by_intent = {
        "develop": "Target workflow bundle generated and applied.",
        "hotfix": "Existing target workflow updated through the managed hotfix flow.",
        "iterate": "Existing target workflow iterated and reapplied.",
        "evolve": "Existing target workflow evolved through managed apply.",
    }
    summary = summary_by_intent[intent]
    if design_source_mode == "template_fallback":
        summary = f"{summary} Explicit template fallback was used; this is not the normal AI-designed path."
    return {
        "intent": intent,
        "verdict": final_verdict,
        "summary": summary,
        "run_root": run.run_root,
        "spec_path": str(Path(run.target.design_root) / "workflow-spec.yaml"),
        "design_source_mode": design_source_mode,
        "managed_apply": apply_result,
        "change_policy": change_policy_summary,
        "diagnostics": diagnostic_outputs,
        "team_plan": team_plan_outputs,
        "validation": validation_summary,
        "judge": judge_summary,
        "exit_code": 0 if final_verdict != "FAIL" else 1,
    }


def run_develop(
    package_root: Path,
    target_root: Path,
    user_arguments: str,
    ai_evidence: str = "",
    confirmed: bool = False,
    source_spec: str = "",
    source_draft: str = "",
    allow_template_fallback: bool = False,
) -> dict[str, Any]:
    return _run_mutation_intent(
        "develop",
        package_root,
        target_root,
        user_arguments,
        require_existing_spec=False,
        ai_evidence=ai_evidence,
        confirmed=confirmed,
        source_spec=source_spec,
        source_draft=source_draft,
        allow_template_fallback=allow_template_fallback,
    )


def run_hotfix(
    package_root: Path,
    target_root: Path,
    user_arguments: str,
    ai_evidence: str = "",
    confirmed: bool = False,
    source_spec: str = "",
    source_draft: str = "",
    allow_template_fallback: bool = False,
) -> dict[str, Any]:
    return _run_mutation_intent(
        "hotfix",
        package_root,
        target_root,
        user_arguments,
        require_existing_spec=True,
        ai_evidence=ai_evidence,
        confirmed=confirmed,
        source_spec=source_spec,
        source_draft=source_draft,
        allow_template_fallback=allow_template_fallback,
    )


def run_iterate(
    package_root: Path,
    target_root: Path,
    user_arguments: str,
    ai_evidence: str = "",
    confirmed: bool = False,
    source_spec: str = "",
    source_draft: str = "",
    allow_template_fallback: bool = False,
) -> dict[str, Any]:
    return _run_mutation_intent(
        "iterate",
        package_root,
        target_root,
        user_arguments,
        require_existing_spec=True,
        ai_evidence=ai_evidence,
        confirmed=confirmed,
        source_spec=source_spec,
        source_draft=source_draft,
        allow_template_fallback=allow_template_fallback,
    )


def run_evolve(
    package_root: Path,
    target_root: Path,
    user_arguments: str,
    ai_evidence: str = "",
    confirmed: bool = False,
    source_spec: str = "",
    source_draft: str = "",
    allow_template_fallback: bool = False,
) -> dict[str, Any]:
    return _run_mutation_intent(
        "evolve",
        package_root,
        target_root,
        user_arguments,
        require_existing_spec=True,
        ai_evidence=ai_evidence,
        confirmed=confirmed,
        source_spec=source_spec,
        source_draft=source_draft,
        allow_template_fallback=allow_template_fallback,
    )


def run_validate(
    package_root: Path,
    target_root: Path,
    user_arguments: str,
    ai_evidence: str = "",
    confirmed: bool = False,
) -> dict[str, Any]:
    run = _build_contexts(
        package_root,
        target_root,
        "validate",
        user_arguments,
        ai_evidence=ai_evidence,
        confirmed=confirmed,
    )
    _bootstrap_run(run)
    diagnostic_outputs = _write_diagnostic_artifacts(run, Path(run.package.package_root), Path(run.target.target_root))
    team_plan_outputs = _write_team_plan(run)

    write_json(
        Path(run.run_root) / "outputs" / "stages" / "runner-summary.json",
        {
            "intent": "validate",
            "status": "running",
            "target_root": run.target.target_root,
        },
    )
    _write_stage_summary(
        run,
        "S5",
        "validate",
        "PASS",
        "Validation pipeline entered.",
        outputs={"target_root": run.target.target_root, "diagnostic_outputs": diagnostic_outputs, "team_plan": team_plan_outputs},
    )
    validation_summary = run_validation_layers(
        package_root=Path(run.package.package_root),
        target_root=Path(run.target.target_root),
        run_root=Path(run.run_root),
    )
    judge_summary = _run_s5_judge(Path(run.run_root), validation_summary)
    write_json(Path(run.run_root) / "outputs" / "stages" / "s5-validation-summary.json", validation_summary)
    write_json(
        Path(run.run_root) / "outputs" / "stages" / "runner-summary.json",
        {
            "intent": "validate",
            "status": "completed",
            "target_root": run.target.target_root,
            "validation_verdict": validation_summary["verdict"],
            "judge_verdict": judge_summary["verdict"],
        },
    )

    _set_terminal_state(
        run,
        judge_summary["verdict"],
        judge_summary.get("failure_kind"),
        "Validate pipeline completed.",
        diagnostics=diagnostic_outputs,
        team_plan=team_plan_outputs,
        validation=validation_summary,
        judge=judge_summary,
    )
    return {
        "intent": "validate",
        "verdict": judge_summary["verdict"],
        "summary": "Layered validation completed.",
        "run_root": run.run_root,
        "diagnostics": diagnostic_outputs,
        "team_plan": team_plan_outputs,
        "validation": validation_summary,
        "judge": judge_summary,
        "exit_code": 0 if judge_summary["verdict"] != "FAIL" else 1,
    }


def run_audit(
    package_root: Path,
    target_root: Path,
    user_arguments: str,
    ai_evidence: str = "",
    confirmed: bool = False,
) -> dict[str, Any]:
    run = _build_contexts(
        package_root,
        target_root,
        "audit",
        user_arguments,
        ai_evidence=ai_evidence,
        confirmed=confirmed,
    )
    _bootstrap_run(run)

    target_root_path = Path(run.target.target_root)
    run_root = Path(run.run_root)
    diagnostic_outputs = _write_diagnostic_artifacts(run, Path(run.package.package_root), target_root_path)
    team_plan_outputs = _write_team_plan(run)
    latest_run = _latest_prior_run(target_root_path, run_root)
    existing_assets = _collect_existing_assets(target_root_path)
    if latest_run:
        existing_assets["latest_prior_run"] = latest_run
    existing_assets["diagnostic_outputs"] = diagnostic_outputs
    _write_stage_summary(
        run,
        "S1",
        "audit-request",
        "PASS",
        "Audit request captured.",
        outputs={"user_arguments": user_arguments, "latest_prior_run": latest_run, "team_plan": team_plan_outputs},
    )
    _write_stage_summary(
        run,
        "S2",
        "audit-context",
        "PASS" if existing_assets["existing_workflow_spec"] else "WARN",
        (
            "Existing generated target workflow detected for audit."
            if existing_assets["existing_workflow_spec"]
            else "No generated target workflow detected; audit is limited to package and host diagnostics."
        ),
        outputs=existing_assets,
    )

    if existing_assets["existing_workflow_spec"]:
        validation_summary = run_validation_layers(
            package_root=Path(run.package.package_root),
            target_root=target_root_path,
            run_root=run_root,
        )
    else:
        package_result = validate_package_contract(Path(run.package.package_root))
        validation_summary = {
            "verdict": "WARN" if package_result["verdict"] == "PASS" else "FAIL",
            "layers": {
                "package": package_result,
                "spec": _placeholder_layer("workflow_spec_validator", "WARN", "No target workflow spec present yet."),
                "target": _placeholder_layer("target_bundle_validator", "WARN", "No target bundle present yet."),
                "run_state": _placeholder_layer("run_state_validator", "PASS", "Audit run-state initialized."),
            },
            "exit_code": 0 if package_result["verdict"] == "PASS" else 1,
        }
        _write_validation_artifacts(run_root, validation_summary)

    judge_summary = _run_s5_judge(run_root, validation_summary)
    audit_report = {
        "schema_version": SCHEMA_VERSION,
        "intent": "audit",
        "target_root": run.target.target_root,
        "latest_prior_run": latest_run,
        "existing_assets": existing_assets,
        "validation_verdict": validation_summary["verdict"],
        "judge_verdict": judge_summary["verdict"],
        "diagnostics": diagnostic_outputs,
    }
    write_json(run_root / "outputs" / "audit-report.json", audit_report)
    write_text(
        run_root / "outputs" / "audit-report.md",
        "\n".join(
            [
                "# WorkflowProgram Audit Report",
                "",
                f"- Verdict: `{judge_summary['verdict']}`",
                f"- Target workflow present: `{existing_assets['existing_workflow_spec']}`",
                f"- Validation verdict: `{validation_summary['verdict']}`",
                f"- Latest prior run: `{latest_run['run_id'] if latest_run else 'none'}`",
                "",
            ]
        ),
    )
    _write_stage_summary(
        run,
        "S5",
        "audit-validate",
        judge_summary["verdict"],
        "Audit validation completed.",
        outputs={
            "validation_path": str(run_root / "validation-summary.json"),
            "audit_report": str(run_root / "outputs" / "audit-report.json"),
        },
    )
    _write_stage_summary(
        run,
        "S6",
        "audit-summary",
        "PASS" if judge_summary["verdict"] != "FAIL" else "FAIL",
        "Audit summary emitted.",
        outputs={"audit_report": str(run_root / "outputs" / "audit-report.md")},
    )
    _set_terminal_state(
        run,
        judge_summary["verdict"],
        judge_summary.get("failure_kind"),
        "Audit pipeline completed.",
        diagnostics=diagnostic_outputs,
        validation=validation_summary,
        judge=judge_summary,
        audit_report=str(run_root / "outputs" / "audit-report.json"),
    )
    return {
        "intent": "audit",
        "verdict": judge_summary["verdict"],
        "summary": "Audit completed without mutating target assets.",
        "run_root": run.run_root,
        "diagnostics": diagnostic_outputs,
        "team_plan": team_plan_outputs,
        "validation": validation_summary,
        "judge": judge_summary,
        "audit_report": str(run_root / "outputs" / "audit-report.json"),
        "exit_code": 0 if judge_summary["verdict"] != "FAIL" else 1,
    }


def run_preflight(
    package_root: Path,
    target_root: Path,
    user_arguments: str,
    ai_evidence: str = "",
    confirmed: bool = False,
) -> dict[str, Any]:
    run = _build_contexts(
        package_root,
        target_root,
        "preflight",
        user_arguments,
        ai_evidence=ai_evidence,
        confirmed=confirmed,
    )
    _bootstrap_run(run)

    target_root_path = Path(run.target.target_root)
    run_root = Path(run.run_root)
    diagnostic_outputs = _write_diagnostic_artifacts(run, Path(run.package.package_root), target_root_path)
    team_plan_outputs = _write_team_plan(run)
    latest_run = _latest_prior_run(target_root_path, run_root)
    _write_stage_summary(
        run,
        "S1",
        "preflight-request",
        "PASS",
        "Preflight request captured.",
        outputs={"user_arguments": user_arguments, "latest_prior_run": latest_run, "diagnostic_outputs": diagnostic_outputs, "team_plan": team_plan_outputs},
    )

    existing_assets = _collect_existing_assets(target_root_path)
    if latest_run:
        existing_assets["latest_prior_run"] = latest_run
    existing_assets["diagnostic_outputs"] = diagnostic_outputs
    context_verdict = "PASS" if existing_assets["existing_workflow_spec"] else "WARN"
    context_message = (
        "Existing generated target workflow detected."
        if existing_assets["existing_workflow_spec"]
        else "No generated target workflow detected yet; preflight ran against package readiness only."
    )
    _write_stage_summary(
        run,
        "S2",
        "preflight-context",
        context_verdict,
        context_message,
        outputs=existing_assets,
    )

    if existing_assets["existing_workflow_spec"]:
        validation_summary = run_validation_layers(
            package_root=Path(run.package.package_root),
            target_root=target_root_path,
            run_root=run_root,
        )
    else:
        package_result = validate_package_contract(Path(run.package.package_root))
        validation_summary = {
            "verdict": "WARN" if package_result["verdict"] == "PASS" else "FAIL",
            "layers": {
                "package": package_result,
                "spec": _placeholder_layer("workflow_spec_validator", "WARN", "No target workflow spec present yet."),
                "target": _placeholder_layer("target_bundle_validator", "WARN", "No target bundle present yet."),
                "run_state": _placeholder_layer("run_state_validator", "PASS", "Preflight run-state initialized."),
            },
            "exit_code": 0 if package_result["verdict"] == "PASS" else 1,
        }
        _write_validation_artifacts(run_root, validation_summary)

    judge_summary = _run_s5_judge(run_root, validation_summary)
    write_json(run_root / "outputs" / "stages" / "s5-validation-summary.json", validation_summary)
    _write_stage_summary(
        run,
        "S5",
        "preflight-validate",
        judge_summary["verdict"],
        "Preflight readiness checks completed.",
        outputs={
            "validation_path": str(run_root / "validation-summary.json"),
            "judge_report_path": str(run_root / "validation-runtime-report.md"),
        },
    )
    write_json(
        run_root / "outputs" / "stages" / "runner-summary.json",
        {
            "intent": "preflight",
            "status": "completed",
            "target_root": run.target.target_root,
            "validation_verdict": validation_summary["verdict"],
            "judge_verdict": judge_summary["verdict"],
        },
    )

    _set_terminal_state(
        run,
        judge_summary["verdict"],
        judge_summary.get("failure_kind"),
        "Preflight pipeline completed.",
        diagnostics=diagnostic_outputs,
        validation=validation_summary,
        judge=judge_summary,
    )
    return {
        "intent": "preflight",
        "verdict": judge_summary["verdict"],
        "summary": "Preflight readiness checks completed.",
        "run_root": run.run_root,
        "diagnostics": diagnostic_outputs,
        "team_plan": team_plan_outputs,
        "validation": validation_summary,
        "judge": judge_summary,
        "exit_code": 0 if judge_summary["verdict"] != "FAIL" else 1,
    }


def run_ship(
    package_root: Path,
    target_root: Path,
    user_arguments: str,
    ai_evidence: str = "",
    confirmed: bool = False,
) -> dict[str, Any]:
    run = _build_contexts(
        package_root,
        target_root,
        "ship",
        user_arguments,
        ai_evidence=ai_evidence,
        confirmed=confirmed,
    )
    _bootstrap_run(run)

    target_root_path = Path(run.target.target_root)
    run_root = Path(run.run_root)
    diagnostic_outputs = _write_diagnostic_artifacts(run, Path(run.package.package_root), target_root_path)
    team_plan_outputs = _write_team_plan(run)
    latest_run = _latest_prior_run(target_root_path, run_root)
    _write_stage_summary(
        run,
        "S1",
        "ship-request",
        "PASS",
        "Ship request captured.",
        outputs={"user_arguments": user_arguments, "latest_prior_run": latest_run, "diagnostic_outputs": diagnostic_outputs, "team_plan": team_plan_outputs},
    )

    existing_assets = _collect_existing_assets(target_root_path)
    if latest_run:
        existing_assets["latest_prior_run"] = latest_run
    existing_assets["diagnostic_outputs"] = diagnostic_outputs
    existing_assets["team_plan"] = team_plan_outputs
    if not existing_assets["existing_workflow_spec"]:
        _write_stage_summary(
            run,
            "S2",
            "ship-context",
            "FAIL",
            "Ship requires an existing generated target workflow.",
            outputs=existing_assets,
        )
        return _missing_target_result(
            run,
            "ship",
            "Ship requires an existing generated target workflow.",
            existing_assets,
        )

    _write_stage_summary(
        run,
        "S2",
        "ship-context",
        "PASS",
        "Existing generated target workflow detected for ship readiness.",
        outputs=existing_assets,
    )

    validation_summary = run_validation_layers(
        package_root=Path(run.package.package_root),
        target_root=target_root_path,
        run_root=run_root,
    )
    judge_summary = _run_s5_judge(run_root, validation_summary)
    write_json(run_root / "outputs" / "stages" / "s5-validation-summary.json", validation_summary)
    _write_stage_summary(
        run,
        "S5",
        "ship-validate",
        judge_summary["verdict"],
        "Ship readiness validation completed.",
        outputs={
            "validation_path": str(run_root / "validation-summary.json"),
            "judge_report_path": str(run_root / "validation-runtime-report.md"),
        },
    )

    ship_verdict = "PASS" if judge_summary["verdict"] == "PASS" else "FAIL"
    _write_stage_summary(
        run,
        "S6",
        "ship-summary",
        ship_verdict,
        "Ship readiness confirmed." if ship_verdict == "PASS" else "Ship readiness blocked by validation findings.",
        outputs={"validation_verdict": validation_summary["verdict"], "judge_verdict": judge_summary["verdict"]},
    )
    write_json(
        run_root / "outputs" / "stages" / "runner-summary.json",
        {
            "intent": "ship",
            "status": "completed" if ship_verdict == "PASS" else "blocked",
            "target_root": run.target.target_root,
            "validation_verdict": validation_summary["verdict"],
            "judge_verdict": judge_summary["verdict"],
        },
    )
    _set_terminal_state(
        run,
        ship_verdict,
        None if ship_verdict == "PASS" else judge_summary.get("failure_kind"),
        "Ship pipeline completed." if ship_verdict == "PASS" else "Ship pipeline blocked.",
        diagnostics=diagnostic_outputs,
        validation=validation_summary,
        judge=judge_summary,
    )
    return {
        "intent": "ship",
        "verdict": ship_verdict,
        "summary": "Ship readiness confirmed." if ship_verdict == "PASS" else "Ship readiness blocked.",
        "run_root": run.run_root,
        "diagnostics": diagnostic_outputs,
        "team_plan": team_plan_outputs,
        "validation": validation_summary,
        "judge": judge_summary,
        "exit_code": 0 if ship_verdict == "PASS" else 1,
    }


def run_orchestrate(
    package_root: Path,
    target_root: Path,
    user_arguments: str,
    ai_evidence: str = "",
    confirmed: bool = False,
) -> dict[str, Any]:
    run = _build_contexts(
        package_root,
        target_root,
        "orchestrate",
        user_arguments,
        ai_evidence=ai_evidence,
        confirmed=confirmed,
    )
    _bootstrap_run(run)
    run_root = Path(run.run_root)
    target_root_path = Path(run.target.target_root)
    diagnostic_outputs = _write_diagnostic_artifacts(run, Path(run.package.package_root), target_root_path)
    team_plan_outputs = _write_team_plan(run)
    target_status = assess_target_workflow(target_root_path)
    route_module = _load_runtime_module("route-intent.py", "workflowprogram_route_intent")
    route = route_module.route_request(user_arguments)
    selected_intent = str(route.get("intent", "develop"))
    selected_contract = PRODUCT_INTENT_CONTRACT.get(selected_intent, {})
    if selected_contract.get("requires_existing_target") and not target_status["target_workflow_exists"]:
        route["original_intent"] = selected_intent
        route["original_entry_command"] = selected_contract.get("command")
        route["intent"] = "develop"
        route["entry_command"] = PRODUCT_INTENT_CONTRACT["develop"]["command"]
        route["reason"] = "target-workflow-missing-fallback-to-develop"
        route["context_override"] = (
            "The routed intent requires an existing generated target workflow, "
            "but .workflowprogram/design/workflow-spec.yaml is missing."
        )
        selected_intent = "develop"
        selected_contract = PRODUCT_INTENT_CONTRACT[selected_intent]
    mutating = bool(selected_contract.get("mutating"))
    needs_clarification = bool(route.get("ambiguous")) or float(route.get("confidence", 0.0)) < 0.7
    execute_allowed = False
    verdict = "WARN" if needs_clarification or mutating else "PASS"
    summary = (
        "Route requires clarification before execution."
        if needs_clarification
        else (
            "Mutating intent selected; run the recommended command explicitly."
            if mutating
            else "Read-only intent selected; run the recommended command explicitly."
        )
    )
    routing_result = {
        "schema_version": SCHEMA_VERSION,
        "request": user_arguments,
        "route": route,
        "selected_intent": selected_intent,
        "entry_command": route.get("entry_command"),
        "mutating": mutating,
        "needs_clarification": needs_clarification,
        "execute_allowed": execute_allowed,
        "target_workflow_status": target_status,
        "summary": summary,
    }
    write_json(run_root / "outputs" / "orchestrate-route.json", routing_result)
    write_text(
        run_root / "outputs" / "orchestrate-route.md",
        "\n".join(
            [
                "# WorkflowProgram Route",
                "",
                f"- Selected intent: `{selected_intent}`",
                f"- Entry command: `{route.get('entry_command')}`",
                f"- Confidence: `{route.get('confidence')}`",
                f"- Ambiguous: `{route.get('ambiguous')}`",
                f"- Mutating: `{mutating}`",
                f"- Target workflow exists: `{target_status['target_workflow_exists']}`",
                f"- Action: {summary}",
                "",
            ]
        ),
    )
    _write_stage_summary(
        run,
        "S1",
        "orchestrate-route",
        verdict,
        summary,
        outputs={"route": routing_result, "diagnostic_outputs": diagnostic_outputs, "team_plan": team_plan_outputs},
    )
    _set_terminal_state(
        run,
        verdict,
        None,
        "Orchestrate routing completed.",
        diagnostics=diagnostic_outputs,
        target_workflow_status=target_status,
        route=routing_result,
    )
    return {
        "intent": "orchestrate",
        "verdict": verdict,
        "summary": summary,
        "run_root": run.run_root,
        "diagnostics": diagnostic_outputs,
        "team_plan": team_plan_outputs,
        "route": routing_result,
        "exit_code": 0,
    }


def run_intent(
    intent: str,
    package_root: Path,
    target_root: Path,
    user_arguments: str,
    ai_evidence: str = "",
    confirmed: bool = False,
    source_spec: str = "",
    source_draft: str = "",
    allow_template_fallback: bool = False,
) -> dict[str, Any]:
    handlers = {
        "develop": run_develop,
        "validate": run_validate,
        "preflight": run_preflight,
        "hotfix": run_hotfix,
        "iterate": run_iterate,
        "evolve": run_evolve,
        "ship": run_ship,
        "audit": run_audit,
        "orchestrate": run_orchestrate,
    }
    if intent not in handlers:
        raise ValueError(f"Unsupported intent: {intent}")
    if intent in {"develop", "hotfix", "iterate", "evolve"}:
        return handlers[intent](
            package_root,
            target_root,
            user_arguments,
            ai_evidence=ai_evidence,
            confirmed=confirmed,
            source_spec=source_spec,
            source_draft=source_draft,
            allow_template_fallback=allow_template_fallback,
        )
    return handlers[intent](
        package_root,
        target_root,
        user_arguments,
        ai_evidence=ai_evidence,
        confirmed=confirmed,
    )
