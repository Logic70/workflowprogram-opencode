#!/usr/bin/env python3
"""Workflow spec validator for WorkflowProgram OpenCode targets."""

from __future__ import annotations

import argparse
import json
import re
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
    VALID_RUNTIME_CAPABILITIES,
    derive_expected_target_files,
    node_loop_enabled_nodes,
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
VALID_LOOP_MODES = {"ralph"}
VALID_LOOP_GOAL_SOURCES = {"user", "model_subgoal"}
VALID_LOOP_FEEDBACK_KINDS = {"validator", "verifier", "test"}
VALID_LOOP_FAILURE_EFFECTS = {"feedback", "gate", "hard_fail"}
VALID_LOOP_MAX_ITERATION_EFFECTS = {"fail", "warn"}
DESIGN_REF_PATH_KEYS = {
    "requirements",
    "context_findings",
    "design_highlevel",
    "design_lowlevel",
    "implementation_plan",
    "acceptance_tests",
    "traceability_matrix",
}


def _safe_relative_path(path_text: str) -> bool:
    cleaned = path_text.strip().replace("\\", "/")
    if not cleaned or cleaned.startswith("/") or cleaned.startswith("~") or "//" in cleaned:
        return False
    return all(part not in {"", ".", ".."} for part in cleaned.split("/"))


def _safe_slug(value: str) -> bool:
    return bool(re.match(r"^[A-Za-z0-9_-]+$", value))


def _check(check_id: str, passed: bool, detail: str, category: str) -> dict[str, Any]:
    return {
        "id": check_id,
        "passed": passed,
        "detail": detail,
        "category": category,
        "error_code": None if passed else code_for(category, check_id),
        "remediation": None if passed else remediation_for(category),
    }


