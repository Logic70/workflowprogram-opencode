#!/usr/bin/env python3
"""Focused regression checks for the OpenCode develop design flow."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[1]
ENTRY = ROOT / "package" / ".workflowprogram" / "runtime" / "workflow-entry.py"
PACKAGE_ROOT = ROOT / "package"
SPEC_VALIDATOR = PACKAGE_ROOT / ".workflowprogram" / "runtime" / "validators" / "workflow_spec_validator.py"


def run_entry(target: Path, args: list[str], expect_code: int = 0) -> dict[str, Any]:
    command = [
        sys.executable,
        str(ENTRY),
        "develop",
        "--package-root",
        str(PACKAGE_ROOT),
        "--target-root",
        str(target),
        *args,
        "--json",
    ]
    completed = subprocess.run(command, cwd=str(ROOT), text=True, capture_output=True)
    if completed.returncode != expect_code:
        raise AssertionError(
            f"expected exit {expect_code}, got {completed.returncode}\nSTDOUT:\n{completed.stdout}\nSTDERR:\n{completed.stderr}"
        )
    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise AssertionError(f"runtime did not return JSON: {exc}\n{completed.stdout}") from exc


def assert_no_design_write_without_confirmation() -> None:
    with tempfile.TemporaryDirectory(prefix="wp-no-confirm-") as tmp:
        target = Path(tmp)
        result = run_entry(
            target,
            ["--user-arguments", "Design a broad reverse engineering workflow"],
        )
        if result["verdict"] != "WARN":
            raise AssertionError(f"expected WARN, got {result['verdict']}")
        if (target / ".workflowprogram" / "design" / "workflow-spec.yaml").exists():
            raise AssertionError("unconfirmed develop wrote workflow-spec.yaml")


def assert_plugin_hook_independent_from_cli() -> None:
    with tempfile.TemporaryDirectory(prefix="wp-plugin-only-") as tmp:
        target = Path(tmp)
        result = run_entry(
            target,
            [
                "--user-arguments",
                "Design plugin-only target workflow --emit-target-plugin",
                "--confirmed",
                "--allow-template-fallback",
            ],
        )
        if result["validation"]["verdict"] != "PASS":
            raise AssertionError("plugin-only fallback validation did not pass")
        commands = list((target / ".opencode" / "commands").glob("*.md"))
        plugins = list((target / ".opencode" / "plugins").glob("*.ts"))
        if commands:
            raise AssertionError(f"plugin-only spec generated commands: {commands}")
        if len(plugins) != 1:
            raise AssertionError(f"expected one target plugin, got {plugins}")
        if (target / ".workflowprogram" / "design" / "workflow-view.md").exists():
            raise AssertionError("workflow-view.md should not be a core generated artifact")
        if (target / ".workflowprogram" / "design" / "workflow-lowlevel.md").exists():
            raise AssertionError("workflow-lowlevel.md should not be a core generated artifact")


def assert_self_iteration_is_selected_by_graph() -> None:
    with tempfile.TemporaryDirectory(prefix="wp-self-iteration-") as tmp:
        target = Path(tmp)
        result = run_entry(
            target,
            [
                "--user-arguments",
                "Design a complex workflow --complexity L",
                "--confirmed",
                "--allow-template-fallback",
            ],
        )
        if result["validation"]["verdict"] != "PASS":
            raise AssertionError("self-iteration fallback validation did not pass")
        spec = json.loads(json.dumps(result["validation"]["layers"]["spec"]))
        if not any("SPEC-16" == check["id"] and check["passed"] for check in spec["checks"]):
            raise AssertionError("self-iteration graph validation did not pass")
        spec_path = target / ".workflowprogram" / "design" / "workflow-spec.yaml"
        text = spec_path.read_text(encoding="utf-8")
        if "self-iteration-loop" not in text:
            raise AssertionError("complexity L did not select self-iteration-loop")


def assert_design_lineage_and_node_loop_evidence() -> None:
    with tempfile.TemporaryDirectory(prefix="wp-lineage-loop-") as tmp:
        target = Path(tmp)
        result = run_entry(
            target,
            [
                "--user-arguments",
                "Design a complex workflow that needs bounded validation iteration --complexity L",
                "--confirmed",
                "--allow-template-fallback",
            ],
        )
        if result["validation"]["verdict"] != "PASS":
            raise AssertionError("lineage and node-loop fallback validation did not pass")
        spec_path = target / ".workflowprogram" / "design" / "workflow-spec.yaml"
        spec = yaml.safe_load(spec_path.read_text(encoding="utf-8"))
        if not isinstance(spec.get("design_refs"), dict):
            raise AssertionError("generated spec did not declare design_refs")
        if "node_loop_execution" not in spec["generated_runtime_contract"]["runtime_capabilities"]:
            raise AssertionError("loop-enabled spec did not declare node_loop_execution")
        loop_nodes = [
            node
            for node in spec.get("nodes", [])
            if isinstance(node, dict)
            and isinstance(node.get("loop_policy"), dict)
            and node["loop_policy"].get("enabled") is True
        ]
        if [node.get("id") for node in loop_nodes] != ["iterate-on-failures"]:
            raise AssertionError(f"unexpected loop nodes: {loop_nodes}")

        run_root = Path(result["run_root"])
        for rel_path in (
            "outputs/clarification/question-backlog.json",
            "outputs/clarification/requirement-logic-map.json",
            "outputs/stages/question-backlog.json",
            "outputs/stages/requirement-logic-map.json",
            "outputs/stages/s1-requirements.yaml",
            "outputs/stages/s2-context-findings.yaml",
            "outputs/stages/s3-design-highlevel.md",
            "outputs/stages/s3-design-lowlevel.md",
            "outputs/stages/s3-implementation-plan.md",
            "outputs/stages/acceptance-tests.yaml",
            "outputs/stages/traceability-matrix.json",
            "outputs/stages/loops/iterate-on-failures/loop-plan.json",
            "outputs/stages/loops/iterate-on-failures/iteration-summary.jsonl",
            "outputs/stages/loops/iterate-on-failures/final-verdict.json",
        ):
            if not (run_root / rel_path).is_file():
                raise AssertionError(f"missing lineage or loop evidence: {rel_path}")
        judge_checks = result["judge"].get("checks", [])
        required_checks = {
            "design_lineage_requirement_traceability",
            "requirement_logic_lenses_complete",
            "requirement_logic_questions_design_consequential",
            "requirement_logic_handoff_ready",
            "node_loop_evidence_present",
            "node_loop_verifier_gate_observed",
        }
        passed_checks = {check.get("name") for check in judge_checks if check.get("status") == "PASS"}
        if not required_checks.issubset(passed_checks):
            raise AssertionError(f"S5 did not pass required lineage/loop checks: {judge_checks}")


def assert_loop_policy_requires_runtime_capability() -> None:
    with tempfile.TemporaryDirectory(prefix="wp-loop-capability-") as tmp:
        target = Path(tmp)
        result = run_entry(
            target,
            [
                "--user-arguments",
                "Design a complex workflow --complexity L",
                "--confirmed",
                "--allow-template-fallback",
            ],
        )
        spec_path = target / ".workflowprogram" / "design" / "workflow-spec.yaml"
        spec = yaml.safe_load(spec_path.read_text(encoding="utf-8"))
        spec["generated_runtime_contract"]["runtime_capabilities"] = [
            capability
            for capability in spec["generated_runtime_contract"]["runtime_capabilities"]
            if capability != "node_loop_execution"
        ]
        invalid_spec = Path(tmp) / "invalid-loop-spec.yaml"
        invalid_spec.write_text(yaml.safe_dump(spec, sort_keys=False), encoding="utf-8")
        completed = subprocess.run(
            [sys.executable, str(SPEC_VALIDATOR), "--spec", str(invalid_spec), "--json"],
            cwd=str(ROOT),
            text=True,
            capture_output=True,
        )
        if completed.returncode == 0:
            raise AssertionError("loop policy without node_loop_execution passed spec validation")
        payload = json.loads(completed.stdout)
        failed = [check for check in payload.get("checks", []) if check.get("id") == "SPEC-20"]
        if not failed or failed[0].get("passed") is not False:
            raise AssertionError(f"SPEC-20 did not report missing node_loop_execution: {payload}")


def assert_requirement_logic_validators_reject_shallow_draft() -> None:
    with tempfile.TemporaryDirectory(prefix="wp-shallow-draft-") as tmp:
        target = Path(tmp)
        draft = target / "workflow-spec.md"
        draft.write_text(
            "\n".join(
                [
                    "# Workflow Spec Draft",
                    "",
                    "## User Intent",
                    "",
                    "- Summary: build something",
                    "",
                    "## Clarification Summary",
                    "",
                    "- 澄清轮次: 1",
                    "",
                    "## Open Questions",
                    "",
                    "- 还有哪些边界场景？",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        completed = subprocess.run(
            [
                sys.executable,
                str(PACKAGE_ROOT / ".workflowprogram" / "runtime" / "validate-workflow-draft.py"),
                "--spec",
                str(draft),
                "--run-root",
                str(target),
                "--json",
            ],
            cwd=str(ROOT),
            text=True,
            capture_output=True,
        )
        if completed.returncode == 0:
            raise AssertionError("shallow draft passed requirement logic validation")
        payload = json.loads(completed.stdout)
        failed_ids = {check["id"] for check in payload["checks"] if not check["passed"]}
        if not {"DRAFT-03", "DRAFT-04", "DRAFT-05", "DRAFT-08"}.issubset(failed_ids):
            raise AssertionError(f"shallow draft did not fail expected checks: {payload}")


def assert_ai_evidence_does_not_bypass_spec() -> None:
    with tempfile.TemporaryDirectory(prefix="wp-ai-evidence-") as tmp:
        target = Path(tmp)
        result = run_entry(
            target,
            [
                "--user-arguments",
                "Design a workflow --confirmed",
                "--ai-evidence",
                "agent said ok",
                "--confirmed",
            ],
        )
        if result["verdict"] not in {"WARN", "FAIL"}:
            raise AssertionError(f"expected non-PASS, got {result['verdict']}")
        if "workflow-spec.yaml is required" not in result["summary"]:
            raise AssertionError(f"unexpected failure summary: {result['summary']}")
        if (target / ".workflowprogram" / "design" / "workflow-spec.yaml").exists():
            raise AssertionError("ai-evidence-only run wrote workflow-spec.yaml")


def main() -> int:
    assert_no_design_write_without_confirmation()
    assert_plugin_hook_independent_from_cli()
    assert_self_iteration_is_selected_by_graph()
    assert_design_lineage_and_node_loop_evidence()
    assert_loop_policy_requires_runtime_capability()
    assert_requirement_logic_validators_reject_shallow_draft()
    assert_ai_evidence_does_not_bypass_spec()
    print("design flow runtime regression checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
