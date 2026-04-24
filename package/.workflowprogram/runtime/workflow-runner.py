#!/usr/bin/env python3
"""WorkflowProgram runtime orchestration for OpenCode v2."""

from __future__ import annotations

import importlib.util
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from managed_assets_lib import apply_staged
from runtime_common import (
    FAILURE_KINDS,
    MANDATORY_DESIGN_FILES,
    MANDATORY_RUNTIME_FILES,
    MANDATORY_TARGET_FILES,
    PRODUCT_INTENT_CONTRACT,
    SCHEMA_VERSION,
    STAGE_SLOTS,
    DevelopRequest,
    aggregate_verdicts,
    append_jsonl,
    detect_package_layout,
    ensure_dir,
    iso_now,
    make_run_id,
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
    package: PackageContext
    target: TargetContext


def _build_contexts(package_root: Path, target_root: Path, intent: str, user_arguments: str) -> RunContext:
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
    present_required = [path for path in MANDATORY_TARGET_FILES if (target_root / path).is_file()]
    missing_required = [path for path in MANDATORY_TARGET_FILES if not (target_root / path).is_file()]
    return {
        "existing_opencode": existing_opencode,
        "existing_workflowprogram": existing_workflowprogram,
        "present_required_target_files": present_required,
        "missing_required_target_files": missing_required,
        "existing_workflow_spec": (target_root / ".workflowprogram" / "design" / "workflow-spec.yaml").is_file(),
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
        return {
            "run_id": candidate.name,
            "run_root": str(candidate),
            "verdict": state.get("verdict"),
            "status": state.get("status"),
            "message": state.get("message"),
            "validation_verdict": validation.get("verdict"),
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
) -> dict[str, str]:
    clarification_root = Path(run.run_root) / "outputs" / "clarification"
    ensure_dir(clarification_root)

    clarification_record = {
        "intent": run.intent,
        "target_root": run.target.target_root,
        "request_summary": request.summary,
        "raw_user_arguments": request.raw,
        "normalized_spec_name": request.spec_name,
        "complexity": request.complexity,
        "latest_prior_run": latest_run,
        "generated_at": iso_now(),
    }
    open_questions = {
        "blocking": [],
        "non_blocking": [],
        "summary": "No explicit clarification round was required for this direct command invocation.",
    }
    readiness_report = {
        "ready": True,
        "clarification_mode": "direct-command",
        "blocking_open_questions": 0,
        "readback_confirmed": False,
        "reason": "Explicit package command invocation produced a normalized develop request.",
    }
    assumption_log = "\n".join(
        [
            "# Assumption Log",
            "",
            "- The direct `/wp-develop` invocation is treated as an explicit intent selection.",
            "- No additional clarification questions were required for this run.",
            "",
        ]
    )

    clarification_record_path = clarification_root / "clarification-record.json"
    open_questions_path = clarification_root / "open-questions.json"
    readiness_report_path = clarification_root / "design-readiness-report.json"
    assumption_log_path = clarification_root / "assumption-log.md"
    write_json(clarification_record_path, clarification_record)
    write_json(open_questions_path, open_questions)
    write_json(readiness_report_path, readiness_report)
    write_text(assumption_log_path, assumption_log)

    return {
        "clarification_record": str(clarification_record_path),
        "open_questions": str(open_questions_path),
        "design_readiness_report": str(readiness_report_path),
        "assumption_log": str(assumption_log_path),
    }


def _load_clarification_package(artifact_paths: dict[str, str]) -> dict[str, Any]:
    clarification_record = read_json(Path(artifact_paths["clarification_record"]))
    open_questions = read_json(Path(artifact_paths["open_questions"]))
    design_readiness = read_json(Path(artifact_paths["design_readiness_report"]))
    assumption_log = Path(artifact_paths["assumption_log"]).read_text(encoding="utf-8")
    return {
        "clarification_record": clarification_record,
        "open_questions": open_questions,
        "design_readiness_report": design_readiness,
        "assumption_log": assumption_log,
    }


def _load_runtime_module(script_name: str, module_name: str):
    script_path = Path(__file__).resolve().parent / script_name
    spec = importlib.util.spec_from_file_location(module_name, script_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load runtime module from {script_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


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
    write_json(team_plan_path, team_plan)
    return {"team_plan": str(team_plan_path)}


def _build_workflow_spec(
    run: RunContext,
    request: DevelopRequest,
    clarification_package: dict[str, Any] | None,
) -> dict[str, Any]:
    required_outputs = list(MANDATORY_DESIGN_FILES + MANDATORY_RUNTIME_FILES)
    required_outputs.append(".workflowprogram/managed-files.json")

    registry_commands: list[dict[str, Any]] = []
    registry_plugins: list[dict[str, Any]] = []
    target_allow = [
        ".workflowprogram/design/**",
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
            }
        )
        required_outputs.append(plugin_file)
        target_allow.append(".opencode/plugins/**")

    runtime_capabilities = ["state_transitions", "run_state_validation"]
    if registry_commands:
        runtime_capabilities.append("target_command_delivery")
    if registry_plugins:
        runtime_capabilities.append("target_plugin_bridge")

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
        "stages": [
            {"id": "clarify", "stage_slot": "S1", "name": "Requirement Clarification", "pattern": "Explore"},
            {"id": "context", "stage_slot": "S2", "name": "Target Context Review", "pattern": "Explore"},
            {"id": "design", "stage_slot": "S3", "name": "Workflow Spec Design", "pattern": "Specialized Agent"},
            {"id": "generate", "stage_slot": "S4", "name": "Target Bundle Generation", "pattern": "Sequential"},
            {"id": "validate", "stage_slot": "S5", "name": "Layered Validation", "pattern": "Test-Driven"},
            {"id": "lessons", "stage_slot": "S6", "name": "Constraint Closure", "pattern": "Sequential"},
        ],
        "intent_flows": {
            "develop": {
                "required_stage_slots": list(STAGE_SLOTS),
                "optional_stage_slots": [],
            },
            "preflight": {
                "required_stage_slots": ["S2", "S5"],
                "optional_stage_slots": ["S6"],
            },
            "hotfix": {
                "required_stage_slots": ["S2", "S3", "S4", "S5"],
                "optional_stage_slots": ["S6"],
            },
            "validate": {
                "required_stage_slots": ["S5"],
                "optional_stage_slots": ["S6"],
            },
            "iterate": {
                "required_stage_slots": ["S2", "S3", "S4", "S5", "S6"],
                "optional_stage_slots": [],
            },
            "ship": {
                "required_stage_slots": ["S5", "S6"],
                "optional_stage_slots": [],
            },
            "audit": {
                "required_stage_slots": ["S5"],
                "optional_stage_slots": ["S6"],
            },
            "evolve": {
                "required_stage_slots": ["S2", "S3", "S4", "S5", "S6"],
                "optional_stage_slots": [],
            },
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
                    "workflow-spec.yaml",
                    "workflow-view.md",
                    "workflow-lowlevel.md",
                    "outputs/**",
                ],
                "deny": ["**/.git/**", "**/node_modules/**"],
            },
            "required_evidence": [
                "context.json",
                "state.json",
                "events.jsonl",
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
                "required_stage_slots": list(STAGE_SLOTS),
                "failure_recovery": {
                    "design": "S3",
                    "implementation": "S4",
                    "conflict": "S4",
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
    lines = [
        "# Target Workflow View",
        "",
        f"- Name: `{spec['meta']['name']}`",
        f"- Platform: `{spec['meta']['target_platform']}`",
        f"- Complexity: `{spec['meta']['complexity']}`",
        f"- Request: {request.summary}",
        "",
        "## Intent Flows",
        "",
    ]
    for intent, flow in spec["intent_flows"].items():
        lines.append(f"- `{intent}` -> {', '.join(flow['required_stage_slots'])}")
    lines.extend(["", "## Deliverables", ""])
    for path in spec["outputs"]["required"]:
        lines.append(f"- `{path}`")
    return "\n".join(lines) + "\n"


def _build_lowlevel_markdown(spec: dict[str, Any], request: DevelopRequest) -> str:
    command_mode = "enabled" if spec["registry"]["commands"] else "disabled"
    plugin_mode = "enabled" if spec["registry"]["plugins"] else "disabled"
    lines = [
        "# Target Workflow LowLevel Guide",
        "",
        "## Summary",
        "",
        f"- Request: {request.summary}",
        f"- Target commands: {command_mode}",
        f"- Target plugins: {plugin_mode}",
        "",
        "## Runtime Contract",
        "",
        "- Writes only under target `.workflowprogram/*` and spec-selected `.opencode/*`.",
        "- Managed apply rejects unmanaged overwrite and preserves conflict copies.",
        "- Validation is layered: package, spec, target, run-state.",
        "",
        "## Required Files",
        "",
    ]
    for path in spec["outputs"]["required"]:
        lines.append(f"- `{path}`")
    return "\n".join(lines) + "\n"


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


def _target_plugin_source(plugin_id: str, spec_name: str) -> str:
    return f"""const TARGET_PLUGIN_ID = "{plugin_id}"

export const TargetWorkflowPlugin = async (context) => {{
  return {{
    "tool.execute.after": async (input, output) => {{
      if (input?.tool !== "bash") {{
        return
      }}
      await context?.client?.app?.log?.({{
        body: {{
          service: TARGET_PLUGIN_ID,
          level: output?.exitCode === 0 ? "info" : "warn",
          message: "Generated target workflow command executed",
          extra: {{
            workflow: "{spec_name}",
            exitCode: output?.exitCode ?? null,
          }},
        }},
      }})
    }},
  }}
}}
"""


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


def _build_candidate_bundle(run: RunContext, spec: dict[str, Any], view_text: str, lowlevel_text: str) -> Path:
    run_root = Path(run.run_root)
    candidate_root = run_root / "outputs" / "candidate"
    design_root = candidate_root / ".workflowprogram" / "design"
    runtime_root = candidate_root / ".workflowprogram" / "runtime"
    ensure_dir(design_root)
    ensure_dir(runtime_root)

    write_yaml(design_root / "workflow-spec.yaml", spec)
    write_text(design_root / "workflow-view.md", view_text)
    write_text(design_root / "workflow-lowlevel.md", lowlevel_text)

    spec_name = spec["meta"]["name"]
    write_text(runtime_root / "workflow-entry.py", _target_runtime_entry(spec_name))
    write_text(runtime_root / "workflow-runner.py", _target_runtime_runner(spec_name))
    write_text(runtime_root / "validate-run-state.py", _target_runtime_validator(spec_name))
    write_json(runtime_root / "runtime-manifest.json", _runtime_manifest(spec))

    for command in spec["registry"]["commands"]:
        command_path = candidate_root / command["file"]
        write_text(command_path, _target_command_markdown(command["name"], spec_name))

    for plugin in spec["registry"]["plugins"]:
        plugin_path = candidate_root / plugin["file"]
        write_text(plugin_path, _target_plugin_source(plugin["plugin_id"], spec_name))

    return candidate_root


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


def _run_mutation_intent(
    intent: str,
    package_root: Path,
    target_root: Path,
    user_arguments: str,
    *,
    require_existing_spec: bool,
) -> dict[str, Any]:
    run = _build_contexts(package_root, target_root, intent, user_arguments)
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
    request_outputs: dict[str, Any] = {"summary": request.summary, "team_plan": team_plan_outputs}
    if inherited_identity:
        request_outputs["inherited_identity"] = inherited_identity
    if latest_run:
        request_outputs["latest_prior_run"] = latest_run
    clarification_package: dict[str, Any] | None = None
    if intent == "develop":
        clarification_paths = _write_clarification_package(run, request, latest_run)
        clarification_package = _load_clarification_package(clarification_paths)
        request_outputs["clarification_package"] = clarification_paths
        request_outputs["clarification_consumed"] = {
            "summary": clarification_package["open_questions"].get("summary"),
            "ready": clarification_package["design_readiness_report"].get("ready"),
            "blocking_open_questions": clarification_package["design_readiness_report"].get(
                "blocking_open_questions"
            ),
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

    spec = _build_workflow_spec(run, request, clarification_package)
    spec["meta"]["source_intent"] = intent
    spec_path = run_root / "workflow-spec.yaml"
    view_path = run_root / "workflow-view.md"
    lowlevel_path = run_root / "workflow-lowlevel.md"
    write_yaml(spec_path, spec)
    write_text(view_path, _build_view_markdown(spec, request))
    write_text(lowlevel_path, _build_lowlevel_markdown(spec, request))
    spec_validation = validate_workflow_spec(spec_path)
    _write_stage_summary(
        run,
        "S3",
        "design",
        spec_validation["verdict"],
        f"Workflow spec generated and validated for `{intent}`.",
        outputs={
            "spec_path": str(spec_path),
            "spec_verdict": spec_validation["verdict"],
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
        view_path.read_text(encoding="utf-8"),
        lowlevel_path.read_text(encoding="utf-8"),
    )
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
        },
    )

    lessons_payload = {
        "new_constraints": [],
        "notes": f"No automatic rule updates are emitted for `{intent}` in v1.",
    }
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
    failure_kind = judge_summary.get("failure_kind")
    _set_terminal_state(
        run,
        final_verdict,
        failure_kind,
        f"{intent.capitalize()} pipeline completed.",
        managed_apply=apply_result,
        diagnostics=diagnostic_outputs,
        validation=validation_summary,
        judge=judge_summary,
    )
    summary_by_intent = {
        "develop": "Target workflow bundle generated and applied.",
        "hotfix": "Existing target workflow updated through the managed hotfix flow.",
        "iterate": "Existing target workflow iterated and reapplied.",
        "evolve": "Existing target workflow evolved through managed apply.",
    }
    return {
        "intent": intent,
        "verdict": final_verdict,
        "summary": summary_by_intent[intent],
        "run_root": run.run_root,
        "spec_path": str(Path(run.target.design_root) / "workflow-spec.yaml"),
        "managed_apply": apply_result,
        "diagnostics": diagnostic_outputs,
        "validation": validation_summary,
        "judge": judge_summary,
        "exit_code": 0 if final_verdict != "FAIL" else 1,
    }


def run_develop(package_root: Path, target_root: Path, user_arguments: str) -> dict[str, Any]:
    return _run_mutation_intent(
        "develop",
        package_root,
        target_root,
        user_arguments,
        require_existing_spec=False,
    )


def run_hotfix(package_root: Path, target_root: Path, user_arguments: str) -> dict[str, Any]:
    return _run_mutation_intent(
        "hotfix",
        package_root,
        target_root,
        user_arguments,
        require_existing_spec=True,
    )


def run_iterate(package_root: Path, target_root: Path, user_arguments: str) -> dict[str, Any]:
    return _run_mutation_intent(
        "iterate",
        package_root,
        target_root,
        user_arguments,
        require_existing_spec=True,
    )


def run_evolve(package_root: Path, target_root: Path, user_arguments: str) -> dict[str, Any]:
    return _run_mutation_intent(
        "evolve",
        package_root,
        target_root,
        user_arguments,
        require_existing_spec=True,
    )


def run_validate(package_root: Path, target_root: Path, user_arguments: str) -> dict[str, Any]:
    run = _build_contexts(package_root, target_root, "validate", user_arguments)
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
        validation=validation_summary,
        judge=judge_summary,
    )
    return {
        "intent": "validate",
        "verdict": judge_summary["verdict"],
        "summary": "Layered validation completed.",
        "run_root": run.run_root,
        "diagnostics": diagnostic_outputs,
        "validation": validation_summary,
        "judge": judge_summary,
        "exit_code": 0 if judge_summary["verdict"] != "FAIL" else 1,
    }


def run_audit(package_root: Path, target_root: Path, user_arguments: str) -> dict[str, Any]:
    run = _build_contexts(package_root, target_root, "audit", user_arguments)
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
        "validation": validation_summary,
        "judge": judge_summary,
        "audit_report": str(run_root / "outputs" / "audit-report.json"),
        "exit_code": 0 if judge_summary["verdict"] != "FAIL" else 1,
    }


def run_preflight(package_root: Path, target_root: Path, user_arguments: str) -> dict[str, Any]:
    run = _build_contexts(package_root, target_root, "preflight", user_arguments)
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
        "validation": validation_summary,
        "judge": judge_summary,
        "exit_code": 0 if judge_summary["verdict"] != "FAIL" else 1,
    }


def run_ship(package_root: Path, target_root: Path, user_arguments: str) -> dict[str, Any]:
    run = _build_contexts(package_root, target_root, "ship", user_arguments)
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
        "validation": validation_summary,
        "judge": judge_summary,
        "exit_code": 0 if ship_verdict == "PASS" else 1,
    }


def run_orchestrate(package_root: Path, target_root: Path, user_arguments: str) -> dict[str, Any]:
    run = _build_contexts(package_root, target_root, "orchestrate", user_arguments)
    _bootstrap_run(run)
    run_root = Path(run.run_root)
    diagnostic_outputs = _write_diagnostic_artifacts(run, Path(run.package.package_root), Path(run.target.target_root))
    team_plan_outputs = _write_team_plan(run)
    route_module = _load_runtime_module("route-intent.py", "workflowprogram_route_intent")
    route = route_module.route_request(user_arguments)
    selected_intent = str(route.get("intent", "develop"))
    selected_contract = PRODUCT_INTENT_CONTRACT.get(selected_intent, {})
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
        route=routing_result,
    )
    return {
        "intent": "orchestrate",
        "verdict": verdict,
        "summary": summary,
        "run_root": run.run_root,
        "diagnostics": diagnostic_outputs,
        "route": routing_result,
        "exit_code": 0,
    }


def run_intent(intent: str, package_root: Path, target_root: Path, user_arguments: str) -> dict[str, Any]:
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
    return handlers[intent](package_root, target_root, user_arguments)