def _validate_node_loop_policy(node: dict[str, Any], node_index: int) -> list[str]:
    errors: list[str] = []
    node_id = str(node.get("id", "")).strip()
    policy = node.get("loop_policy")
    if policy is None:
        return errors
    prefix = f"nodes[{node_index}].loop_policy"
    if not isinstance(policy, dict):
        return [f"{prefix} must be an object"]

    enabled = policy.get("enabled")
    if not isinstance(enabled, bool):
        return [f"{prefix}.enabled must be a boolean"]
    if enabled is False:
        return errors

    mode = str(policy.get("mode", "")).strip()
    if mode not in VALID_LOOP_MODES:
        errors.append(f"{prefix}.mode must be one of {sorted(VALID_LOOP_MODES)}")

    max_iterations = policy.get("max_iterations")
    if not isinstance(max_iterations, int) or max_iterations < 1 or max_iterations > 50:
        errors.append(f"{prefix}.max_iterations must be an integer between 1 and 50")

    if not isinstance(policy.get("fresh_context_each_iteration"), bool):
        errors.append(f"{prefix}.fresh_context_each_iteration must be a boolean")

    prompt_package = str(policy.get("prompt_package", "")).strip().replace("\\", "/")
    if not _safe_relative_path(prompt_package):
        errors.append(f"{prefix}.prompt_package must be a safe relative path")
    elif not prompt_package.startswith(".workflowprogram/loops/"):
        errors.append(f"{prefix}.prompt_package must stay under .workflowprogram/loops/**")

    goal_source = str(policy.get("goal_source", "user")).strip() or "user"
    if goal_source not in VALID_LOOP_GOAL_SOURCES:
        errors.append(f"{prefix}.goal_source must be one of {sorted(VALID_LOOP_GOAL_SOURCES)}")
    if goal_source == "model_subgoal" and not str(policy.get("parent_goal_ref", "")).strip():
        errors.append(f"{prefix}.parent_goal_ref is required when goal_source=model_subgoal")

    feedback_commands = policy.get("feedback_commands", [])
    if not isinstance(feedback_commands, list) or not feedback_commands:
        errors.append(f"{prefix}.feedback_commands must be a non-empty list")
        feedback_commands = []
    for command_index, raw_command in enumerate(feedback_commands):
        command_prefix = f"{prefix}.feedback_commands[{command_index}]"
        if not isinstance(raw_command, dict):
            errors.append(f"{command_prefix} must be an object")
            continue
        if not str(raw_command.get("id", "")).strip():
            errors.append(f"{command_prefix}.id is required")
        if str(raw_command.get("kind", "")).strip() not in VALID_LOOP_FEEDBACK_KINDS:
            errors.append(f"{command_prefix}.kind must be one of {sorted(VALID_LOOP_FEEDBACK_KINDS)}")
        if "command" in raw_command:
            errors.append(f"{command_prefix}.command is not allowed; use structured argv")
        argv = raw_command.get("argv")
        if not isinstance(argv, list) or not argv or any(not str(item).strip() for item in argv):
            errors.append(f"{command_prefix}.argv must be a non-empty list of strings")
        timeout = raw_command.get("timeout_seconds")
        if timeout is not None and (not isinstance(timeout, int) or timeout < 1 or timeout > 600):
            errors.append(f"{command_prefix}.timeout_seconds must be an integer between 1 and 600")
        if str(raw_command.get("failure_effect", "")).strip() not in VALID_LOOP_FAILURE_EFFECTS:
            errors.append(
                f"{command_prefix}.failure_effect must be one of {sorted(VALID_LOOP_FAILURE_EFFECTS)}"
            )

    stop_conditions = policy.get("stop_conditions", {})
    if not isinstance(stop_conditions, dict):
        errors.append(f"{prefix}.stop_conditions must be an object")
        stop_conditions = {}
    success = stop_conditions.get("success", [])
    if not isinstance(success, list) or not [str(item).strip() for item in success]:
        errors.append(f"{prefix}.stop_conditions.success must be a non-empty list")
    if str(stop_conditions.get("max_iterations", "")).strip() not in VALID_LOOP_MAX_ITERATION_EFFECTS:
        errors.append(
            f"{prefix}.stop_conditions.max_iterations must be one of {sorted(VALID_LOOP_MAX_ITERATION_EFFECTS)}"
        )
    no_progress = stop_conditions.get("no_progress_iterations")
    if no_progress is not None:
        if not isinstance(no_progress, int) or no_progress < 1:
            errors.append(f"{prefix}.stop_conditions.no_progress_iterations must be a positive integer")
        elif isinstance(max_iterations, int) and no_progress > max_iterations:
            errors.append(f"{prefix}.stop_conditions.no_progress_iterations must be <= max_iterations")
    hard_fail_on = stop_conditions.get("hard_fail_on", [])
    if hard_fail_on is not None and not isinstance(hard_fail_on, list):
        errors.append(f"{prefix}.stop_conditions.hard_fail_on must be a list when provided")

    tdd_policy = policy.get("tdd_policy", {})
    if tdd_policy:
        if not isinstance(tdd_policy, dict):
            errors.append(f"{prefix}.tdd_policy must be an object")
        else:
            tdd_enabled = tdd_policy.get("enabled", False)
            if not isinstance(tdd_enabled, bool):
                errors.append(f"{prefix}.tdd_policy.enabled must be a boolean")
            if tdd_enabled:
                for key in ("test_first_required", "red_green_refactor"):
                    if not isinstance(tdd_policy.get(key), bool):
                        errors.append(f"{prefix}.tdd_policy.{key} must be a boolean when tdd_policy.enabled=true")

    expected_evidence_prefix = f"outputs/stages/loops/{node_id}/"
    evidence_outputs = policy.get("evidence_outputs", [])
    if not isinstance(evidence_outputs, list) or not evidence_outputs:
        errors.append(f"{prefix}.evidence_outputs must be a non-empty list")
    else:
        for output_index, raw_output in enumerate(evidence_outputs):
            output = str(raw_output).strip().replace("\\", "/")
            if not _safe_relative_path(output):
                errors.append(f"{prefix}.evidence_outputs[{output_index}] must be a safe relative path")
            elif not output.startswith(expected_evidence_prefix):
                errors.append(f"{prefix}.evidence_outputs[{output_index}] must stay under {expected_evidence_prefix}**")
    return errors


