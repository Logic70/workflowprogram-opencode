#!/usr/bin/env python3
"""Minimal end-to-end smoke harness for WorkflowProgram OpenCode package."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
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
    runtime_host = runtime_root / "runtime_host.py"
    host_integration_smoke = runtime_root / "host-integration-smoke.py"
    provider_judge_regression = runtime_root / "provider-judge-regression.py"
    package_validator = runtime_root / "validators" / "package_contract_validator.py"
    deploy_script = runtime_root / "package-deploy.py"
    python_executable = sys.executable or "python3"

    temp_parent = Path("/tmp") if Path("/tmp").is_dir() else None
    temp_dir = tempfile.mkdtemp(prefix="workflowprogram-smoke-", dir=str(temp_parent) if temp_parent else None)
    try:
        install_root = Path(temp_dir) / "project"
        install_root.mkdir(parents=True, exist_ok=True)
        bootstrap_global_root = Path(temp_dir) / "global-opencode"
        bootstrap_cache_root = Path(temp_dir) / "cache"
        bootstrap_project_root = Path(temp_dir) / "bootstrap-project"
        bootstrap_project_root.mkdir(parents=True, exist_ok=True)

        package_result = run_cmd(
            [python_executable, str(package_validator), "--package-root", str(package_root), "--json"]
        )
        fixture_probe_result = run_cmd(
            [
                python_executable,
                str(runtime_host),
                "probe",
                "--provider",
                "fixture_host",
                "--json",
            ]
        )
        opencode_probe_result = run_cmd(
            [
                python_executable,
                str(runtime_host),
                "probe",
                "--provider",
                "opencode_native",
                "--json",
            ]
        )
        provider_judge_regression_result = run_cmd(
            [
                python_executable,
                str(provider_judge_regression),
                "--json",
            ]
        )
        install_result = run_cmd(
            [
                python_executable,
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
        status_result = run_cmd(
            [
                python_executable,
                str(deploy_script),
                "status",
                "--mode",
                "project-local",
                "--target-root",
                str(install_root),
                "--json",
            ]
        )
        reinstall_result = run_cmd(
            [
                python_executable,
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
        install_bootstrap_result = run_cmd(
            [
                python_executable,
                str(deploy_script),
                "install-bootstrap",
                "--source-package-root",
                str(package_root),
                "--target-root",
                str(bootstrap_global_root),
                "--cache-root",
                str(bootstrap_cache_root),
                "--version",
                "smoke",
                "--json",
            ]
        )
        bootstrap_status_result = run_cmd(
            [
                python_executable,
                str(deploy_script),
                "bootstrap-status",
                "--target-root",
                str(bootstrap_global_root),
                "--json",
            ]
        )
        bootstrap_runtime = bootstrap_global_root / ".workflowprogram" / "bootstrap" / "bootstrap-runtime.py"
        bootstrap_project_install_result = run_cmd(
            [
                python_executable,
                str(bootstrap_runtime),
                "--global-root",
                str(bootstrap_global_root),
                "install",
                "--target-root",
                str(bootstrap_project_root),
                "--json",
            ]
        )
        bootstrap_project_status_result = run_cmd(
            [
                python_executable,
                str(bootstrap_runtime),
                "--global-root",
                str(bootstrap_global_root),
                "status",
                "--target-root",
                str(bootstrap_project_root),
                "--json",
            ]
        )
        deployed_runtime_root = install_root / ".workflowprogram" / "package" / "runtime"
        deployed_runtime_entry = deployed_runtime_root / "workflow-entry.py"
        deployed_package_validator = deployed_runtime_root / "validators" / "package_contract_validator.py"
        deployed_package_result = run_cmd(
            [python_executable, str(deployed_package_validator), "--package-root", str(install_root), "--json"]
        )
        doctor_result = run_cmd(
            [
                python_executable,
                str(deployed_runtime_root / "doctor.py"),
                "--package-root",
                str(install_root),
                "--target-root",
                str(install_root),
                "--json",
            ]
        )
        develop_result = run_cmd(
            [
                python_executable,
                str(deployed_runtime_entry),
                "develop",
                "--package-root",
                str(install_root),
                "--target-root",
                str(install_root),
                "--user-arguments",
                "smoke target workflow --emit-target-command --emit-target-plugin",
                "--confirmed",
                "--allow-template-fallback",
                "--json",
            ]
        )
        preflight_result = run_cmd(
            [
                python_executable,
                str(deployed_runtime_entry),
                "preflight",
                "--package-root",
                str(install_root),
                "--target-root",
                str(install_root),
                "--user-arguments",
                "smoke readiness check",
                "--json",
            ]
        )
        hotfix_result = run_cmd(
            [
                python_executable,
                str(deployed_runtime_entry),
                "hotfix",
                "--package-root",
                str(install_root),
                "--target-root",
                str(install_root),
                "--user-arguments",
                "smoke hotfix update --emit-target-command --emit-target-plugin",
                "--json",
            ]
        )
        iterate_result = run_cmd(
            [
                python_executable,
                str(deployed_runtime_entry),
                "iterate",
                "--package-root",
                str(install_root),
                "--target-root",
                str(install_root),
                "--user-arguments",
                "smoke iterate update --emit-target-command --emit-target-plugin",
                "--json",
            ]
        )
        audit_result = run_cmd(
            [
                python_executable,
                str(deployed_runtime_entry),
                "audit",
                "--package-root",
                str(install_root),
                "--target-root",
                str(install_root),
                "--user-arguments",
                "smoke audit",
                "--json",
            ]
        )
        evolve_result = run_cmd(
            [
                python_executable,
                str(deployed_runtime_entry),
                "evolve",
                "--package-root",
                str(install_root),
                "--target-root",
                str(install_root),
                "--user-arguments",
                "smoke evolve update --emit-target-command --emit-target-plugin",
                "--json",
            ]
        )
        orchestrate_result = run_cmd(
            [
                python_executable,
                str(deployed_runtime_entry),
                "orchestrate",
                "--package-root",
                str(install_root),
                "--target-root",
                str(install_root),
                "--user-arguments",
                "please audit this workflow",
                "--json",
            ]
        )
        ship_result = run_cmd(
            [
                python_executable,
                str(deployed_runtime_entry),
                "ship",
                "--package-root",
                str(install_root),
                "--target-root",
                str(install_root),
                "--user-arguments",
                "smoke ship readiness",
                "--json",
            ]
        )
        validate_result = run_cmd(
            [
                python_executable,
                str(deployed_runtime_entry),
                "validate",
                "--package-root",
                str(install_root),
                "--target-root",
                str(install_root),
                "--json",
            ]
        )
        host_integration_result = run_cmd(
            [
                python_executable,
                str(host_integration_smoke),
                "--package-root",
                str(install_root),
                "--target-root",
                str(install_root),
                "--timeout-seconds",
                "15",
                "--json",
            ]
        )
        target_host_result = run_cmd(
            [
                python_executable,
                str(deployed_runtime_root / "target-host-smoke.py"),
                "--target-root",
                str(install_root),
                "--timeout-seconds",
                "15",
                "--json",
            ]
        )

        summary = {
            "package": package_result,
            "runtime_host_fixture_probe": fixture_probe_result,
            "runtime_host_opencode_probe": opencode_probe_result,
            "provider_judge_regression": provider_judge_regression_result,
            "install": install_result,
            "status": status_result,
            "reinstall": reinstall_result,
            "install_bootstrap": install_bootstrap_result,
            "bootstrap_status": bootstrap_status_result,
            "bootstrap_project_install": bootstrap_project_install_result,
            "bootstrap_project_status": bootstrap_project_status_result,
            "deployed_package": deployed_package_result,
            "doctor": doctor_result,
            "develop": develop_result,
            "preflight": preflight_result,
            "hotfix": hotfix_result,
            "iterate": iterate_result,
            "audit": audit_result,
            "evolve": evolve_result,
            "orchestrate": orchestrate_result,
            "ship": ship_result,
            "validate": validate_result,
            "host_integration": host_integration_result,
            "target_host": target_host_result,
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
            and fixture_probe_result["exit_code"] == 0
            and provider_judge_regression_result["exit_code"] == 0
            and install_result["exit_code"] == 0
            and status_result["exit_code"] == 0
            and reinstall_result["exit_code"] == 0
            and install_bootstrap_result["exit_code"] == 0
            and bootstrap_status_result["exit_code"] == 0
            and bootstrap_project_install_result["exit_code"] == 0
            and bootstrap_project_status_result["exit_code"] == 0
            and deployed_package_result["exit_code"] == 0
            and doctor_result["exit_code"] == 0
            and develop_result["exit_code"] == 0
            and preflight_result["exit_code"] == 0
            and hotfix_result["exit_code"] == 0
            and iterate_result["exit_code"] == 0
            and audit_result["exit_code"] == 0
            and evolve_result["exit_code"] == 0
            and orchestrate_result["exit_code"] == 0
            and ship_result["exit_code"] == 0
            and validate_result["exit_code"] == 0
            and host_integration_result["exit_code"] == 0
            and target_host_result["exit_code"] == 0
        )
        return 0 if ok else 1
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
