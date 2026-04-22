#!/usr/bin/env python3
"""Minimal end-to-end smoke harness for WorkflowProgram OpenCode package."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import tempfile
from pathlib import Path


def run_cmd(cmd: list[str]) -> dict[str, object]:
    proc = subprocess.run(cmd, capture_output=True, text=True)
    return {
        "command": cmd,
        "exit_code": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="WorkflowProgram smoke harness")
    parser.add_argument("--package-root", required=True)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    package_root = Path(args.package_root).resolve()
    runtime_root = package_root / ".workflowprogram" / "runtime"
    runtime_entry = runtime_root / "workflow-entry.py"
    package_validator = runtime_root / "validators" / "package_contract_validator.py"
    deploy_script = runtime_root / "package-deploy.py"

    with tempfile.TemporaryDirectory(prefix="workflowprogram-smoke-") as temp_dir:
        install_root = Path(temp_dir) / "project"
        install_root.mkdir(parents=True, exist_ok=True)

        package_result = run_cmd(
            ["python3", str(package_validator), "--package-root", str(package_root), "--json"]
        )
        install_result = run_cmd(
            [
                "python3",
                str(deploy_script),
                "install",
                "--source-package-root",
                str(package_root),
                "--mode",
                "project-local",
                "--target-root",
                str(install_root),
                "--json",
            ]
        )
        deployed_runtime_root = install_root / ".workflowprogram" / "package" / "runtime"
        deployed_runtime_entry = deployed_runtime_root / "workflow-entry.py"
        deployed_package_validator = deployed_runtime_root / "validators" / "package_contract_validator.py"
        deployed_package_result = run_cmd(
            ["python3", str(deployed_package_validator), "--package-root", str(install_root), "--json"]
        )
        develop_result = run_cmd(
            [
                "python3",
                str(deployed_runtime_entry),
                "develop",
                "--package-root",
                str(install_root),
                "--target-root",
                str(install_root),
                "--user-arguments",
                "smoke target workflow --emit-target-command --emit-target-plugin",
                "--json",
            ]
        )
        validate_result = run_cmd(
            [
                "python3",
                str(deployed_runtime_entry),
                "validate",
                "--package-root",
                str(install_root),
                "--target-root",
                str(install_root),
                "--json",
            ]
        )

        summary = {
            "package": package_result,
            "install": install_result,
            "deployed_package": deployed_package_result,
            "develop": develop_result,
            "validate": validate_result,
            "target_root": str(install_root),
            "target_files": sorted(
                str(path.relative_to(install_root))
                for path in install_root.rglob("*")
                if path.is_file()
                and "__pycache__" not in path.parts
                and path.suffix != ".pyc"
            ),
        }

        if args.json:
            print(json.dumps(summary, indent=2, ensure_ascii=True))
        else:
            print(json.dumps(summary, indent=2, ensure_ascii=True))

        ok = (
            package_result["exit_code"] == 0
            and install_result["exit_code"] == 0
            and deployed_package_result["exit_code"] == 0
            and develop_result["exit_code"] == 0
            and validate_result["exit_code"] == 0
        )
        shutil.rmtree(install_root, ignore_errors=True)
        return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
