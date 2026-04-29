#!/usr/bin/env python3
"""Global bootstrap runtime for installing WorkflowProgram into projects."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


BOOTSTRAP_MANIFEST_PATH = ".workflowprogram/bootstrap/bootstrap-manifest.json"
INSTALL_MANIFEST_PATH = ".workflowprogram/package/install-manifest.json"
DEFAULT_SCHEMA_VERSION = "opencode-v2.1"


def _global_root_from_script() -> Path:
    resolved = Path(__file__).resolve()
    if resolved.parent.name == "bootstrap" and resolved.parent.parent.name == ".workflowprogram":
        return resolved.parent.parent.parent
    return Path(os.environ.get("OPENCODE_CONFIG_DIR") or Path.home() / ".config" / "opencode").resolve()


def _manifest_path(global_root: Path) -> Path:
    return global_root / BOOTSTRAP_MANIFEST_PATH


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(payload: Any) -> None:
    json.dump(payload, sys.stdout, indent=2, ensure_ascii=True)
    sys.stdout.write("\n")


def _venv_python(venv_root: Path) -> Path:
    if sys.platform == "win32":
        return venv_root / "Scripts" / "python.exe"
    return venv_root / "bin" / "python"


def _run(cmd: list[str]) -> dict[str, Any]:
    proc = subprocess.run(cmd, capture_output=True, text=True)
    return {
        "command": cmd,
        "exit_code": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
    }


def _load_bootstrap(global_root: Path) -> dict[str, Any]:
    path = _manifest_path(global_root)
    if not path.is_file():
        raise FileNotFoundError(f"Bootstrap manifest not found: {path}")
    manifest = _read_json(path)
    if not isinstance(manifest, dict):
        raise ValueError(f"Bootstrap manifest is not an object: {path}")
    return manifest


def _package_root_from_manifest(manifest: dict[str, Any]) -> Path:
    package_root = manifest.get("cache_package_root")
    if not isinstance(package_root, str) or not package_root:
        raise ValueError("Bootstrap manifest does not contain cache_package_root")
    resolved = Path(package_root).resolve()
    if not (resolved / ".workflowprogram" / "runtime" / "package-deploy.py").is_file():
        raise FileNotFoundError(f"Cached package-deploy.py not found under {resolved}")
    return resolved


def _ensure_project_venv(package_root: Path, target_root: Path, base_python: str, use_lock: bool) -> Path:
    venv_root = target_root / ".workflowprogram" / "package" / ".venv"
    requirements_name = "requirements.lock.txt" if use_lock else "requirements.txt"
    requirements = package_root / ".workflowprogram" / "runtime" / requirements_name
    if not requirements.is_file():
        raise FileNotFoundError(f"Requirements file not found: {requirements}")
    venv_root.parent.mkdir(parents=True, exist_ok=True)
    create_result = _run([base_python, "-m", "venv", str(venv_root)])
    if create_result["exit_code"] != 0:
        raise RuntimeError(create_result["stderr"] or create_result["stdout"] or "venv creation failed")
    python = _venv_python(venv_root)
    install_result = _run([str(python), "-m", "pip", "install", "-r", str(requirements)])
    if install_result["exit_code"] != 0:
        raise RuntimeError(
            install_result["stderr"] or install_result["stdout"] or "dependency install failed"
        )
    return python


def _deploy_script(package_root: Path) -> Path:
    return package_root / ".workflowprogram" / "runtime" / "package-deploy.py"


def _run_deploy(
    package_root: Path,
    action: str,
    target_root: Path,
    python_executable: str,
    extra_args: list[str] | None = None,
) -> dict[str, Any]:
    cmd = [
        python_executable,
        str(_deploy_script(package_root)),
        action,
        "--mode",
        "project-local",
        "--target-root",
        str(target_root),
        "--json",
    ]
    if action == "install":
        cmd.extend(["--source-package-root", str(package_root)])
    if extra_args:
        cmd.extend(extra_args)
    result = _run(cmd)
    try:
        parsed = json.loads(result["stdout"])
    except Exception:
        parsed = {
            "action": action,
            "verdict": "FAIL",
            "summary": "package-deploy.py did not return JSON",
            "stdout": result["stdout"],
            "stderr": result["stderr"],
            "exit_code": result["exit_code"] or 1,
        }
    return parsed


def install_project(args: argparse.Namespace, manifest: dict[str, Any]) -> dict[str, Any]:
    target_root = Path(args.target_root).resolve()
    package_root = Path(args.source_package_root).resolve() if args.source_package_root else _package_root_from_manifest(manifest)
    base_python = args.python or ("python" if sys.platform == "win32" else "python3")
    runner_python = base_python
    warnings: list[str] = []
    if args.create_venv:
        try:
            runner_python = str(_ensure_project_venv(package_root, target_root, base_python, args.use_lock))
        except Exception as exc:
            return {
                "action": "bootstrap-install",
                "verdict": "FAIL",
                "summary": "Project venv provisioning failed before package install.",
                "target_root": str(target_root),
                "package_root": str(package_root),
                "error": str(exc),
                "exit_code": 3,
            }
        warnings.append("Project venv was pre-provisioned so package-deploy.py can run without system PyYAML.")

    extra_args = []
    if args.create_venv:
        extra_args.append("--create-venv")
        extra_args.extend(["--python", runner_python])
    if args.use_lock:
        extra_args.append("--use-lock")
    if args.force:
        extra_args.append("--force")
    result = _run_deploy(package_root, "install", target_root, runner_python, extra_args)
    result["bootstrap_action"] = "install"
    result["bootstrap_schema_version"] = manifest.get("schema_version", DEFAULT_SCHEMA_VERSION)
    result["bootstrap_package_root"] = str(package_root)
    if warnings:
        result.setdefault("warnings", [])
        if isinstance(result["warnings"], list):
            result["warnings"].extend(warnings)
    return result


def status_project(args: argparse.Namespace, manifest: dict[str, Any]) -> dict[str, Any]:
    target_root = Path(args.target_root).resolve()
    package_root = _package_root_from_manifest(manifest)
    python = args.python or _python_from_project_manifest(target_root) or ("python" if sys.platform == "win32" else "python3")
    result = _run_deploy(package_root, "status", target_root, python)
    result["bootstrap_action"] = "status"
    result["bootstrap_package_root"] = str(package_root)
    return result


def uninstall_project(args: argparse.Namespace, manifest: dict[str, Any]) -> dict[str, Any]:
    target_root = Path(args.target_root).resolve()
    package_root = _package_root_from_manifest(manifest)
    python = args.python or _python_from_project_manifest(target_root) or ("python" if sys.platform == "win32" else "python3")
    result = _run_deploy(package_root, "uninstall", target_root, python)
    result["bootstrap_action"] = "uninstall"
    result["bootstrap_package_root"] = str(package_root)
    return result


def _python_from_project_manifest(target_root: Path) -> str | None:
    manifest_path = target_root / INSTALL_MANIFEST_PATH
    if not manifest_path.is_file():
        return None
    try:
        manifest = _read_json(manifest_path)
    except Exception:
        return None
    python = manifest.get("python_executable") if isinstance(manifest, dict) else None
    if isinstance(python, str) and python:
        return python
    return None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="WorkflowProgram global bootstrap runtime")
    parser.add_argument("--global-root", help="OpenCode global config root; defaults to OPENCODE_CONFIG_DIR or ~/.config/opencode")
    parser.add_argument("--json", action="store_true")
    subparsers = parser.add_subparsers(dest="action", required=True)

    install = subparsers.add_parser("install", help="Install WorkflowProgram into the current project")
    install.add_argument("--target-root", default=".")
    install.add_argument("--source-package-root", help="Override cached package root")
    install.add_argument("--create-venv", action="store_true")
    install.add_argument("--python", help="Base Python interpreter")
    install.add_argument("--use-lock", action="store_true")
    install.add_argument("--force", action="store_true")
    install.add_argument("--json", action="store_true")

    status = subparsers.add_parser("status", help="Inspect the current project's WorkflowProgram install")
    status.add_argument("--target-root", default=".")
    status.add_argument("--python", help="Python interpreter for package-deploy.py")
    status.add_argument("--json", action="store_true")

    upgrade = subparsers.add_parser("upgrade", help="Reinstall the current project from the bootstrap cache")
    upgrade.add_argument("--target-root", default=".")
    upgrade.add_argument("--create-venv", action="store_true")
    upgrade.add_argument("--python", help="Base Python interpreter")
    upgrade.add_argument("--use-lock", action="store_true")
    upgrade.add_argument("--force", action="store_true", default=True)
    upgrade.add_argument("--json", action="store_true")

    uninstall = subparsers.add_parser("uninstall", help="Remove WorkflowProgram from the current project")
    uninstall.add_argument("--target-root", default=".")
    uninstall.add_argument("--python", help="Python interpreter for package-deploy.py")
    uninstall.add_argument("--json", action="store_true")

    return parser


def main() -> int:
    args = build_parser().parse_args()
    global_root = Path(args.global_root).resolve() if args.global_root else _global_root_from_script()
    try:
        manifest = _load_bootstrap(global_root)
        if args.action == "install":
            result = install_project(args, manifest)
        elif args.action == "status":
            result = status_project(args, manifest)
        elif args.action == "upgrade":
            result = install_project(args, manifest)
            result["bootstrap_action"] = "upgrade"
        else:
            result = uninstall_project(args, manifest)
    except Exception as exc:
        result = {
            "action": f"bootstrap-{args.action}",
            "verdict": "FAIL",
            "summary": "WorkflowProgram bootstrap failed.",
            "global_root": str(global_root),
            "error": str(exc),
            "exit_code": 1,
        }

    if args.json:
        _write_json(result)
    else:
        sys.stdout.write(f"[{result.get('verdict')}] {result.get('summary', result.get('action'))}\n")
        for key, value in result.items():
            if key in {"summary", "exit_code"}:
                continue
            sys.stdout.write(f"{key}: {value}\n")
    return int(result.get("exit_code", 0))


if __name__ == "__main__":
    raise SystemExit(main())
