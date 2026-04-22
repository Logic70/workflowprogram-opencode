#!/usr/bin/env python3
"""Layered validation coordinator for WorkflowProgram runtime."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from runtime_common import aggregate_verdicts, write_json, write_text


RUNTIME_DIR = Path(__file__).resolve().parent
VALIDATORS_DIR = RUNTIME_DIR / "validators"
if str(VALIDATORS_DIR) not in sys.path:
    sys.path.insert(0, str(VALIDATORS_DIR))

from package_contract_validator import validate_package_contract  # type: ignore  # noqa: E402
from run_state_validator import validate_run_state  # type: ignore  # noqa: E402
from target_bundle_validator import validate_target_bundle  # type: ignore  # noqa: E402
from workflow_spec_validator import validate_workflow_spec  # type: ignore  # noqa: E402


def _markdown_report(summary: dict[str, Any]) -> str:
    lines = [
        "# Validation Summary",
        "",
        f"- Overall verdict: `{summary['verdict']}`",
        f"- Package: `{summary['layers']['package']['verdict']}`",
        f"- Spec: `{summary['layers']['spec']['verdict']}`",
        f"- Target: `{summary['layers']['target']['verdict']}`",
        f"- Run state: `{summary['layers']['run_state']['verdict']}`",
        "",
    ]
    for key in ("package", "spec", "target", "run_state"):
        layer = summary["layers"][key]
        lines.extend(
            [
                f"## {key}",
                "",
                f"- Verdict: `{layer['verdict']}`",
                f"- Summary: {layer.get('summary', 'n/a')}",
                "",
            ]
        )
    return "\n".join(lines) + "\n"


def run_validation_layers(package_root: Path, target_root: Path, run_root: Path) -> dict[str, Any]:
    spec_path = target_root / ".workflowprogram" / "design" / "workflow-spec.yaml"
    package_result = validate_package_contract(package_root)
    spec_result = validate_workflow_spec(spec_path)
    target_result = validate_target_bundle(target_root)
    run_state_result = validate_run_state(run_root)

    verdict = aggregate_verdicts(
        [
            package_result["verdict"],
            spec_result["verdict"],
            target_result["verdict"],
            run_state_result["verdict"],
        ]
    )
    summary = {
        "verdict": verdict,
        "layers": {
            "package": package_result,
            "spec": spec_result,
            "target": target_result,
            "run_state": run_state_result,
        },
        "exit_code": 0 if verdict != "FAIL" else 1,
    }
    write_json(run_root / "validation-summary.json", summary)
    write_text(run_root / "validation-summary.md", _markdown_report(summary))
    return summary
