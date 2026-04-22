#!/usr/bin/env python3
"""Workflow spec validator for WorkflowProgram OpenCode targets."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


RUNTIME_DIR = Path(__file__).resolve().parents[1]
if str(RUNTIME_DIR) not in sys.path:
    sys.path.insert(0, str(RUNTIME_DIR))

from runtime_common import (  # noqa: E402
    FAILURE_KINDS,
    MANDATORY_DESIGN_FILES,
    MANDATORY_RUNTIME_FILES,
    PACKAGE_COMMAND_PREFIX,
    PACKAGE_PLUGIN_FILE,
    PACKAGE_PLUGIN_ID,
    STAGE_SLOTS,
    derive_expected_target_files,
    read_yaml,
    registry_commands,
    registry_plugins,
)


REQUIRED_TOP_KEYS = {
    "meta",
    "stages",
    "intent_flows",
    "registry",
    "outputs",
    "runtime_contract",
    "generated_runtime_contract",
    "test_contract",
}
REQUIRED_META_KEYS = {"name", "version", "target_platform", "source_design", "complexity"}
REQUIRED_RUNTIME_KEYS = {"write_boundaries", "required_evidence", "failure_kinds", "environment_skip"}
REQUIRED_GENERATED_RUNTIME_KEYS = {
    "runtime_root",
    "design_spec_path",
    "entry_script",
    "runner_script",
    "state_validator_script",
    "runtime_manifest",
    "run_root_dir",
    "mode",
    "runtime_capabilities",
}


def _check(check_id: str, passed: bool, detail: str, category: str) -> dict[str, Any]:
    return {
        "id": check_id,
        "passed": passed,
        "detail": detail,
        "category": category,
    }


def validate_workflow_spec(spec_path: Path) -> dict[str, Any]:
    resolved = spec_path.resolve()
    checks: list[dict[str, Any]] = []

    if not resolved.exists():
        return {
            "validator": "workflow_spec_validator",
            "spec_path": str(resolved),
            "verdict": "FAIL",
            "summary": "workflow-spec.yaml is missing",
            "checks": [_check("SPEC-01", False, "workflow-spec.yaml not found", "design")],
            "exit_code": 1,
        }

    try:
        spec = read_yaml(resolved)
    except Exception as exc:
        return {
            "validator": "workflow_spec_validator",
            "spec_path": str(resolved),
            "verdict": "FAIL",
            "summary": f"workflow-spec.yaml is not valid YAML: {exc}",
            "checks": [_check("SPEC-01", False, f"yaml parse failed: {exc}", "design")],
            "exit_code": 1,
        }

    checks.append(_check("SPEC-01", isinstance(spec, dict), "workflow-spec.yaml parsed", "design"))
    spec = spec if isinstance(spec, dict) else {}

    missing_top = sorted(REQUIRED_TOP_KEYS - set(spec.keys()))
    meta = spec.get("meta", {}) if isinstance(spec.get("meta"), dict) else {}
    missing_meta = sorted(REQUIRED_META_KEYS - set(meta.keys()))
    checks.append(
        _check(
            "SPEC-02",
            not missing_top and not missing_meta,
            f"missing_top={missing_top} missing_meta={missing_meta}",
            "design",
        )
    )

    stage_slots = {
        str(stage.get("stage_slot", "")).strip()
        for stage in spec.get("stages", [])
        if isinstance(stage, dict)
    }
    intent_flows = spec.get("intent_flows", {}) if isinstance(spec.get("intent_flows"), dict) else {}
    flow_ok = bool(stage_slots) and stage_slots.issubset(set(STAGE_SLOTS))
    for flow in intent_flows.values():
        if not isinstance(flow, dict):
            flow_ok = False
            continue
        required_slots = flow.get("required_stage_slots", [])
        if not isinstance(required_slots, list):
            flow_ok = False
            continue
        if any(slot not in stage_slots for slot in required_slots):
            flow_ok = False
    checks.append(_check("SPEC-03", flow_ok, f"stage_slots={sorted(stage_slots)}", "design"))

    runtime_contract = (
        spec.get("runtime_contract", {}) if isinstance(spec.get("runtime_contract"), dict) else {}
    )
    failure_kinds = runtime_contract.get("failure_kinds", [])
    failure_ok = isinstance(failure_kinds, list) and set(FAILURE_KINDS).issubset(set(failure_kinds))
    checks.append(
        _check(
            "SPEC-04",
            failure_ok,
            f"failure_kinds={failure_kinds}",
            "design",
        )
    )

    write_boundaries = (
        runtime_contract.get("write_boundaries", {})
        if isinstance(runtime_contract.get("write_boundaries"), dict)
        else {}
    )
    target_allow = write_boundaries.get("target_root_allow", [])
    run_allow = write_boundaries.get("run_root_allow", [])
    deny = write_boundaries.get("deny", [])
    boundaries_ok = (
        set(REQUIRED_RUNTIME_KEYS).issubset(set(runtime_contract.keys()))
        and isinstance(target_allow, list)
        and isinstance(run_allow, list)
        and isinstance(deny, list)
        and ".workflowprogram/design/**" in target_allow
        and ".workflowprogram/runtime/**" in target_allow
    )
    checks.append(
        _check(
            "SPEC-05",
            boundaries_ok,
            f"target_root_allow={target_allow}",
            "design",
        )
    )

    generated_runtime_contract = (
        spec.get("generated_runtime_contract", {})
        if isinstance(spec.get("generated_runtime_contract"), dict)
        else {}
    )
    deliverables = derive_expected_target_files(spec)
    deliverables_ok = (
        set(REQUIRED_GENERATED_RUNTIME_KEYS).issubset(set(generated_runtime_contract.keys()))
        and all(path in deliverables for path in MANDATORY_DESIGN_FILES)
        and all(path in deliverables for path in MANDATORY_RUNTIME_FILES)
    )
    checks.append(
        _check(
            "SPEC-06",
            deliverables_ok,
            f"deliverables={deliverables}",
            "design",
        )
    )

    plugins = registry_plugins(spec)
    plugin_optional_ok = all(
        plugin.get("file", "").startswith(".opencode/plugins/")
        and plugin.get("file") != f".opencode/plugins/{PACKAGE_PLUGIN_FILE}"
        and plugin.get("plugin_id") != PACKAGE_PLUGIN_ID
        for plugin in plugins
    )
    checks.append(
        _check(
            "SPEC-07",
            plugin_optional_ok,
            f"plugins={plugins}",
            "design",
        )
    )

    package_refs = []
    serialized = json.dumps(spec, ensure_ascii=True)
    for marker in ("WP_PACKAGE_ROOT", PACKAGE_PLUGIN_ID, f".opencode/plugins/{PACKAGE_PLUGIN_FILE}"):
        if marker in serialized:
            package_refs.append(marker)
    checks.append(
        _check(
            "SPEC-08",
            not package_refs,
            f"package_refs={package_refs}",
            "layering",
        )
    )

    commands = registry_commands(spec)
    command_names_ok = all(
        not str(item.get("name", "")).startswith(PACKAGE_COMMAND_PREFIX)
        and not Path(str(item.get("file", ""))).stem.startswith(PACKAGE_COMMAND_PREFIX)
        for item in commands
    )
    checks.append(
        _check(
            "SPEC-09",
            command_names_ok,
            f"commands={commands}",
            "namespace_conflict",
        )
    )

    failed = [check for check in checks if not check["passed"]]
    verdict = "PASS" if not failed else "FAIL"
    return {
        "validator": "workflow_spec_validator",
        "spec_path": str(resolved),
        "verdict": verdict,
        "summary": "Workflow spec validated" if verdict == "PASS" else "Workflow spec validation failed",
        "checks": checks,
        "exit_code": 0 if verdict == "PASS" else 1,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate workflow spec")
    parser.add_argument("--spec", required=True)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = validate_workflow_spec(Path(args.spec))
    if args.json:
        json.dump(result, sys.stdout, indent=2, ensure_ascii=True)
        sys.stdout.write("\n")
    else:
        sys.stdout.write(f"{result['verdict']} spec={result['spec_path']}\n")
        for check in result["checks"]:
            status = "PASS" if check["passed"] else "FAIL"
            sys.stdout.write(f"{status} {check['id']} {check['detail']}\n")
    return result["exit_code"]


if __name__ == "__main__":
    raise SystemExit(main())
