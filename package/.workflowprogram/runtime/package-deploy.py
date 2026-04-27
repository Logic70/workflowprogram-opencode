#!/usr/bin/env python3
"""Install or remove the WorkflowProgram OpenCode package layout."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


RUNTIME_DIR = Path(__file__).resolve().parent
if str(RUNTIME_DIR) not in sys.path:
    sys.path.insert(0, str(RUNTIME_DIR))

from runtime_common import (  # noqa: E402
    BOOTSTRAP_COMMANDS,
    BOOTSTRAP_MANIFEST_PATH,
    INSTALL_MANIFEST_PATH,
    PACKAGE_COMMAND_PREFIX,
    PACKAGE_PLUGIN_FILE,
    REQUIRED_PACKAGE_COMMANDS,
    SCHEMA_VERSION,
    assess_target_workflow,
    default_bootstrap_cache_root,
    default_global_config_root,
    detect_package_layout,
    ensure_dir,
    infer_package_root_from_runtime_dir,
    iso_now,
    read_json,
    write_json,
)

# Engine-in-cache model: Python runtime stays at source_package_root, never copied to target project

BACKUP_CONFIG_PATH = ".workflowprogram/package/opencode.json.backup"
VENV_RELATIVE_PATH = ".workflowprogram/package/.venv"
REQUIREMENTS_FILE = "requirements.txt"
REQUIREMENTS_LOCK_FILE = "requirements.lock.txt"
BOOTSTRAP_RUNTIME_RELATIVE = ".workflowprogram/bootstrap/bootstrap-runtime.py"
BOOTSTRAP_COMMAND_DIR = "commands"
BOOTSTRAP_CACHE_EXCLUDED_PARTS = {
    "__pycache__",
    ".pytest_cache",
    "node_modules",
    "runs",
}
BOOTSTRAP_CACHE_EXCLUDED_NAMES = {
    "package-lock.json",
    "package.json",
    ".package-lock.json",
    "bun.lock",
}
BOOTSTRAP_CACHE_EXCLUDED_SUFFIXES = {
    ".log",
    ".pyc",
    ".pyd",
    ".pyo",
}


def _read_json_file(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_text_file(path: Path, content: str) -> None:
    ensure_dir(path.parent)
    path.write_text(content, encoding="utf-8", newline="\n")


def _bootstrap_command_body(action: str) -> str:
    script = "${OPENCODE_CONFIG_DIR:-$HOME/.config/opencode}/.workflowprogram/bootstrap/bootstrap-runtime.py"
    descriptions = {
        "install": "Install WorkflowProgram into the current project from the global bootstrap cache",
        "status": "Inspect WorkflowProgram project-local installation status",
        "upgrade": "Upgrade the current project's WorkflowProgram installation from the global bootstrap cache",
        "uninstall": "Remove WorkflowProgram project-local installation from the current project",
    }
    extra = {
        "install": "--create-venv --use-lock",
        "status": "",
        "upgrade": "--create-venv --use-lock --force",
        "uninstall": "",
    }[action]
    suffix = f" {extra}" if extra else ""
    return f"""---
description: {descriptions[action]}
---

This is the lightweight WorkflowProgram global bootstrap command.

Rules:
- Treat the current working directory as the target project root.
- Use the global bootstrap cache as the source package.
- Do not edit project files directly from the command body.
- Pass any extra user arguments through to the bootstrap runtime only when they are explicit CLI flags.

Run this first:

```bash
python3 "{script}" {action} --target-root "$PWD"{suffix} --json
```

If `python3` is not available on this host, retry once with `python`.

