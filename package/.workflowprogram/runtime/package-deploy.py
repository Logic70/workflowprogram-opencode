#!/usr/bin/env python3
"""Install or remove the WorkflowProgram OpenCode package layout."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


RUNTIME_DIR = Path(__file__).resolve().parent
if str(RUNTIME_DIR) not in sys.path:
    sys.path.insert(0, str(RUNTIME_DIR))

from runtime_common import (  # noqa: E402
    INSTALL_MANIFEST_PATH,
    PACKAGE_COMMAND_PREFIX,
    PACKAGE_PLUGIN_FILE,
    REQUIRED_PACKAGE_COMMANDS,
    SCHEMA_VERSION,
    default_global_config_root,
    detect_package_layout,
    ensure_dir,
    infer_package_root_from_runtime_dir,
    iso_now,
    read_json,
    write_json,
)


BACKUP_CONFIG_PATH = ".workflowprogram/package/opencode.json.backup"
VENV_RELATIVE_PATH = ".workflowprogram/package/.venv"
REQUIREMENTS_FILE = "requirements.txt"
REQUIREMENTS_LOCK_FILE = "requirements.lock.txt"


def _read_json_file(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_text_file(path: Path, content: str) -> None:
    ensure_dir(path.parent)
    path.write_text(content, encoding="utf-8", newline="\n")


def _copy_file(source: Path, destination: Path) -> None:
    ensure_dir(destination.parent)
    shutil.copy2(source, destination)


def _iter_runtime_files(runtime_root: Path) -> list[Path]:
    files: list[Path] = []
    for candidate in sorted(runtime_root.rglob("*")):
        if not candidate.is_file():
            continue
        relative = candidate.relative_to(runtime_root)
        if "__pycache__" in relative.parts or candidate.suffix == ".pyc":
            continue
        files.append(candidate)
    return files


def _deepcopy_json(payload: dict[str, Any]) -> dict[str, Any]:
    return json.loads(json.dumps(payload, ensure_ascii=True))


def _merge_opencode_config(existing: dict[str, Any], source: dict[str, Any]) -> dict[str, Any]:
    merged = _deepcopy_json(existing)
    if "$schema" not in merged and "$schema" in source:
        merged["$schema"] = source["$schema"]

    source_permission = source.get("permission", {})
    if isinstance(source_permission, dict):
        merged_permission = merged.setdefault("permission", {})
        if isinstance(merged_permission, dict):
            source_edit = source_permission.get("edit")
            if source_edit is not None and "edit" not in merged_permission:
                merged_permission["edit"] = source_edit

            source_bash = source_permission.get("bash", {})
            if isinstance(source_bash, dict):
                merged_bash = merged_permission.get("bash", {})
                if not isinstance(merged_bash, dict):
                    merged_bash = {}
                for key, value in source_bash.items():
                    merged_bash.setdefault(key, value)
                merged_permission["bash"] = merged_bash

    source_watcher = source.get("watcher", {})
    if isinstance(source_watcher, dict):
        merged_watcher = merged.setdefault("watcher", {})
        if isinstance(merged_watcher, dict):
            merged_ignore = merged_watcher.get("ignore", [])
            if not isinstance(merged_ignore, list):
                merged_ignore = []
            source_ignore = source_watcher.get("ignore", [])
            if isinstance(source_ignore, list):
                for value in source_ignore:
                    if value not in merged_ignore:
                        merged_ignore.append(value)
            merged_watcher["ignore"] = merged_ignore

    return merged


def _resolve_install_root(mode: str, target_root: str | None) -> Path:
    if mode == "global":
        return Path(target_root).resolve() if target_root else default_global_config_root().resolve()
    if not target_root:
        raise ValueError("--target-root is required for project-local install")
    return Path(target_root).resolve()


def _installed_command_paths(root: Path, mode: str, source_layout: Any) -> list[tuple[Path, str]]:
    commands_dir = (root / ".opencode" / "commands") if mode == "project-local" else (root / "commands")
    files = []
    for command in sorted(source_layout.commands_dir.glob("*.md")):
        if not command.stem.startswith(PACKAGE_COMMAND_PREFIX):
            continue
        files.append((command, str((commands_dir / command.name).relative_to(root).as_posix())))
    return files


def _installed_agent_paths(root: Path, mode: str, source_layout: Any) -> list[tuple[Path, str]]:
    agents_dir = (root / ".opencode" / "agents") if mode == "project-local" else (root / "agents")
    files = []
    for agent in sorted(source_layout.agents_dir.glob("*.md")):
        files.append((agent, str((agents_dir / agent.name).relative_to(root).as_posix())))
    return files


def _runtime_destination_root(root: Path) -> Path:
    return root / ".workflowprogram" / "package" / "runtime"


def _venv_root(root: Path) -> Path:
    return root / ".workflowprogram" / "package" / ".venv"


def _venv_python(venv_root: Path) -> Path:
    if sys.platform == "win32":
        return venv_root / "Scripts" / "python.exe"
    return venv_root / "bin" / "python"


def _plugin_destination(root: Path, mode: str) -> Path:
    plugins_dir = (root / ".opencode" / "plugins") if mode == "project-local" else (root / "plugins")
    return plugins_dir / PACKAGE_PLUGIN_FILE


def _assert_installable_target(source_root: Path, install_root: Path, mode: str) -> None:
    if mode == "project-local" and source_root.resolve() == install_root.resolve():
        raise ValueError("project-local install target must not be the source package root itself")


def _plan_install(source_root: Path, install_root: Path, mode: str) -> dict[str, Any]:
    source_layout = detect_package_layout(source_root)
    command_files = _installed_command_paths(install_root, mode, source_layout)
    agent_files = _installed_agent_paths(install_root, mode, source_layout)
    runtime_dest_root = _runtime_destination_root(install_root)

    runtime_files: list[tuple[Path, str]] = []
    for runtime_file in _iter_runtime_files(source_layout.runtime_root):
        relative = runtime_file.relative_to(source_layout.runtime_root)
        destination = runtime_dest_root / relative
        runtime_files.append((runtime_file, str(destination.relative_to(install_root).as_posix())))

    plugin_destination = _plugin_destination(install_root, mode)
    return {
        "source_layout": source_layout,
        "install_root": install_root,
        "mode": mode,
        "command_files": command_files,
        "agent_files": agent_files,
        "runtime_files": runtime_files,
        "plugin_file": (source_layout.plugin_file, str(plugin_destination.relative_to(install_root).as_posix())),
        "config_path": install_root / "opencode.json",
        "manifest_path": install_root / INSTALL_MANIFEST_PATH,
        "backup_config_path": install_root / BACKUP_CONFIG_PATH,
        "venv_root": _venv_root(install_root),
        "requirements_relative": str((runtime_dest_root / REQUIREMENTS_FILE).relative_to(install_root).as_posix()),
        "requirements_lock_relative": str((runtime_dest_root / REQUIREMENTS_LOCK_FILE).relative_to(install_root).as_posix()),
    }


def _detect_unmanaged_conflicts(plan: dict[str, Any], force: bool, create_venv: bool) -> list[str]:
    if force:
        return []
    manifest_path: Path = plan["manifest_path"]
    managed_files: set[str] = set()
    if manifest_path.exists():
        try:
            manifest = read_json(manifest_path)
            managed_files = set(manifest.get("installed_files", []))
        except Exception:
            managed_files = set()

    conflicts: list[str] = []
    all_targets = [relative for _, relative in plan["command_files"]]
    all_targets.extend(relative for _, relative in plan["agent_files"])
    all_targets.append(plan["plugin_file"][1])
    all_targets.extend(relative for _, relative in plan["runtime_files"])
    if create_venv:
        all_targets.append(str(plan["venv_root"].relative_to(plan["install_root"]).as_posix()))

    for relative in all_targets:
        target_path = plan["install_root"] / relative
        if target_path.exists() and relative not in managed_files:
            conflicts.append(relative)
    return conflicts


def _run_checked(cmd: list[str], cwd: Path | None = None) -> tuple[bool, str]:
    proc = subprocess.run(cmd, capture_output=True, text=True, cwd=str(cwd) if cwd else None)
    if proc.returncode == 0:
        return True, proc.stdout.strip()
    detail = proc.stderr.strip() or proc.stdout.strip() or f"exit_code={proc.returncode}"
    return False, detail


def _provision_venv(base_python: str, venv_root: Path, requirements_path: Path) -> tuple[bool, dict[str, Any]]:
    ensure_dir(venv_root.parent)
    ok, detail = _run_checked([base_python, "-m", "venv", str(venv_root)])
    if not ok:
        return False, {"step": "create-venv", "detail": detail}
    venv_python = _venv_python(venv_root)
    ok, detail = _run_checked([str(venv_python), "-m", "pip", "install", "-r", str(requirements_path)])
    if not ok:
        return False, {"step": "install-requirements", "detail": detail}
    return True, {
        "step": "completed",
        "python_executable": str(venv_python),
        "requirements_path": str(requirements_path),
    }


def install_package(
    source_package_root: Path,
    mode: str,
    target_root: str | None,
    create_venv: bool = False,
    python_executable: str | None = None,
    force: bool = False,
    use_lock: bool = False,
) -> dict[str, Any]:
    source_root = source_package_root.resolve()
    install_root = _resolve_install_root(mode, target_root)
    _assert_installable_target(source_root, install_root, mode)
    plan = _plan_install(source_root, install_root, mode)

    conflicts = _detect_unmanaged_conflicts(plan, force, create_venv)
    if conflicts:
        return {
            "action": "install",
            "verdict": "FAIL",
            "summary": "Install target contains unmanaged WorkflowProgram paths.",
            "mode": mode,
            "source_package_root": str(source_root),
            "install_root": str(install_root),
            "conflicts": conflicts,
            "exit_code": 2,
        }

    ensure_dir(install_root)
    source_config = _read_json_file(plan["source_layout"].config_path)
    config_path: Path = plan["config_path"]
    config_status = "created"
    warnings: list[str] = []
    if config_path.exists():
        try:
            existing_config = _read_json_file(config_path)
            _copy_file(config_path, plan["backup_config_path"])
            merged = _merge_opencode_config(existing_config, source_config)
            write_json(config_path, merged)
            config_status = "merged"
        except Exception as exc:
            config_status = "skipped-invalid-json"
            warnings.append(f"opencode.json merge skipped: {exc}")
    else:
        write_json(config_path, source_config)

    installed_files: list[str] = []
    for source, relative in plan["command_files"]:
        destination = install_root / relative
        _copy_file(source, destination)
        installed_files.append(relative)

    for source, relative in plan["agent_files"]:
        destination = install_root / relative
        _copy_file(source, destination)
        installed_files.append(relative)

    source_plugin, plugin_relative = plan["plugin_file"]
    _copy_file(source_plugin, install_root / plugin_relative)
    installed_files.append(plugin_relative)

    for source, relative in plan["runtime_files"]:
        _copy_file(source, install_root / relative)
        installed_files.append(relative)

    selected_python = python_executable or sys.executable
    venv_info: dict[str, Any] | None = None
    requirements_relative = plan["requirements_lock_relative"] if use_lock else plan["requirements_relative"]
    if create_venv:
        provisioned, venv_info = _provision_venv(
            base_python=selected_python,
            venv_root=plan["venv_root"],
            requirements_path=install_root / requirements_relative,
        )
        if not provisioned:
            return {
                "action": "install",
                "verdict": "FAIL",
                "summary": "WorkflowProgram venv provisioning failed.",
                "mode": mode,
                "source_package_root": str(source_root),
                "install_root": str(install_root),
                "runtime_root": str(_runtime_destination_root(install_root)),
                "venv_root": str(plan["venv_root"]),
                "python_executable": selected_python,
                "venv_error": venv_info,
                "exit_code": 3,
            }
        selected_python = str(_venv_python(plan["venv_root"]))

    manifest = {
        "schema_version": SCHEMA_VERSION,
        "installed_at": iso_now(),
        "mode": mode,
        "source_package_root": str(source_root),
        "install_root": str(install_root),
        "config_path": str(config_path),
        "config_status": config_status,
        "config_backup": (
            str(plan["backup_config_path"].relative_to(install_root).as_posix())
            if plan["backup_config_path"].exists()
            else None
        ),
        "created_config": source_config if config_status == "created" else None,
        "installed_files": sorted(installed_files),
        "managed_directories": (
            [str(plan["venv_root"].relative_to(install_root).as_posix())] if create_venv else []
        ),
        "required_package_commands": list(REQUIRED_PACKAGE_COMMANDS),
        "requirements_relative": requirements_relative,
        "requirements_mode": "lock" if use_lock else "range",
        "create_venv": create_venv,
        "venv_root": (
            str(plan["venv_root"].relative_to(install_root).as_posix()) if create_venv else None
        ),
        "python_executable": selected_python,
        "warnings": warnings,
    }
    write_json(plan["manifest_path"], manifest)

    return {
        "action": "install",
        "verdict": "PASS" if not warnings else "WARN",
        "summary": "WorkflowProgram package installed." if not warnings else "WorkflowProgram package installed with warnings.",
        "mode": mode,
        "source_package_root": str(source_root),
        "install_root": str(install_root),
        "runtime_root": str(_runtime_destination_root(install_root)),
        "config_status": config_status,
        "python_executable": selected_python,
        "create_venv": create_venv,
        "venv_root": str(plan["venv_root"]) if create_venv else None,
        "venv_info": venv_info,
        "warnings": warnings,
        "installed_files": sorted(installed_files),
        "manifest_path": str(plan["manifest_path"]),
        "exit_code": 0,
    }


def _remove_file_if_exists(path: Path) -> None:
    if path.exists():
        path.unlink()


def _prune_empty_dirs(path: Path, stop_at: Path) -> None:
    current = path
    while current != stop_at and current.exists():
        try:
            current.rmdir()
        except OSError:
            return
        current = current.parent


def uninstall_package(mode: str, target_root: str | None) -> dict[str, Any]:
    install_root = _resolve_install_root(mode, target_root)
    manifest_path = install_root / INSTALL_MANIFEST_PATH
    if not manifest_path.exists():
        return {
            "action": "uninstall",
            "verdict": "FAIL",
            "summary": "Install manifest not found.",
            "mode": mode,
            "install_root": str(install_root),
            "exit_code": 1,
        }

    manifest = read_json(manifest_path)
    installed_files = manifest.get("installed_files", [])
    managed_directories = manifest.get("managed_directories", [])
    removed_files: list[str] = []
    for relative in installed_files:
        target = install_root / relative
        if target.exists():
            target.unlink()
            removed_files.append(relative)

    backup_relative = manifest.get("config_backup")
    config_path = install_root / "opencode.json"
    if backup_relative:
        backup_path = install_root / backup_relative
        if backup_path.exists():
            shutil.copy2(backup_path, config_path)
            backup_path.unlink()
    elif manifest.get("config_status") == "created" and config_path.exists():
        created_snapshot = manifest.get("created_config")
        try:
            current_config = _read_json_file(config_path)
        except Exception:
            current_config = None
        if isinstance(created_snapshot, dict) and current_config == created_snapshot:
            config_path.unlink()

    manifest_path.unlink()

    removed_directories: list[str] = []
    for relative in managed_directories:
        directory = install_root / relative
        if directory.exists():
            shutil.rmtree(directory, ignore_errors=True)
            removed_directories.append(relative)

    runtime_root = _runtime_destination_root(install_root)
    _prune_empty_dirs(runtime_root, install_root)
    _prune_empty_dirs((install_root / ".opencode" / "commands") if mode == "project-local" else (install_root / "commands"), install_root)
    _prune_empty_dirs((install_root / ".opencode" / "agents") if mode == "project-local" else (install_root / "agents"), install_root)
    _prune_empty_dirs((install_root / ".opencode" / "plugins") if mode == "project-local" else (install_root / "plugins"), install_root)

    return {
        "action": "uninstall",
        "verdict": "PASS",
        "summary": "WorkflowProgram package uninstalled.",
        "mode": mode,
        "install_root": str(install_root),
        "removed_files": removed_files,
        "removed_directories": removed_directories,
        "exit_code": 0,
    }


def install_status(source_package_root: Path | None, mode: str, target_root: str | None) -> dict[str, Any]:
    install_root = _resolve_install_root(mode, target_root)
    layout = detect_package_layout(install_root)
    manifest = None
    if layout.install_manifest.exists():
        try:
            manifest = read_json(layout.install_manifest)
        except Exception:
            manifest = {"error": "manifest unreadable"}
    validator = None
    validator_path = layout.validators_dir / "package_contract_validator.py"
    if validator_path.is_file():
        validator = {
            "validator_path": str(validator_path),
            "available": True,
        }
    source_root = source_package_root.resolve() if source_package_root else None
    return {
        "action": "status",
        "verdict": "PASS" if layout.runtime_root.exists() and layout.plugin_file.exists() else "WARN",
        "mode": mode,
        "source_package_root": str(source_root) if source_root else None,
        "install_root": str(install_root),
        "layout_kind": layout.layout_kind,
        "commands_dir": str(layout.commands_dir),
        "plugins_dir": str(layout.plugins_dir),
        "runtime_root": str(layout.runtime_root),
        "python_executable": manifest.get("python_executable") if isinstance(manifest, dict) else None,
        "requirements_path": str(layout.runtime_root / REQUIREMENTS_FILE) if layout.runtime_root.exists() else None,
        "venv_root": (
            str((install_root / manifest.get("venv_root")).resolve())
            if isinstance(manifest, dict) and manifest.get("venv_root")
            else None
        ),
        "manifest": manifest,
        "validator": validator,
        "exit_code": 0,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Install or uninstall WorkflowProgram package layouts")
    parser.add_argument("--json", action="store_true")
    subparsers = parser.add_subparsers(dest="action", required=True)

    install_parser = subparsers.add_parser("install", help="Install WorkflowProgram into an OpenCode-visible root")
    install_parser.add_argument(
        "--source-package-root",
        help="Source WorkflowProgram package root; defaults to the package containing this script",
    )
    install_parser.add_argument("--mode", choices=("project-local", "global"), required=True)
    install_parser.add_argument("--target-root", help="Project root or global config root")
    install_parser.add_argument("--create-venv", action="store_true", help="Create a package-local Python venv and install runtime dependencies")
    install_parser.add_argument("--python", help="Base Python interpreter to use for venv creation or fallback runtime execution")
    install_parser.add_argument("--force", action="store_true", help="Overwrite unmanaged reserved package paths")
    install_parser.add_argument("--use-lock", action="store_true", help="Install Python dependencies from requirements.lock.txt when creating a venv")
    install_parser.add_argument("--json", action="store_true")

    uninstall_parser = subparsers.add_parser("uninstall", help="Remove a previously installed WorkflowProgram package")
    uninstall_parser.add_argument("--mode", choices=("project-local", "global"), required=True)
    uninstall_parser.add_argument("--target-root", help="Project root or global config root")
    uninstall_parser.add_argument("--json", action="store_true")

    status_parser = subparsers.add_parser("status", help="Inspect the installed WorkflowProgram layout")
    status_parser.add_argument("--mode", choices=("project-local", "global"), required=True)
    status_parser.add_argument("--target-root", help="Project root or global config root")
    status_parser.add_argument("--source-package-root", help="Optional source package root for context")
    status_parser.add_argument("--json", action="store_true")

    return parser


def main() -> int:
    args = build_parser().parse_args()
    default_source_root = infer_package_root_from_runtime_dir(RUNTIME_DIR)

    if args.action == "install":
        source_root = Path(args.source_package_root).resolve() if args.source_package_root else default_source_root
        result = install_package(
            source_package_root=source_root,
            mode=args.mode,
            target_root=args.target_root,
            create_venv=args.create_venv,
            python_executable=args.python,
            force=args.force,
            use_lock=args.use_lock,
        )
    elif args.action == "uninstall":
        result = uninstall_package(mode=args.mode, target_root=args.target_root)
    else:
        source_root = Path(args.source_package_root).resolve() if args.source_package_root else None
        result = install_status(source_package_root=source_root, mode=args.mode, target_root=args.target_root)

    if args.json:
        json.dump(result, sys.stdout, indent=2, ensure_ascii=True)
        sys.stdout.write("\n")
    else:
        sys.stdout.write(f"[{result['verdict']}] {result['summary'] if 'summary' in result else result['action']}\n")
        for key, value in result.items():
            if key in {"summary", "exit_code"}:
                continue
            sys.stdout.write(f"{key}: {value}\n")
    return int(result.get("exit_code", 0))


if __name__ == "__main__":
    raise SystemExit(main())