def _validate_design_refs(design_refs: Any, node_ids: set[str]) -> list[str]:
    if design_refs in (None, {}):
        return []
    if not isinstance(design_refs, dict):
        return ["design_refs must be an object when declared"]
    errors: list[str] = []
    for key in DESIGN_REF_PATH_KEYS:
        if key not in design_refs:
            continue
        value = str(design_refs.get(key, "")).strip().replace("\\", "/")
        if not _safe_relative_path(value):
            errors.append(f"design_refs.{key} must be a safe relative path")
        elif not value.startswith("outputs/stages/"):
            errors.append(f"design_refs.{key} must stay under outputs/stages/")
    node_designs = design_refs.get("node_designs")
    if node_designs is None:
        return errors
    if not isinstance(node_designs, dict):
        errors.append("design_refs.node_designs must be a mapping of node id to path")
        return errors
    for raw_node_id, raw_path in node_designs.items():
        node_id = str(raw_node_id).strip()
        path = str(raw_path).strip().replace("\\", "/")
        if not node_id:
            errors.append("design_refs.node_designs contains an empty node id")
        elif node_id not in node_ids:
            errors.append(f"design_refs.node_designs references unknown node: {node_id}")
        if not _safe_relative_path(path):
            errors.append(f"design_refs.node_designs.{node_id or '<missing>'} must be a safe relative path")
        elif not path.startswith("outputs/stages/node-designs/"):
            errors.append(f"design_refs.node_designs.{node_id} must stay under outputs/stages/node-designs/")
    return errors


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
        if str(node.get("id", "")).strip() and not _safe_slug(str(node.get("id", "")).strip()):
            node_schema_ok = False
    checks.append(
        _check(
            "SPEC-03",
            node_schema_ok,
            f"node_ids={node_ids}",
            "design",
        )
    )

    loop_policy_errors: list[str] = []
    for index, node in enumerate(nodes):
        if isinstance(node, dict):
            loop_policy_errors.extend(_validate_node_loop_policy(node, index))
    loop_enabled_ids = [str(node.get("id", "")).strip() for node in node_loop_enabled_nodes(spec)]
    checks.append(
        _check(
            "SPEC-18",
            not loop_policy_errors,
            f"loop_enabled_nodes={loop_enabled_ids} errors={loop_policy_errors}",
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

    design_ref_errors = _validate_design_refs(spec.get("design_refs"), unique_node_ids)
    checks.append(
        _check(
            "SPEC-19",
            not design_ref_errors,
            f"declared={isinstance(spec.get('design_refs'), dict)} errors={design_ref_errors}",
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
    runtime_capabilities = (
        generated_runtime_contract.get("runtime_capabilities", [])
        if isinstance(generated_runtime_contract.get("runtime_capabilities"), list)
        else []
    )
    runtime_capability_errors: list[str] = []
    normalized_capabilities = [str(item).strip() for item in runtime_capabilities if str(item).strip()]
    if not normalized_capabilities:
        runtime_capability_errors.append("generated_runtime_contract.runtime_capabilities must be a non-empty list")
    for capability in normalized_capabilities:
        if capability not in VALID_RUNTIME_CAPABILITIES:
            runtime_capability_errors.append(
                f"generated_runtime_contract.runtime_capabilities contains unsupported capability: {capability}"
            )
    for required_capability in ("state_transitions", "run_state_validation"):
        if required_capability not in normalized_capabilities:
            runtime_capability_errors.append(
                f"generated_runtime_contract.runtime_capabilities must include {required_capability}"
            )
    if registry_commands(spec) and "target_command_delivery" not in normalized_capabilities:
        runtime_capability_errors.append(
            "generated_runtime_contract.runtime_capabilities must include target_command_delivery when registry.commands is declared"
        )
    if registry_plugins(spec) and "target_plugin_bridge" not in normalized_capabilities:
        runtime_capability_errors.append(
            "generated_runtime_contract.runtime_capabilities must include target_plugin_bridge when registry.plugins is declared"
        )
    if loop_enabled_ids and "node_loop_execution" not in normalized_capabilities:
        runtime_capability_errors.append(
            "generated_runtime_contract.runtime_capabilities must include node_loop_execution when nodes[*].loop_policy.enabled=true"
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
    checks.append(
        _check(
            "SPEC-20",
            not runtime_capability_errors,
            f"runtime_capabilities={normalized_capabilities} errors={runtime_capability_errors}",
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
