#!/usr/bin/env python3
"""Target bundle validator for WorkflowProgram OpenCode targets."""

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
    PACKAGE_COMMAND_PREFIX,
    PACKAGE_PLUGIN_FILE,
    PACKAGE_PLUGIN_ID,
    SCHEMA_VERSION,
    derive_expected_target_files,
    read_json,
    read_yaml,
    registry_commands,
    registry_plugins,
)
from error_codes import code_for, remediation_for  # noqa: E402


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


def validate_target_bundle(target_root: Path) -> dict[str, Any]:
    resolved = target_root.resolve()
    design_dir = resolved / ".workflowprogram" / "design"
    runtime_dir = resolved / ".workflowprogram" / "runtime"
    spec_path = design_dir / "workflow-spec.yaml"
    manifest_path = resolved / ".workflowprogram" / "managed-files.json"
    checks: list[dict[str, Any]] = []

    checks.append(_check("TGT-01", design_dir.is_dir(), f"design_dir={design_dir}", "bundle_structure"))
    checks.append(_check("TGT-02", runtime_dir.is_dir(), f"runtime_dir={runtime_dir}", "bundle_structure"))

    if not spec_path.exists():
        checks.append(_check("TGT-03", False, "workflow-spec.yaml missing from target bundle", "bundle_mismatch"))
        verdict = "FAIL"
        return {
            "validator": "target_bundle_validator",
            "target_root": str(resolved),
            "verdict": verdict,
            "summary": "Target bundle validation failed",
            "checks": checks,
            "exit_code": 1,
        }

    spec = read_yaml(spec_path)
    spec = spec if isinstance(spec, dict) else {}
    checks.append(
        _check(
            "MIG-01",
            spec.get("schema_version") in {SCHEMA_VERSION, None},
            f"schema_version={spec.get('schema_version') or 'legacy-v1'}",
            "schema_contract",
        )
    )
    deliverables = derive_expected_target_files(spec)
    missing_deliverables = [path for path in deliverables if not (resolved / path).exists()]
    checks.append(
        _check(
            "TGT-03",
            not missing_deliverables,
            f"missing={missing_deliverables}",
            "bundle_mismatch",
        )
    )

    manifest_ok = manifest_path.is_file()
    manifest_entries: list[dict[str, Any]] = []
    if manifest_ok:
        try:
            manifest_payload = read_json(manifest_path)
            manifest_entries = manifest_payload.get("entries", [])
            manifest_ok = manifest_payload.get("schema_version") in {SCHEMA_VERSION, None}
        except Exception:
            manifest_ok = False
    checks.append(
        _check(
            "TGT-04",
            manifest_ok and isinstance(manifest_entries, list),
            f"manifest_path={manifest_path}",
            "bundle_state",
        )
    )

    commands = registry_commands(spec)
    command_names_ok = True
    for command in commands:
        command_name = str(command.get("name", ""))
        command_file = str(command.get("file", ""))
        if command_name.startswith(PACKAGE_COMMAND_PREFIX) or Path(command_file).stem.startswith(PACKAGE_COMMAND_PREFIX):
            command_names_ok = False
            break
    checks.append(
        _check(
            "TGT-05",
            command_names_ok,
            f"commands={commands}",
            "namespace_conflict",
        )
    )

    checks.append(
        _check(
            "TGT-06",
            True if commands else True,
            f"command_count={len(commands)}",
            "bundle_policy",
        )
    )

    plugins = registry_plugins(spec)
    checks.append(
        _check(
            "TGT-07",
            True if plugins else True,
            f"plugin_count={len(plugins)}",
            "bundle_policy",
        )
    )

    plugin_names_ok = all(
        plugin.get("file") != f".opencode/plugins/{PACKAGE_PLUGIN_FILE}"
        and plugin.get("plugin_id") != PACKAGE_PLUGIN_ID
        for plugin in plugins
    )
    checks.append(
        _check(
            "TGT-08",
            plugin_names_ok,
            f"plugins={plugins}",
            "namespace_conflict",
        )
    )
    declared_command_files = {
        str(command.get("file", "")).replace("\\", "/")
        for command in commands
        if str(command.get("file", "")).strip()
    }
    actual_command_files = {
        path.relative_to(resolved).as_posix()
        for path in (resolved / ".opencode" / "commands").glob("*.md")
        if path.is_file()
    }
    declared_plugin_files = {
        str(plugin.get("file", "")).replace("\\", "/")
        for plugin in plugins
        if str(plugin.get("file", "")).strip()
    }
    actual_plugin_files = {
        path.relative_to(resolved).as_posix()
        for path in (resolved / ".opencode" / "plugins").glob("*.ts")
        if path.is_file()
    }
    undeclared_opencode_assets = sorted(
        (actual_command_files - declared_command_files)
        | (actual_plugin_files - declared_plugin_files)
    )
    missing_declared_opencode_assets = sorted(
        (declared_command_files - actual_command_files)
        | (declared_plugin_files - actual_plugin_files)
    )
    checks.append(
        _check(
            "TGT-10",
            not undeclared_opencode_assets and not missing_declared_opencode_assets,
            f"undeclared={undeclared_opencode_assets} missing_declared={missing_declared_opencode_assets}",
            "bundle_policy",
        )
    )
    hook_consistency_ok = True
    hook_details: list[str] = []
    for plugin in plugins:
        relative_file = str(plugin.get("file", "")).replace("\\", "/")
        hook_events = plugin.get("hook_events", [])
        plugin_path = resolved / relative_file
        content = plugin_path.read_text(encoding="utf-8") if plugin_path.is_file() else ""
        declared_events = {str(event).strip() for event in hook_events} if isinstance(hook_events, list) else set()
        current_ok = bool(declared_events) and declared_events.issubset(ALLOWED_TARGET_PLUGIN_HOOK_EVENTS)
        for event in declared_events:
            if event not in content:
                current_ok = False
        for event in ALLOWED_TARGET_PLUGIN_HOOK_EVENTS - declared_events:
            if event in content:
                current_ok = False
        hook_consistency_ok = hook_consistency_ok and current_ok
        hook_details.append(f"{relative_file}: declared={sorted(declared_events)}")
    checks.append(
        _check(
            "TGT-11",
            hook_consistency_ok,
            "; ".join(hook_details) if hook_details else "plugins=[]",
            "bundle_policy",
        )
    )

    generated_runtime = (
        spec.get("generated_runtime_contract", {})
        if isinstance(spec.get("generated_runtime_contract"), dict)
        else {}
    )
    runtime_wrapper_files = [
        generated_runtime.get("entry_script"),
        generated_runtime.get("runner_script"),
        generated_runtime.get("state_validator_script"),
        generated_runtime.get("runtime_manifest"),
    ]
    runtime_wrapper_ok = all(
        isinstance(path, str) and path and (resolved / path).is_file()
        for path in runtime_wrapper_files
    )
    checks.append(
        _check(
            "TGT-09",
            runtime_wrapper_ok,
            f"runtime_wrapper_files={runtime_wrapper_files}",
            "bundle_structure",
        )
    )

    failed = [check for check in checks if not check["passed"]]
    verdict = "PASS" if not failed else "FAIL"
    return {
        "validator": "target_bundle_validator",
        "target_root": str(resolved),
        "verdict": verdict,
        "summary": "Target bundle validated" if verdict == "PASS" else "Target bundle validation failed",
        "checks": checks,
        "exit_code": 0 if verdict == "PASS" else 1,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate target bundle")
    parser.add_argument("--target-root", required=True)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = validate_target_bundle(Path(args.target_root))
    if args.json:
        json.dump(result, sys.stdout, indent=2, ensure_ascii=True)
        sys.stdout.write("\n")
    else:
        sys.stdout.write(f"{result['verdict']} target_root={result['target_root']}\n")
        for check in result["checks"]:
            status = "PASS" if check["passed"] else "FAIL"
            sys.stdout.write(f"{status} {check['id']} {check['detail']}\n")
    return result["exit_code"]


if __name__ == "__main__":
    raise SystemExit(main())
