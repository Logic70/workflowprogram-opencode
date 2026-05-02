#!/usr/bin/env python3
"""Focused regression checks for the OpenCode develop design flow."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ENTRY = ROOT / "package" / ".workflowprogram" / "runtime" / "workflow-entry.py"
PACKAGE_ROOT = ROOT / "package"


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
    assert_ai_evidence_does_not_bypass_spec()
    print("design flow runtime regression checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
