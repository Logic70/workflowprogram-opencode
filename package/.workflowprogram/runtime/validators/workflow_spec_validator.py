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
    PRODUCT_INTENT_CONTRACT,
    SCHEMA_VERSION,
    derive_expected_target_files,
    read_yaml,
    registry_commands,
    registry_plugins,
)
from error_codes import code_for, remediation_for  # noqa: E402


REQUIRED_TOP_KEYS = {
    "meta",
    "nodes",
    "transitions",
    "templates",
    "intent_routes",
    "context_contract",
    "registry",
    "outputs",
    "runtime_contract",
    "generated_runtime_contract",
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
ALLOWED_TARGET_PLUGIN_HOOK_EVENTS = {"event", "tool.execute.before", "tool.execute.after"}


def _check(check_id: str, passed: bool, detail: str, category: str) -> dict[str, Any]:
    return {
        "id": check_id,
        "passed": passed,
        "detail": detail,
        "category": category,
        "error_code": None if passed else code_for(category, check_id),
        "remediation": None if passed else remediation_for(category),
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

    nodes = spec.get("nodes", []) if isinstance(spec.get("nodes"), list) else []
    node_ids = [
        str(node.get("id", "")).strip()
        for node in nodes
        if isinstance(node, dict)
    ]
    unique_node_ids = set(node_ids)
    node_schema_ok = bool(node_ids) and len(node_ids) == len(unique_node_ids)
    for node in nodes:
        if not isinstance(node, dict):
            node_schema_ok = False
            continue
        required_node_keys = {"id", "name", "purpose", "inputs", "outputs", "preconditions", "postconditions"}
        if not required_node_keys.issubset(set(node.keys())):
            node_schema_ok = False
        for list_key in ("inputs", "outputs", "preconditions", "postconditions"):
            if not isinstance(node.get(list_key), list):
                node_schema_ok = False
    checks.append(
        _check(
            "SPEC-03",
            node_schema_ok,
            f"node_ids={node_ids}",
            "design",
        )
    )

    transitions = spec.get("transitions", []) if isinstance(spec.get("transitions"), list) else []
    transition_schema_ok = bool(transitions) and bool(unique_node_ids)
    outgoing: dict[str, set[str]] = {node_id: set() for node_id in unique_node_ids}
    incoming: dict[str, set[str]] = {node_id: set() for node_id in unique_node_ids}
    for transition in transitions:
        if not isinstance(transition, dict):
            transition_schema_ok = False
            continue
        source = str(transition.get("from", "")).strip()
        target = str(transition.get("to", "")).strip()
        if source not in unique_node_ids or target not in unique_node_ids:
            transition_schema_ok = False
            continue
        if not str(transition.get("kind", "")).strip():
            transition_schema_ok = False
        outgoing[source].add(target)
        incoming[target].add(source)
    entry_nodes = sorted(node_id for node_id, sources in incoming.items() if not sources)
    reachable: set[str] = set()
    stack = list(entry_nodes)
    while stack:
        current = stack.pop()
        if current in reachable:
            continue
        reachable.add(current)
        stack.extend(sorted(outgoing.get(current, set()) - reachable))
    transition_graph_ok = transition_schema_ok and bool(entry_nodes) and reachable == unique_node_ids
    checks.append(
        _check(
            "SPEC-11",
            transition_graph_ok,
            f"entry_nodes={entry_nodes} reachable={sorted(reachable)} node_ids={sorted(unique_node_ids)}",
            "design",
        )
    )

    templates = spec.get("templates", []) if isinstance(spec.get("templates"), list) else []
    template_ids = set()
    template_by_id: dict[str, dict[str, Any]] = {}
    template_ok = isinstance(templates, list)
    for template in templates:
        if isinstance(template, str):
            template_ids.add(template)
            continue
        if not isinstance(template, dict):
            template_ok = False
            continue
        template_id = str(template.get("id", "")).strip()
        if not template_id:
            template_ok = False
        template_ids.add(template_id)
        template_by_id[template_id] = template
        expanded_nodes = template.get("expanded_nodes", [])
        if expanded_nodes and (
            not isinstance(expanded_nodes, list)
            or any(str(node_id) not in unique_node_ids for node_id in expanded_nodes)
        ):
            template_ok = False
    node_template_refs = {
        str(template_ref)
        for node in nodes
        if isinstance(node, dict)
        for template_ref in (node.get("templates", []) if isinstance(node.get("templates", []), list) else [])
    }
    missing_template_refs = sorted(node_template_refs - template_ids)
    checks.append(
        _check(
            "SPEC-12",
            template_ok and not missing_template_refs,
            f"templates={sorted(template_ids)} missing_refs={missing_template_refs}",
            "design",
        )
    )

    intent_routes = spec.get("intent_routes", {}) if isinstance(spec.get("intent_routes"), dict) else {}
    supported_spec_flows = {
        intent for intent, contract in PRODUCT_INTENT_CONTRACT.items() if contract.get("spec_flow")
    }
    route_names_ok = set(intent_routes).issubset(supported_spec_flows)
    route_ok = bool(intent_routes) and route_names_ok
    for route in intent_routes.values():
        if not isinstance(route, dict):
            route_ok = False
            continue
        entry_node = str(route.get("entry_node", "")).strip()
        terminal_nodes = route.get("terminal_nodes", [])
        failure_nodes = route.get("failure_nodes", [])
        path = route.get("path", [])
        route_nodes = [entry_node]
        if not entry_node:
            route_ok = False
        for values in (terminal_nodes, failure_nodes, path):
            if not isinstance(values, list):
                route_ok = False
                continue
            route_nodes.extend(str(value).strip() for value in values)
        if any(node_id and node_id not in unique_node_ids for node_id in route_nodes):
            route_ok = False
    checks.append(
        _check(
            "SPEC-13",
            route_ok,
            f"intent_routes={sorted(intent_routes)} supported={sorted(supported_spec_flows)}",
            "design",
        )
    )

    legacy_fixed_slot_keys = sorted(key for key in ("stages", "intent_flows") if key in spec)
    legacy_fixed_slot_markers = []
    serialized = json.dumps(spec, ensure_ascii=True)
    for marker in ("stage_slot", "required_stage_slots", "optional_stage_slots"):
        if marker in serialized:
            legacy_fixed_slot_markers.append(marker)
    checks.append(
        _check(
            "SPEC-14",
            not legacy_fixed_slot_keys and not legacy_fixed_slot_markers,
            f"legacy_keys={legacy_fixed_slot_keys} legacy_markers={legacy_fixed_slot_markers}",
            "design",
        )
    )

    context_contract = (
        spec.get("context_contract", {}) if isinstance(spec.get("context_contract"), dict) else {}
    )
    context_required_keys = {"shared_inputs", "shared_outputs", "authoritative_sources", "derived_data"}
    context_ok = context_required_keys.issubset(set(context_contract.keys()))
    for key in context_required_keys:
        if not isinstance(context_contract.get(key), list):
            context_ok = False
    checks.append(
        _check(
            "SPEC-15",
            context_ok,
            f"context_keys={sorted(context_contract.keys())}",
            "design",
        )
    )

    self_iteration_selected = "self-iteration-loop" in template_ids
    self_iteration_template = template_by_id.get("self-iteration-loop")
    self_iteration_ok = True
    self_iteration_detail = "not selected"
    if self_iteration_selected and self_iteration_template is None:
        self_iteration_ok = False
        self_iteration_detail = "self-iteration-loop must be a template object with max_attempts and stop_conditions"
    elif self_iteration_template is not None:
        max_attempts = self_iteration_template.get("max_attempts")
        stop_conditions = self_iteration_template.get("stop_conditions")
        route_failure_nodes = {
            str(node_id).strip()
            for route in intent_routes.values()
            if isinstance(route, dict)
            for node_id in (route.get("failure_nodes", []) if isinstance(route.get("failure_nodes", []), list) else [])
        }
        route_terminal_nodes = {
            str(node_id).strip()
            for route in intent_routes.values()
            if isinstance(route, dict)
            for node_id in (route.get("terminal_nodes", []) if isinstance(route.get("terminal_nodes", []), list) else [])
        }
        generation_nodes = {
            node_id
            for node_id, node in zip(node_ids, nodes)
            if isinstance(node, dict)
            and (
                "generate" in node_id
                or "repair" in node_id
                or "candidate_bundle" in {str(output) for output in node.get("outputs", []) if isinstance(node.get("outputs", []), list)}
            )
        }
        retry_ok = any(
            isinstance(transition, dict)
            and str(transition.get("kind", "")).strip() == "retry"
            and str(transition.get("from", "")).strip() in route_failure_nodes
            and str(transition.get("to", "")).strip() in generation_nodes
            for transition in transitions
        )
        handoff_ok = any(
            isinstance(transition, dict)
            and str(transition.get("from", "")).strip() in route_failure_nodes
            and str(transition.get("to", "")).strip() in route_terminal_nodes
            and str(transition.get("kind", "")).strip() in {"handoff", "stop", "normal"}
            for transition in transitions
        )
        self_iteration_ok = (
            isinstance(max_attempts, int)
            and max_attempts > 0
            and isinstance(stop_conditions, list)
            and bool(stop_conditions)
            and retry_ok
            and handoff_ok
        )
        self_iteration_detail = (
            f"max_attempts={max_attempts} stop_conditions={len(stop_conditions) if isinstance(stop_conditions, list) else 'invalid'} "
            f"failure_nodes={sorted(route_failure_nodes)} generation_nodes={sorted(generation_nodes)} retry_ok={retry_ok} handoff_ok={handoff_ok}"
        )
    checks.append(
        _check(
            "SPEC-16",
            self_iteration_ok,
            self_iteration_detail,
            "design",
        )
    )

    schema_version = spec.get("schema_version")
    checks.append(
        _check(
            "SPEC-10",
            schema_version in {SCHEMA_VERSION, None},
            f"schema_version={schema_version or 'legacy-v1'}",
            "schema_contract",
        )
    )

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
    plugin_hook_ok = True
    plugin_hook_details: list[str] = []
    for plugin in plugins:
        hook_intents = plugin.get("hook_intents", [])
        hook_events = plugin.get("hook_events", [])
        plugin_name = str(plugin.get("name", plugin.get("file", "unknown")))
        current_ok = (
            isinstance(hook_intents, list)
            and bool(hook_intents)
            and all(str(item).strip() for item in hook_intents)
            and isinstance(hook_events, list)
            and bool(hook_events)
            and all(str(item).strip() in ALLOWED_TARGET_PLUGIN_HOOK_EVENTS for item in hook_events)
        )
        plugin_hook_ok = plugin_hook_ok and current_ok
        plugin_hook_details.append(f"{plugin_name}: intents={hook_intents} events={hook_events}")
    checks.append(
        _check(
            "SPEC-17",
            plugin_hook_ok,
            "; ".join(plugin_hook_details) if plugin_hook_details else "plugins=[]",
            "design",
        )
    )

    package_refs = []
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