Then:
- Report the bootstrap verdict and install/status/upgrade/uninstall summary.
- Interpret `project_package_installed=true` as the only proof that the WorkflowProgram package is installed in this project.
- Interpret `target_workflow_exists=true` as the only proof that a generated target workflow exists; `.workflowprogram/package/*`, `.workflowprogram/runtime/*`, or `.workflowprogram/runs/*` alone do not prove that.
- If `project_package_installed=false`, tell the user to run `/wp-install` before using lifecycle commands.
- If `target_workflow_exists=false`, do not recommend `/wp-evolve`, `/wp-iterate`, `/wp-hotfix`, or `/wp-ship`; use `/wp-develop` for first-time workflow creation.
- If the command installs or upgrades the package, tell the user to restart OpenCode or reopen the project so local `/wp-*` commands refresh.
- If the command fails, surface the JSON `error`, `stderr`, or failed check directly.
"""


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


def _should_skip_cached_package_path(relative: Path) -> bool:
    if any(part in BOOTSTRAP_CACHE_EXCLUDED_PARTS for part in relative.parts):
        return True
    if relative.name in BOOTSTRAP_CACHE_EXCLUDED_NAMES:
        return True
    if relative.suffix in BOOTSTRAP_CACHE_EXCLUDED_SUFFIXES:
        return True
    return False


def _copy_package_to_cache(source_root: Path, cache_package_root: Path) -> dict[str, Any]:
    if cache_package_root.exists():
        shutil.rmtree(cache_package_root)
    ensure_dir(cache_package_root)
    included_files: list[str] = []
    excluded_entries: list[str] = []
    for current_root, dirnames, filenames in os.walk(source_root):
        current = Path(current_root)
        relative_current = current.relative_to(source_root)
        kept_dirnames: list[str] = []
        for dirname in sorted(dirnames):
            relative_dir = relative_current / dirname
            if _should_skip_cached_package_path(relative_dir):
                excluded_entries.append(relative_dir.as_posix() + "/")
                continue
            kept_dirnames.append(dirname)
            ensure_dir(cache_package_root / relative_dir)
        dirnames[:] = kept_dirnames
        for filename in sorted(filenames):
            relative_file = relative_current / filename
            if _should_skip_cached_package_path(relative_file):
                excluded_entries.append(relative_file.as_posix())
                continue
            _copy_file(source_root / relative_file, cache_package_root / relative_file)
            included_files.append(relative_file.as_posix())
    return {
        "cache_package_root": str(cache_package_root),
        "included_files": included_files,
        "excluded_entries": sorted(set(excluded_entries)),
    }


def _bootstrap_runtime_source(source_layout: Any) -> Path:
    runtime = source_layout.runtime_root / "bootstrap-runtime.py"
    if not runtime.is_file():
        raise FileNotFoundError(f"bootstrap-runtime.py not found: {runtime}")
    return runtime


def _install_bootstrap_commands(global_root: Path) -> list[str]:
    installed: list[str] = []
    command_actions = {
        "wp-install": "install",
        "wp-status": "status",
        "wp-upgrade": "upgrade",
        "wp-uninstall": "uninstall",
    }
    commands_root = global_root / BOOTSTRAP_COMMAND_DIR
    for command_name in BOOTSTRAP_COMMANDS:
        action = command_actions[command_name]
        relative = f"{BOOTSTRAP_COMMAND_DIR}/{command_name}.md"
        _write_text_file(global_root / relative, _bootstrap_command_body(action))
        installed.append(relative)
    return installed


def _bootstrap_manifest_path(global_root: Path) -> Path:
    return global_root / BOOTSTRAP_MANIFEST_PATH


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


# Deprecated in engine-in-cache model; kept for reference only
def _runtime_destination_root(root: Path) -> Path:
    """Deprecated in engine-in-cache model (deepseek).
    Engine runtime stays at source/cache, never copied to target project."""
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

    plugin_destination = _plugin_destination(install_root, mode)
    return {
        "source_layout": source_layout,
        "install_root": install_root,
        "mode": mode,
        "command_files": command_files,
        "agent_files": agent_files,
        "plugin_file": (source_layout.plugin_file, str(plugin_destination.relative_to(install_root).as_posix())),
        "config_path": install_root / "opencode.json",
        "manifest_path": install_root / INSTALL_MANIFEST_PATH,
        "backup_config_path": install_root / BACKUP_CONFIG_PATH,
    }


def _detect_unmanaged_conflicts(plan: dict[str, Any], force: bool) -> list[str]:
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

    # Engine-in-cache model (deepseek): no runtime files or venv in target project
    conflicts = _detect_unmanaged_conflicts(plan, force)
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

    # Venv provisioning moved to bootstrap-runtime.py; installed at source_package_root

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
        "managed_directories": [],
        "required_package_commands": list(REQUIRED_PACKAGE_COMMANDS),
        "create_venv": False,
        "python_executable": python_executable or sys.executable,
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
        "config_status": config_status,
        "python_executable": python_executable or sys.executable,
        "create_venv": False,
        "venv_root": None,
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

    # Engine-in-cache model (deepseek): no runtime files in project to prune
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


def _project_package_install_status(install_root: Path) -> dict[str, Any]:
    manifest_path = install_root / INSTALL_MANIFEST_PATH
    manifest = None
    if manifest_path.exists():
        try:
            manifest = read_json(manifest_path)
        except Exception:
            manifest = {"error": "manifest unreadable"}

    commands_dir = install_root / ".opencode" / "commands"
    agents_dir = install_root / ".opencode" / "agents"
    plugins_dir = install_root / ".opencode" / "plugins"
    plugin_file = _plugin_destination(install_root, "project-local")
    # Engine-in-cache model (deepseek): runtime lives in cache, not project.
    # Installation is valid when manifest + plugin exist, regardless of local runtime.
    installed = manifest_path.is_file() and plugin_file.is_file()
    source_root = manifest.get("source_package_root") if isinstance(manifest, dict) else None
    runtime_dir = Path(source_root) / ".workflowprogram" / "runtime" if source_root else None
    return {
        "installed": installed,
        "manifest_path": str(manifest_path),
        "manifest_exists": manifest_path.is_file(),
        "manifest": manifest,
        "commands_dir": str(commands_dir),
        "agents_dir": str(agents_dir),
        "plugins_dir": str(plugins_dir),
        "plugin_file": str(plugin_file),
        "plugin_exists": plugin_file.is_file(),
        "source_package_root": str(source_root) if source_root else None,
        "runtime_root": str(runtime_dir) if runtime_dir else None,
        "runtime_exists": runtime_dir.is_dir() if runtime_dir else False,
        "engine_note": "Runtime engine runs from cache/source package, not from target project.",
    }


def install_status(source_package_root: Path | None, mode: str, target_root: str | None) -> dict[str, Any]:
    install_root = _resolve_install_root(mode, target_root)
    target_status = assess_target_workflow(install_root)
    if mode == "project-local":
        package_status = _project_package_install_status(install_root)
        manifest = package_status["manifest"]
        source_root = source_package_root.resolve() if source_package_root else None
        summary = (
            "WorkflowProgram package is installed in this project."
            if package_status["installed"]
            else "WorkflowProgram package is not installed in this project; run /wp-install before lifecycle commands."
        )
        return {
            "action": "status",
            "verdict": "PASS" if package_status["installed"] else "WARN",
            "summary": summary,
            "mode": mode,
            "source_package_root": str(source_root) if source_root else None,
            "install_root": str(install_root),
            "layout_kind": "project-local" if package_status["installed"] else "not-installed",
            "project_package_installed": package_status["installed"],
            "target_workflow_exists": target_status["target_workflow_exists"],
            "target_workflow_complete": target_status["target_workflow_complete"],
            "package_install_status": package_status,
            "target_workflow_status": target_status,
            "commands_dir": package_status["commands_dir"],
            "plugins_dir": package_status["plugins_dir"],
            "runtime_root": package_status["runtime_root"],
            "python_executable": manifest.get("python_executable") if isinstance(manifest, dict) else None,
            "requirements_path": (
                str(Path(package_status["runtime_root"]) / REQUIREMENTS_FILE)
                if package_status["runtime_exists"]
                else None
            ),
            "venv_root": (
                str((install_root / manifest.get("venv_root")).resolve())
                if isinstance(manifest, dict) and manifest.get("venv_root")
                else None
            ),
            "manifest": manifest,
            "validator": package_status["validator"],
            "interpretation": [
                "project_package_installed controls whether /wp-* package lifecycle commands are available in this project.",
                "target_workflow_exists controls whether evolve/iterate/hotfix/ship can operate on a generated target workflow.",
                "Do not infer either state from the existence of a generic .workflowprogram directory.",
            ],
            "exit_code": 0,
        }

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
        "project_package_installed": bool(manifest),
        "target_workflow_exists": target_status["target_workflow_exists"],
        "target_workflow_complete": target_status["target_workflow_complete"],
        "target_workflow_status": target_status,
        "exit_code": 0,
    }


def install_bootstrap(
    source_package_root: Path,
    target_root: str | None,
    cache_root: str | None,
    version: str | None,
    force: bool = False,
) -> dict[str, Any]:
    source_root = source_package_root.resolve()
    source_layout = detect_package_layout(source_root)
    global_root = _resolve_install_root("global", target_root)
    bootstrap_manifest = _bootstrap_manifest_path(global_root)
    if bootstrap_manifest.exists() and not force:
        try:
            existing = read_json(bootstrap_manifest)
        except Exception:
            existing = {}
        installed_files = existing.get("installed_files", []) if isinstance(existing, dict) else []
        unmanaged_conflicts = [
            path
            for path in installed_files
            if path and (global_root / path).exists()
        ]
        if unmanaged_conflicts:
            return {
                "action": "install-bootstrap",
                "verdict": "FAIL",
                "summary": "Bootstrap is already installed; use --force to replace it.",
                "global_root": str(global_root),
                "existing_manifest": str(bootstrap_manifest),
                "conflicts": unmanaged_conflicts,
                "exit_code": 2,
            }

    selected_version = version or SCHEMA_VERSION
    selected_cache_root = Path(cache_root).resolve() if cache_root else default_bootstrap_cache_root().resolve()
    cache_package_root = selected_cache_root / "packages" / selected_version / "package"
    ensure_dir(global_root)
    cache_result = _copy_package_to_cache(source_root, cache_package_root)

    installed_files: list[str] = []
    installed_files.extend(_install_bootstrap_commands(global_root))
    bootstrap_runtime_dest = global_root / BOOTSTRAP_RUNTIME_RELATIVE
    _copy_file(_bootstrap_runtime_source(source_layout), bootstrap_runtime_dest)
    installed_files.append(BOOTSTRAP_RUNTIME_RELATIVE)

    manifest = {
        "schema_version": SCHEMA_VERSION,
        "installed_at": iso_now(),
        "mode": "global-bootstrap",
        "global_root": str(global_root),
        "source_package_root": str(source_root),
        "cache_root": str(selected_cache_root),
        "cache_package_root": str(cache_package_root),
        "bootstrap_version": selected_version,
        "installed_files": sorted(installed_files),
        "bootstrap_commands": list(BOOTSTRAP_COMMANDS),
        "cache_result": cache_result,
    }
    write_json(bootstrap_manifest, manifest)
    installed_files.append(str(bootstrap_manifest.relative_to(global_root).as_posix()))

    return {
        "action": "install-bootstrap",
        "verdict": "PASS",
        "summary": "WorkflowProgram global bootstrap installed.",
        "global_root": str(global_root),
        "cache_package_root": str(cache_package_root),
        "bootstrap_runtime": str(bootstrap_runtime_dest),
        "installed_files": sorted(installed_files),
        "manifest_path": str(bootstrap_manifest),
        "exit_code": 0,
    }


def bootstrap_status(target_root: str | None) -> dict[str, Any]:
    global_root = _resolve_install_root("global", target_root)
    manifest_path = _bootstrap_manifest_path(global_root)
    manifest = None
    if manifest_path.exists():
        try:
            manifest = read_json(manifest_path)
        except Exception:
            manifest = {"error": "manifest unreadable"}
    command_status = {}
    for command in BOOTSTRAP_COMMANDS:
        command_status[command] = (global_root / BOOTSTRAP_COMMAND_DIR / f"{command}.md").is_file()
    runtime_path = global_root / BOOTSTRAP_RUNTIME_RELATIVE
    cache_package_root = None
    cache_available = False
    if isinstance(manifest, dict) and isinstance(manifest.get("cache_package_root"), str):
        cache_package_root = manifest["cache_package_root"]
        cache_available = (Path(cache_package_root) / ".workflowprogram" / "runtime" / "package-deploy.py").is_file()
    verdict = "PASS" if runtime_path.is_file() and all(command_status.values()) and cache_available else "WARN"
    return {
        "action": "bootstrap-status",
        "verdict": verdict,
        "global_root": str(global_root),
        "runtime_path": str(runtime_path),
        "runtime_available": runtime_path.is_file(),
        "commands": command_status,
        "manifest": manifest,
        "cache_package_root": cache_package_root,
        "cache_available": cache_available,
        "exit_code": 0,
    }


def uninstall_bootstrap(target_root: str | None, remove_cache: bool = False) -> dict[str, Any]:
    global_root = _resolve_install_root("global", target_root)
    manifest_path = _bootstrap_manifest_path(global_root)
    if not manifest_path.exists():
        return {
            "action": "uninstall-bootstrap",
            "verdict": "FAIL",
            "summary": "Bootstrap manifest not found.",
            "global_root": str(global_root),
            "exit_code": 1,
        }
    manifest = read_json(manifest_path)
    removed_files: list[str] = []
    for relative in manifest.get("installed_files", []):
        path = global_root / relative
        if path.exists() and path.is_file():
            path.unlink()
            removed_files.append(relative)
    if manifest_path.exists():
        manifest_path.unlink()
        removed_files.append(str(manifest_path.relative_to(global_root).as_posix()))
    removed_cache = None
    if remove_cache and isinstance(manifest.get("cache_package_root"), str):
        cache_package_root = Path(manifest["cache_package_root"])
        package_version_root = cache_package_root.parent
        if package_version_root.exists():
            shutil.rmtree(package_version_root, ignore_errors=True)
            removed_cache = str(package_version_root)

    _prune_empty_dirs(global_root / BOOTSTRAP_COMMAND_DIR, global_root)
    _prune_empty_dirs(global_root / ".workflowprogram" / "bootstrap", global_root)
    return {
        "action": "uninstall-bootstrap",
        "verdict": "PASS",
        "summary": "WorkflowProgram global bootstrap uninstalled.",
        "global_root": str(global_root),
        "removed_files": removed_files,
        "removed_cache": removed_cache,
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

    bootstrap_install_parser = subparsers.add_parser("install-bootstrap", help="Install a lightweight global bootstrap into OpenCode config")
    bootstrap_install_parser.add_argument(
        "--source-package-root",
        help="Source WorkflowProgram package root; defaults to the package containing this script",
    )
    bootstrap_install_parser.add_argument("--target-root", help="OpenCode global config root")
    bootstrap_install_parser.add_argument("--cache-root", help="WorkflowProgram user cache root")
    bootstrap_install_parser.add_argument("--version", help="Cache version directory; defaults to schema version")
    bootstrap_install_parser.add_argument("--force", action="store_true", help="Replace an existing bootstrap install")
    bootstrap_install_parser.add_argument("--json", action="store_true")

    bootstrap_status_parser = subparsers.add_parser("bootstrap-status", help="Inspect global bootstrap install state")
    bootstrap_status_parser.add_argument("--target-root", help="OpenCode global config root")
    bootstrap_status_parser.add_argument("--json", action="store_true")

    bootstrap_uninstall_parser = subparsers.add_parser("uninstall-bootstrap", help="Remove the global bootstrap install")
    bootstrap_uninstall_parser.add_argument("--target-root", help="OpenCode global config root")
    bootstrap_uninstall_parser.add_argument("--remove-cache", action="store_true")
    bootstrap_uninstall_parser.add_argument("--json", action="store_true")

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
    elif args.action == "status":
        source_root = Path(args.source_package_root).resolve() if args.source_package_root else None
        result = install_status(source_package_root=source_root, mode=args.mode, target_root=args.target_root)
    elif args.action == "install-bootstrap":
        source_root = Path(args.source_package_root).resolve() if args.source_package_root else default_source_root
        result = install_bootstrap(
            source_package_root=source_root,
            target_root=args.target_root,
            cache_root=args.cache_root,
            version=args.version,
            force=args.force,
        )
    elif args.action == "bootstrap-status":
        result = bootstrap_status(target_root=args.target_root)
    else:
        result = uninstall_bootstrap(target_root=args.target_root, remove_cache=args.remove_cache)

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
