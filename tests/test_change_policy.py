#!/usr/bin/env python3
"""Regression checks for controlled change policy and entry exposure."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = ROOT / "package"
ENTRY = PACKAGE_ROOT / ".workflowprogram" / "runtime" / "workflow-entry.py"
RESOLVE = PACKAGE_ROOT / ".workflowprogram" / "runtime" / "resolve-change-context.py"
VALIDATE = PACKAGE_ROOT / ".workflowprogram" / "runtime" / "validate-change-policy.py"
PKG_VALIDATOR = PACKAGE_ROOT / ".workflowprogram" / "runtime" / "validators" / "package_contract_validator.py"


def run_entry(intent: str, target: Path, args: list[str], expect_code: int = 0) -> dict[str, Any]:
    command = [
        sys.executable,
        str(ENTRY),
        intent,
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
    return json.loads(completed.stdout)


def create_target_workflow(target: Path) -> dict[str, Any]:
    return run_entry(
        "develop",
        target,
        [
            "--user-arguments",
            "design a smoke workflow --emit-target-command",
            "--confirmed",
            "--allow-template-fallback",
        ],
    )


def assert_evolve_requires_concrete_confirmed_change() -> None:
    with tempfile.TemporaryDirectory(prefix="wp-change-missing-") as tmp:
        target = Path(tmp)
        create_target_workflow(target)
        result = run_entry(
            "evolve",
            target,
            ["--user-arguments", "", "--confirmed"],
            expect_code=3,
        )
        if result["verdict"] != "FAIL":
            raise AssertionError(f"expected FAIL, got {result['verdict']}")
        failures = set(result["change_policy"].get("failure_categories", []))
        if "missing_change_request" not in failures:
            raise AssertionError(f"missing request was not reported: {result}")


def assert_evolve_emits_change_policy_evidence() -> None:
    with tempfile.TemporaryDirectory(prefix="wp-change-valid-") as tmp:
        target = Path(tmp)
        create_target_workflow(target)
        result = run_entry(
            "evolve",
            target,
            [
                "--user-arguments",
                "evolve workflow to add stronger verifier gate --confirmed",
                "--confirmed",
            ],
        )
        if result["verdict"] != "PASS":
            raise AssertionError(f"expected PASS, got {result['verdict']}: {result}")
        run_root = Path(result["run_root"])
        for rel_path in (
            "outputs/change-policy/change-context.json",
            "outputs/change-policy/change-policy-summary.json",
            "outputs/stages/s3-change-policy.json",
        ):
            if not (run_root / rel_path).is_file():
                raise AssertionError(f"missing change-policy evidence: {rel_path}")
        judge_checks = result["judge"].get("checks", [])
        passed = {check.get("name") for check in judge_checks if check.get("status") == "PASS"}
        if "change_policy_validation_passed" not in passed:
            raise AssertionError(f"S5 did not pass change policy check: {judge_checks}")


def assert_stale_context_is_rejected() -> None:
    with tempfile.TemporaryDirectory(prefix="wp-change-stale-") as tmp:
        target = Path(tmp)
        run_root = target / ".workflowprogram" / "runs" / "manual"
        candidate = target / "candidate"
        (target / ".workflowprogram" / "design").mkdir(parents=True)
        (target / ".workflowprogram" / "design" / "workflow-spec.yaml").write_text("meta:\n  name: old\n", encoding="utf-8")
        (candidate / ".workflowprogram" / "design").mkdir(parents=True)
        (candidate / ".workflowprogram" / "design" / "workflow-spec.yaml").write_text("meta:\n  name: new\n", encoding="utf-8")
        resolved = subprocess.run(
            [
                sys.executable,
                str(RESOLVE),
                "--intent",
                "evolve",
                "--target-root",
                str(target),
                "--run-root",
                str(run_root),
                "--candidate-root",
                str(candidate),
                "--user-arguments",
                "evolve existing workflow",
                "--confirmed",
                "--json",
            ],
            cwd=str(ROOT),
            text=True,
            capture_output=True,
            check=True,
        )
        context = json.loads(resolved.stdout)
        (target / ".workflowprogram" / "design" / "workflow-spec.yaml").write_text("meta:\n  name: changed\n", encoding="utf-8")
        context_path = run_root / "context.json"
        context_path.write_text(json.dumps(context), encoding="utf-8")
        completed = subprocess.run(
            [
                sys.executable,
                str(VALIDATE),
                "--context",
                str(context_path),
                "--target-root",
                str(target),
                "--candidate-root",
                str(candidate),
                "--json",
            ],
            cwd=str(ROOT),
            text=True,
            capture_output=True,
        )
        if completed.returncode == 0:
            raise AssertionError("stale context passed change policy validation")
        payload = json.loads(completed.stdout)
        if "stale_change_context" not in set(payload.get("failure_categories", [])):
            raise AssertionError(f"stale context was not reported: {payload}")


def assert_undeclared_write_is_rejected() -> None:
    with tempfile.TemporaryDirectory(prefix="wp-change-undeclared-") as tmp:
        target = Path(tmp)
        run_root = target / ".workflowprogram" / "runs" / "manual"
        candidate = target / "candidate"
        spec_path = target / ".workflowprogram" / "design" / "workflow-spec.yaml"
        spec_path.parent.mkdir(parents=True)
        spec_path.write_text("meta:\n  name: base\n", encoding="utf-8")
        plugin_path = candidate / ".opencode" / "plugins" / "target.ts"
        plugin_path.parent.mkdir(parents=True)
        plugin_path.write_text("export default {}\n", encoding="utf-8")
        context = {
            "intent": "evolve",
            "target_root": str(target),
            "target_workflow_exists": True,
            "base_spec_sha256": __import__("hashlib").sha256(spec_path.read_bytes()).hexdigest(),
            "change_request": "evolve plugin bridge",
            "change_mode": "redesign",
            "declared_write_scope": [".workflowprogram/design/**"],
            "confirmed": True,
        }
        context_path = target / "context.json"
        context_path.write_text(json.dumps(context), encoding="utf-8")
        completed = subprocess.run(
            [
                sys.executable,
                str(VALIDATE),
                "--context",
                str(context_path),
                "--target-root",
                str(target),
                "--candidate-root",
                str(candidate),
                "--run-root",
                str(run_root),
                "--json",
            ],
            cwd=str(ROOT),
            text=True,
            capture_output=True,
        )
        if completed.returncode == 0:
            raise AssertionError("undeclared write passed change policy validation")
        payload = json.loads(completed.stdout)
        if "undeclared_write" not in set(payload.get("failure_categories", [])):
            raise AssertionError(f"undeclared write was not reported: {payload}")


def assert_entry_exposure_contract() -> None:
    completed = subprocess.run(
        [sys.executable, str(PKG_VALIDATOR), "--package-root", str(PACKAGE_ROOT), "--json"],
        cwd=str(ROOT),
        text=True,
        capture_output=True,
    )
    if completed.returncode != 0:
        raise AssertionError(f"package contract failed:\n{completed.stdout}\n{completed.stderr}")
    payload = json.loads(completed.stdout)
    passed = {check["id"] for check in payload["checks"] if check["passed"]}
    for check_id in ("INT-02", "CHG-01", "DOC-01"):
        if check_id not in passed:
            raise AssertionError(f"{check_id} did not pass: {payload}")


def main() -> int:
    assert_evolve_requires_concrete_confirmed_change()
    assert_evolve_emits_change_policy_evidence()
    assert_stale_context_is_rejected()
    assert_undeclared_write_is_rejected()
    assert_entry_exposure_contract()
    print("change policy regression checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
