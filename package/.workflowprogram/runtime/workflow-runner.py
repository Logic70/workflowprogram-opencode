#!/usr/bin/env python3
"""WorkflowProgram runtime orchestration for OpenCode v2."""

from __future__ import annotations

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
    write_json,
    write_text,
    write_yaml,
)
from validation_coordinator import run_validation_layers


VALIDATORS_DIR = Path(__file__).resolve().parent / "validators"
if str(VALIDATORS_DIR) not in sys.path:
    sys.path.insert(0, str(VALIDATORS_DIR))

from workflow_spec_validator import validate_workflow_spec  # type: ignore  # noqa: E402


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
            "intent": run.intent,
            "run_id": run.run_id,
            "run_root": run.run_root,
            "verdict": "WARN",
            "failure_kind": None,
            "status": "running",
        },
    )
    _append_event(run, "RunStarted", "S0", "running", "WorkflowProgram run started")


def _build_workflow_spec(run: RunContext, request: DevelopRequest) -> dict[str, Any]:
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
        "meta": {
            "name": request.spec_name,
            "version": "1.0.0",
            "target_platform": "opencode",
            "source_design": "workflowprogram-opencode-v2",
            "complexity": request.complexity,
            "request_summary": request.summary,
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
            "validate": {
                "required_stage_slots": ["S5"],
                "optional_stage_slots": ["S6"],
            },
            "iterate": {
                "required_stage_slots": ["S6"],
                "optional_stage_slots": ["S5"],
            },
            "audit": {
                "required_stage_slots": ["S5"],
                "optional_stage_slots": ["S6"],
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

export {{ TARGET_PLUGIN_ID }}

export default async function targetWorkflowPlugin(context) {{
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


def run_develop(package_root: Path, target_root: Path, user_arguments: str) -> dict[str, Any]:
    run = _build_contexts(package_root, target_root, "develop", user_arguments)
    _bootstrap_run(run)

    request = parse_user_arguments(user_arguments, Path(run.target.target_root).name)
    _write_stage_summary(
        run,
        "S1",
        "clarify",
        "PASS",
        "Requirements normalized into a develop request.",
        outputs={"summary": request.summary},
    )

    existing_assets = {
        "existing_opencode": sorted(
            path.relative_to(Path(run.target.target_root)).as_posix()
            for path in Path(run.target.target_root).glob(".opencode/**/*")
            if path.is_file()
        ),
        "existing_workflowprogram": sorted(
            path.relative_to(Path(run.target.target_root)).as_posix()
            for path in Path(run.target.target_root).glob(".workflowprogram/**/*")
            if path.is_file()
        ),
    }
    _write_stage_summary(
        run,
        "S2",
        "context",
        "PASS",
        "Target root context scanned.",
        outputs=existing_assets,
    )

    spec = _build_workflow_spec(run, request)
    run_root = Path(run.run_root)
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
        "Workflow spec generated and validated.",
        outputs={"spec_path": str(spec_path), "spec_verdict": spec_validation["verdict"]},
    )
    if spec_validation["exit_code"] != 0:
        _set_terminal_state(run, "FAIL", "design", "Workflow spec validation failed", spec_validation=spec_validation)
        return {
            "intent": "develop",
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
        "Target bundle generated and managed apply executed.",
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
            "intent": "develop",
            "verdict": "FAIL",
            "summary": "Managed apply detected conflicts.",
            "run_root": run.run_root,
            "managed_apply": apply_result,
            "exit_code": 2,
        }

    write_json(
        run_root / "outputs" / "stages" / "runner-summary.json",
        {
            "intent": "develop",
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
    write_json(run_root / "outputs" / "stages" / "s5-validation-summary.json", validation_summary)
    _write_stage_summary(
        run,
        "S5",
        "validate",
        validation_summary["verdict"],
        "Layered validation completed.",
        outputs={"validation_path": str(run_root / "validation-summary.json")},
    )

    lessons_payload = {
        "new_constraints": [],
        "notes": "No automatic rule updates are emitted in v1.",
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
            "intent": "develop",
            "status": "completed",
            "generated_target_root": run.target.target_root,
            "managed_apply_status": apply_result["status"],
            "validation_verdict": validation_summary["verdict"],
        },
    )

    final_verdict = aggregate_verdicts([validation_summary["verdict"]])
    failure_kind = None if final_verdict != "FAIL" else "implementation"
    _set_terminal_state(
        run,
        final_verdict,
        failure_kind,
        "Develop pipeline completed.",
        managed_apply=apply_result,
        validation=validation_summary,
    )
    return {
        "intent": "develop",
        "verdict": final_verdict,
        "summary": "Target workflow bundle generated and applied.",
        "run_root": run.run_root,
        "spec_path": str(Path(run.target.design_root) / "workflow-spec.yaml"),
        "managed_apply": apply_result,
        "validation": validation_summary,
        "exit_code": 0 if final_verdict != "FAIL" else 1,
    }


def run_validate(package_root: Path, target_root: Path, user_arguments: str) -> dict[str, Any]:
    run = _build_contexts(package_root, target_root, "validate", user_arguments)
    _bootstrap_run(run)

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
        outputs={"target_root": run.target.target_root},
    )
    validation_summary = run_validation_layers(
        package_root=Path(run.package.package_root),
        target_root=Path(run.target.target_root),
        run_root=Path(run.run_root),
    )
    write_json(Path(run.run_root) / "outputs" / "stages" / "s5-validation-summary.json", validation_summary)
    write_json(
        Path(run.run_root) / "outputs" / "stages" / "runner-summary.json",
        {
            "intent": "validate",
            "status": "completed",
            "target_root": run.target.target_root,
            "validation_verdict": validation_summary["verdict"],
        },
    )

    _set_terminal_state(
        run,
        validation_summary["verdict"],
        None if validation_summary["verdict"] != "FAIL" else "implementation",
        "Validate pipeline completed.",
        validation=validation_summary,
    )
    return {
        "intent": "validate",
        "verdict": validation_summary["verdict"],
        "summary": "Layered validation completed.",
        "run_root": run.run_root,
        "validation": validation_summary,
        "exit_code": 0 if validation_summary["verdict"] != "FAIL" else 1,
    }
