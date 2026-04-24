#!/usr/bin/env python3
"""Package contract validator for the WorkflowProgram package."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import yaml


RUNTIME_DIR = Path(__file__).resolve().parents[1]
if str(RUNTIME_DIR) not in sys.path:
    sys.path.insert(0, str(RUNTIME_DIR))

from runtime_common import (  # noqa: E402
    INSTALL_MANIFEST_PATH,
    PACKAGE_COMMAND_PREFIX,
    PACKAGE_PLUGIN_ID,
    PRODUCT_INTENT_CONTRACT,
    REQUIRED_PACKAGE_AGENTS,
    REQUIRED_PACKAGE_COMMANDS,
    detect_package_layout,
)
from error_codes import code_for, remediation_for  # noqa: E402


REQUIRED_VALIDATORS = (
    "package_contract_validator.py",
    "workflow_spec_validator.py",
    "target_bundle_validator.py",
    "run_state_validator.py",
)
REQUIRED_AGENT_METADATA = (
    "workflowprogram_role",
    "workflowprogram_stage_affinity",
    "workflowprogram_capabilities",
    "workflowprogram_trigger",
    "workflowprogram_priority",
    "workflowprogram_fan_in",
)


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _build_check(check_id: str, passed: bool, detail: str, category: str) -> dict[str, Any]:
    return {
        "id": check_id,
        "passed": passed,
        "detail": detail,
        "category": category,
        "error_code": None if passed else code_for(category, check_id),
        "remediation": None if passed else remediation_for(category),
    }


def _agent_frontmatter(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return {}
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}
    payload = yaml.safe_load(parts[1]) or {}
    return payload if isinstance(payload, dict) else {}


def validate_package_contract(package_root: Path) -> dict[str, Any]:
    root = package_root.resolve()
    layout = detect_package_layout(root)
    opencode_json = layout.config_path
    commands_dir = layout.commands_dir
    agents_dir = layout.agents_dir
    plugins_dir = layout.plugins_dir
    plugin_file = layout.plugin_file
    runtime_dir = layout.runtime_root
    validators_dir = layout.validators_dir

    checks: list[dict[str, Any]] = []
    checks.append(
        _build_check(
            "PKG-01",
            root.exists(),
            f"package_root={root} layout={layout.layout_kind}",
            "package_structure",
        )
    )
    checks.append(_build_check("PKG-02", opencode_json.is_file(), f"opencode_json={opencode_json}", "package_structure"))
    checks.append(_build_check("PKG-03", commands_dir.is_dir(), f"commands_dir={commands_dir}", "package_structure"))
    checks.append(_build_check("PKG-04", plugin_file.is_file(), f"plugin_file={plugin_file}", "package_structure"))

    command_files = sorted(commands_dir.glob("*.md")) if commands_dir.is_dir() else []
    command_stems = [path.stem for path in command_files]
    package_command_files = [path for path in command_files if path.stem.startswith(PACKAGE_COMMAND_PREFIX)]
    package_command_stems = [path.stem for path in package_command_files]
    non_package_command_stems = [path.stem for path in command_files if not path.stem.startswith(PACKAGE_COMMAND_PREFIX)]
    namespace_ok = set(REQUIRED_PACKAGE_COMMANDS).issubset(set(package_command_stems))
    checks.append(
        _build_check(
            "PKG-05",
            namespace_ok,
            (
                f"package_commands={[path.name for path in package_command_files]} "
                f"other_commands={[path.name for path in command_files if path not in package_command_files]}"
            ),
            "package_contract",
        )
    )

    config_commands: dict[str, Any] = {}
    if opencode_json.is_file():
        try:
            config_commands = _load_json(opencode_json).get("command", {})
        except Exception as exc:  # pragma: no cover - defensive
            checks.append(_build_check("PKG-02", False, f"invalid json: {exc}", "package_structure"))
            config_commands = {}

    config_package_commands = sorted(
        name for name in config_commands.keys() if str(name).startswith(PACKAGE_COMMAND_PREFIX)
    )
    truth_source_ok = namespace_ok
    checks.append(
        _build_check(
            "PKG-06",
            truth_source_ok,
            (
                "WorkflowProgram product commands must exist under the discovered commands directory; "
                f"required={list(REQUIRED_PACKAGE_COMMANDS)} config_wp_commands={config_package_commands}"
            ),
            "package_contract",
        )
    )

    overlap = sorted(set(package_command_stems) & set(config_package_commands))
    checks.append(
        _build_check(
            "PKG-07",
            not overlap,
            f"overlap={overlap}",
            "package_contract",
        )
    )

    metadata_files = [plugins_dir / "plugin.json", plugins_dir / "marketplace.json"]
    checks.append(
        _build_check(
            "PKG-08",
            True,
            "plugin metadata files are optional",
            "none",
        )
    )
    checks.append(_build_check("PKG-09", runtime_dir.is_dir(), f"runtime_dir={runtime_dir}", "package_structure"))

    validators_present = validators_dir.is_dir() and all(
        (validators_dir / name).is_file() for name in REQUIRED_VALIDATORS
    )
    checks.append(
        _build_check(
            "PKG-10",
            validators_present,
            f"validators_dir={validators_dir}",
            "package_structure",
        )
    )

    permission_policy = runtime_dir / "permission-policy.yaml"
    permission_policy_ok = False
    if permission_policy.is_file():
        policy = yaml.safe_load(permission_policy.read_text(encoding="utf-8")) or {}
        privacy_policy = policy.get("privacy_policy", {}) if isinstance(policy, dict) else {}
        permission_policy_ok = bool(privacy_policy.get("redact_environment_keys_containing"))
    checks.append(
        _build_check(
            "SEC-01",
            permission_policy_ok,
            f"permission_policy={permission_policy}",
            "privacy",
        )
    )

    plugin_id_ok = False
    if plugin_file.is_file():
        plugin_id_ok = PACKAGE_PLUGIN_ID in plugin_file.read_text(encoding="utf-8")
    other_plugin_conflicts: list[str] = []
    if plugins_dir.is_dir():
        for candidate in sorted(plugins_dir.iterdir()):
            if not candidate.is_file() or candidate == plugin_file:
                continue
            try:
                if PACKAGE_PLUGIN_ID in candidate.read_text(encoding="utf-8"):
                    other_plugin_conflicts.append(candidate.name)
            except UnicodeDecodeError:
                continue
    checks.append(
        _build_check(
            "PKG-11",
            namespace_ok and plugin_id_ok and not other_plugin_conflicts and not any(
                stem.startswith(PACKAGE_COMMAND_PREFIX) for stem in non_package_command_stems
            ),
            (
                "package identifiers reserve wp-* and workflowprogram-package-bridge; "
                f"other_plugin_conflicts={other_plugin_conflicts}"
            ),
            "namespace_conflict",
        )
    )

    checks.append(
        _build_check(
            "PKG-12",
            agents_dir.is_dir(),
            f"agents_dir={agents_dir}",
            "package_structure",
        )
    )
    agent_files = sorted(agents_dir.glob("*.md")) if agents_dir.is_dir() else []
    agent_stems = {path.stem for path in agent_files}
    missing_agents = sorted(set(REQUIRED_PACKAGE_AGENTS) - agent_stems)
    checks.append(
        _build_check(
            "PKG-13",
            not missing_agents,
            f"required_agents={list(REQUIRED_PACKAGE_AGENTS)} missing_agents={missing_agents}",
            "package_contract",
        )
    )

    malformed_agents: list[str] = []
    for agent_path in agent_files:
        frontmatter = _agent_frontmatter(agent_path)
        missing_metadata = [key for key in REQUIRED_AGENT_METADATA if key not in frontmatter]
        role_matches = frontmatter.get("workflowprogram_role") == agent_path.stem
        affinity_ok = isinstance(frontmatter.get("workflowprogram_stage_affinity"), list)
        capabilities_ok = isinstance(frontmatter.get("workflowprogram_capabilities"), list)
        priority_ok = isinstance(frontmatter.get("workflowprogram_priority"), int)
        if missing_metadata or not role_matches or not affinity_ok or not capabilities_ok or not priority_ok:
            malformed_agents.append(
                f"{agent_path.name}:missing={missing_metadata},role_matches={role_matches}"
            )
    checks.append(
        _build_check(
            "AGT-01",
            not malformed_agents,
            f"malformed_agents={malformed_agents}",
            "agent_contract",
        )
    )

    runner_path = runtime_dir / "workflow-runner.py"
    entry_path = runtime_dir / "workflow-entry.py"
    runner_text = runner_path.read_text(encoding="utf-8") if runner_path.is_file() else ""
    intent_contract_ok = True
    intent_details: list[str] = []
    for intent, contract in PRODUCT_INTENT_CONTRACT.items():
        command_name = str(contract["command"])
        command_present = command_name in package_command_stems
        handler_present = f"run_{intent}" in runner_text
        if not command_present or not handler_present:
            intent_contract_ok = False
        intent_details.append(
            f"{intent}:command={command_present},handler={handler_present},mutating={contract['mutating']}"
        )
    checks.append(
        _build_check(
            "INT-01",
            intent_contract_ok and entry_path.is_file(),
            "; ".join(intent_details),
            "intent_contract",
        )
    )

    failed = [item for item in checks if not item["passed"] and item["category"] != "none"]
    verdict = "PASS" if not failed else "FAIL"
    return {
        "validator": "package_contract_validator",
        "package_root": str(root),
        "layout_kind": layout.layout_kind,
        "verdict": verdict,
        "checks": checks,
        "exit_code": 0 if verdict == "PASS" else 1,
        "metadata_files_present": [str(path) for path in metadata_files if path.exists()],
        "install_manifest": str(layout.install_manifest) if layout.install_manifest.exists() else None,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate WorkflowProgram package contract")
    parser.add_argument("--package-root", required=True)
    parser.add_argument("--json", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    result = validate_package_contract(Path(args.package_root))
    if args.json:
        json.dump(result, sys.stdout, indent=2, ensure_ascii=True)
        sys.stdout.write("\n")
    else:
        sys.stdout.write(f"{result['verdict']} package_root={result['package_root']}\n")
        for check in result["checks"]:
            status = "PASS" if check["passed"] else "FAIL"
            sys.stdout.write(f"{status} {check['id']} {check['detail']}\n")
    return result["exit_code"]


if __name__ == "__main__":
    raise SystemExit(main())
