#!/usr/bin/env python3
"""Regression coverage for runtime provider, package layout, and S5 judge classification."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import stat
import sys
import tempfile
from pathlib import Path
from typing import Any

from runtime_common import ensure_dir, write_json
from runtime_host import invoke_runtime_host


def _load_module(script_name: str, module_name: str):
    script_path = Path(__file__).resolve().parent / script_name
    spec = importlib.util.spec_from_file_location(module_name, script_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load module from {script_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _load_judge_module():
    return _load_module("workflow-s5-judge.py", "workflowprogram_provider_judge_regression_judge")


def _load_package_validator_module():
    validator_path = Path(__file__).resolve().parent / "validators" / "package_contract_validator.py"
    spec = importlib.util.spec_from_file_location(
        "workflowprogram_provider_judge_regression_package_validator",
        validator_path,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load validator module from {validator_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _write_summary(run_root: Path, layers: dict[str, dict[str, Any]]) -> None:
    write_json(
        run_root / "validation-summary.json",
        {
            "verdict": "FAIL",
            "layers": layers,
            "exit_code": 1,
        },
    )
    write_json(
        run_root / "state.json",
        {
            "run_root": str(run_root),
            "verdict": "FAIL",
            "failure_kind": None,
            "status": "failed",
        },
    )


def run_regressions() -> dict[str, Any]:
    judge = _load_judge_module()
    package_validator = _load_package_validator_module()

    env_result = invoke_runtime_host(
        "command_adapter",
        "noop",
        provider_command="definitely-missing-workflowprogram-binary",
    )

    with tempfile.TemporaryDirectory(prefix="workflowprogram-regression-") as temp_dir:
        temp_root = Path(temp_dir)
        broken_package_root = temp_root / "broken-package"
        broken_package_root.mkdir(parents=True, exist_ok=True)
        structure_root = temp_root / "structure-failure"
        runtime_root = temp_root / "runtime-failure"
        fake_bin_root = temp_root / "fake-bin"
        ensure_dir(structure_root / "outputs" / "stages")
        ensure_dir(runtime_root / "outputs" / "stages")
        ensure_dir(fake_bin_root)

        package_layout_result = package_validator.validate_package_contract(broken_package_root)

        fake_opencode = fake_bin_root / "opencode"
        fake_opencode.write_text(
            "#!/usr/bin/env bash\n"
            "echo 'ProviderInitError: credentials missing' >&2\n"
            "exit 2\n",
            encoding="utf-8",
        )
        fake_opencode.chmod(fake_opencode.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        provider_readiness_result = invoke_runtime_host(
            "opencode_native",
            "noop",
            cwd=str(temp_root),
            timeout_seconds=2,
            extra_env={"PATH": f"{fake_bin_root}:{os.environ.get('PATH', '')}"},
        )

        _write_summary(
            structure_root,
            {
                "package": {"verdict": "PASS"},
                "spec": {"verdict": "FAIL"},
                "target": {"verdict": "PASS"},
                "run_state": {"verdict": "PASS"},
            },
        )
        structure_judge = judge.judge_run(structure_root)

        _write_summary(
            runtime_root,
            {
                "package": {"verdict": "PASS"},
                "spec": {"verdict": "PASS"},
                "target": {"verdict": "PASS"},
                "run_state": {"verdict": "FAIL"},
            },
        )
        runtime_judge = judge.judge_run(runtime_root)

        cases = {
            "package_layout_failure": {
                "result": package_layout_result,
                "passed": package_layout_result["verdict"] == "FAIL",
            },
            "environment_skip": {
                "result": env_result,
                "passed": env_result["verdict"] == "ENVIRONMENT-SKIP",
            },
            "provider_readiness_failure": {
                "result": provider_readiness_result,
                "passed": (
                    provider_readiness_result["verdict"] == "FAIL"
                    and "ProviderInitError" in provider_readiness_result.get("message", "")
                ),
            },
            "structure_failure": {
                "result": structure_judge,
                "passed": (
                    structure_judge["verdict"] == "FAIL"
                    and structure_judge["failure_kind"] == "design"
                    and structure_judge["failure_code"] == "S5_SPEC_FAILED"
                ),
            },
            "runtime_failure": {
                "result": runtime_judge,
                "passed": (
                    runtime_judge["verdict"] == "FAIL"
                    and runtime_judge["failure_kind"] == "implementation"
                    and runtime_judge["failure_code"] == "S5_RUN_STATE_FAILED"
                ),
            },
        }

    verdict = "PASS" if all(item["passed"] for item in cases.values()) else "FAIL"
    return {
        "validator": "provider_judge_regression",
        "verdict": verdict,
        "cases": cases,
        "exit_code": 0 if verdict == "PASS" else 1,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run runtime provider and S5 judge regression coverage")
    parser.add_argument("--json", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    result = run_regressions()
    if args.json:
        json.dump(result, sys.stdout, indent=2, ensure_ascii=True)
        sys.stdout.write("\n")
    else:
        print(json.dumps(result, indent=2, ensure_ascii=True))
    return int(result["exit_code"])


if __name__ == "__main__":
    raise SystemExit(main())
