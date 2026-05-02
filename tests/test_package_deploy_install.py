#!/usr/bin/env python3
"""Focused install/deploy regressions."""

from __future__ import annotations

import importlib.util
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = ROOT / "package"
DEPLOY_SCRIPT = PACKAGE_ROOT / ".workflowprogram" / "runtime" / "package-deploy.py"


def _load_package_deploy() -> Any:
    spec = importlib.util.spec_from_file_location("package_deploy", DEPLOY_SCRIPT)
    if spec is None or spec.loader is None:
        raise AssertionError(f"cannot load {DEPLOY_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def assert_existing_managed_venv_is_not_unmanaged_conflict() -> None:
    package_deploy = _load_package_deploy()
    with tempfile.TemporaryDirectory(prefix="wp-install-conflict-") as tmp:
        target = Path(tmp)
        plan = package_deploy._plan_install(PACKAGE_ROOT.resolve(), target.resolve(), "project-local")
        venv_root = plan["venv_root"]
        venv_root.mkdir(parents=True)
        (venv_root / "pyvenv.cfg").write_text("home = test\n", encoding="utf-8", newline="\n")

        conflicts = package_deploy._detect_unmanaged_conflicts(plan, force=False, create_venv=True)
        venv_relative = venv_root.relative_to(target).as_posix()
        if venv_relative in conflicts:
            raise AssertionError(f"existing package venv was reported as unmanaged: {conflicts}")

        unmanaged_command = plan["command_files"][0][1]
        command_path = target / unmanaged_command
        command_path.parent.mkdir(parents=True, exist_ok=True)
        command_path.write_text("unmanaged command\n", encoding="utf-8", newline="\n")
        conflicts = package_deploy._detect_unmanaged_conflicts(plan, force=False, create_venv=True)
        if unmanaged_command not in conflicts:
            raise AssertionError(f"real unmanaged command conflict was not detected: {conflicts}")
        if venv_relative in conflicts:
            raise AssertionError(f"existing package venv was reported with real conflicts: {conflicts}")


def main() -> int:
    assert_existing_managed_venv_is_not_unmanaged_conflict()
    print("package deploy install regression checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
