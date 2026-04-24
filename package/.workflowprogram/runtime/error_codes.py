#!/usr/bin/env python3
"""Shared WorkflowProgram error code helpers."""

from __future__ import annotations


CATEGORY_PREFIX = {
    "package_structure": "PKG_STRUCTURE",
    "package_contract": "PKG_CONTRACT",
    "namespace_conflict": "NAMESPACE",
    "intent_contract": "INTENT",
    "agent_contract": "AGENT",
    "design": "SPEC_DESIGN",
    "layering": "LAYERING",
    "bundle_structure": "TARGET_STRUCTURE",
    "bundle_mismatch": "TARGET_MISMATCH",
    "bundle_state": "TARGET_STATE",
    "bundle_policy": "TARGET_POLICY",
    "evidence_missing": "EVIDENCE_MISSING",
    "evidence_inconsistent": "EVIDENCE_INCONSISTENT",
    "state_invalid": "STATE_INVALID",
    "orchestration": "ORCHESTRATION",
    "schema_contract": "SCHEMA",
    "apply_recovery": "APPLY",
    "host_isolation": "HOST_ISOLATION",
    "host_compatibility": "HOST_COMPAT",
    "host_reload": "HOST_RELOAD",
    "path_compatibility": "PATH_COMPAT",
    "host_probe": "HOST_PROBE",
    "host_integration": "HOST_INTEGRATION",
    "host_execution": "HOST_EXECUTION",
    "target_command_discovery": "TARGET_COMMAND",
    "target_plugin_discovery": "TARGET_PLUGIN",
    "target_contract": "TARGET_CONTRACT",
    "python": "PYTHON",
    "host": "HOST",
    "target": "TARGET",
    "package": "PACKAGE",
    "privacy": "PRIVACY",
    "none": "NONE",
}


def code_for(category: str, check_id: str) -> str:
    prefix = CATEGORY_PREFIX.get(category, "WORKFLOWPROGRAM")
    return f"{prefix}_{check_id}".upper().replace("-", "_")


def remediation_for(category: str) -> str:
    if category in {"package_structure", "package_contract", "intent_contract", "agent_contract"}:
        return "Reinstall or rebuild the WorkflowProgram OpenCode package, then rerun package validation."
    if category in {"host_isolation", "namespace_conflict"}:
        return "Inspect host-visible OpenCode, Claude, and third-party assets, then isolate conflicting sources."
    if category in {"bundle_structure", "bundle_mismatch", "bundle_state", "bundle_policy"}:
        return "Regenerate the target workflow with managed apply and rerun target validation."
    if category in {"evidence_missing", "evidence_inconsistent", "state_invalid"}:
        return "Rerun the WorkflowProgram intent and inspect RUN_ROOT evidence."
    if category == "apply_recovery":
        return "Inspect managed-change-result and rollback-manifest before retrying a mutating intent."
    if category == "schema_contract":
        return "Run or implement the schema migration path before applying current validators."
    return "Inspect the check detail and rerun the relevant WorkflowProgram validator."
