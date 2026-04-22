#!/usr/bin/env python3
"""Shared runtime helpers for the WorkflowProgram OpenCode package."""

from __future__ import annotations

import json
import os
import re
import shlex
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any

import yaml


STAGE_SLOTS = ("S1", "S2", "S3", "S4", "S5", "S6")
FAILURE_KINDS = ("none", "design", "implementation", "environment", "conflict")
VALID_COMPLEXITY = {"S", "M", "L", "XL"}
PACKAGE_COMMAND_PREFIX = "wp-"
PACKAGE_PLUGIN_FILE = "workflowprogram.ts"
PACKAGE_PLUGIN_ID = "workflowprogram-package-bridge"
REQUIRED_PACKAGE_COMMANDS = ("wp-develop", "wp-validate")
INSTALL_MANIFEST_PATH = ".workflowprogram/package/install-manifest.json"
MANDATORY_DESIGN_FILES = (
    ".workflowprogram/design/workflow-spec.yaml",
    ".workflowprogram/design/workflow-view.md",
    ".workflowprogram/design/workflow-lowlevel.md",
)
MANDATORY_RUNTIME_FILES = (
    ".workflowprogram/runtime/workflow-entry.py",
    ".workflowprogram/runtime/workflow-runner.py",
    ".workflowprogram/runtime/validate-run-state.py",
    ".workflowprogram/runtime/runtime-manifest.json",
)
MANDATORY_TARGET_FILES = MANDATORY_DESIGN_FILES + MANDATORY_RUNTIME_FILES + (
    ".workflowprogram/managed-files.json",
)


@dataclass
class PackageLayout:
    package_root: Path
    config_path: Path
    commands_dir: Path
    plugins_dir: Path
    runtime_root: Path
    validators_dir: Path
    plugin_file: Path
    install_manifest: Path
    layout_kind: str


@dataclass
class DevelopRequest:
    raw: str
    summary: str
    spec_name: str
    complexity: str
    emit_target_command: bool
    emit_target_plugin: bool
    target_command_name: str | None
    target_plugin_file: str | None
    target_plugin_id: str | None


def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def make_run_id(intent: str) -> str:
    return f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{intent}"


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def write_json(path: Path, payload: Any) -> None:
    ensure_dir(path.parent)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_text(path: Path, content: str) -> None:
    ensure_dir(path.parent)
    path.write_text(content, encoding="utf-8", newline="\n")


def append_jsonl(path: Path, payload: Any) -> None:
    ensure_dir(path.parent)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(payload, ensure_ascii=True) + "\n")


def read_jsonl(path: Path) -> list[Any]:
    if not path.exists():
        return []
    records: list[Any] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            records.append(json.loads(line))
    return records


def write_yaml(path: Path, payload: Any) -> None:
    ensure_dir(path.parent)
    path.write_text(
        yaml.safe_dump(payload, sort_keys=False, allow_unicode=False),
        encoding="utf-8",
        newline="\n",
    )


def read_yaml(path: Path) -> Any:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def sha256_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def slugify(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    value = re.sub(r"-{2,}", "-", value).strip("-")
    return value or "target-workflow"


def ensure_non_package_command_name(name: str) -> str:
    cleaned = slugify(name)
    if cleaned.startswith(PACKAGE_COMMAND_PREFIX):
        return f"target-{cleaned}"
    return cleaned


def ensure_non_package_plugin_file(name: str) -> str:
    stem = slugify(name)
    if stem == "workflowprogram":
        stem = "target-workflow-runtime"
    return f"{stem}.ts"


def ensure_non_package_plugin_id(name: str) -> str:
    plugin_id = slugify(name)
    if plugin_id == PACKAGE_PLUGIN_ID or plugin_id == "workflowprogram":
        plugin_id = "target-workflow-runtime"
    return plugin_id


def parse_user_arguments(raw: str, target_root_name: str) -> DevelopRequest:
    tokens = shlex.split(raw)
    summary_parts: list[str] = []
    complexity = "M"
    emit_target_command = False
    emit_target_plugin = False
    spec_name_override: str | None = None
    command_name_override: str | None = None
    plugin_name_override: str | None = None
    plugin_id_override: str | None = None

    index = 0
    while index < len(tokens):
        token = tokens[index]
        if token == "--complexity" and index + 1 < len(tokens):
            candidate = tokens[index + 1].upper()
            if candidate in VALID_COMPLEXITY:
                complexity = candidate
            index += 2
            continue
        if token == "--name" and index + 1 < len(tokens):
            spec_name_override = tokens[index + 1]
            index += 2
            continue
        if token == "--emit-target-command":
            emit_target_command = True
            index += 1
            continue
        if token == "--emit-target-plugin":
            emit_target_plugin = True
            index += 1
            continue
        if token == "--command-name" and index + 1 < len(tokens):
            emit_target_command = True
            command_name_override = tokens[index + 1]
            index += 2
            continue
        if token == "--plugin-name" and index + 1 < len(tokens):
            emit_target_plugin = True
            plugin_name_override = tokens[index + 1]
            index += 2
            continue
        if token == "--plugin-id" and index + 1 < len(tokens):
            emit_target_plugin = True
            plugin_id_override = tokens[index + 1]
            index += 2
            continue
        summary_parts.append(token)
        index += 1

    summary = " ".join(summary_parts).strip() or f"Design a workflow for {target_root_name}"
    spec_name = slugify(spec_name_override or target_root_name or summary)
    command_name = (
        ensure_non_package_command_name(command_name_override or f"{spec_name}-run")
        if emit_target_command
        else None
    )
    plugin_file = (
        ensure_non_package_plugin_file(plugin_name_override or f"{spec_name}-runtime")
        if emit_target_plugin
        else None
    )
    plugin_id = (
        ensure_non_package_plugin_id(plugin_id_override or f"{spec_name}-target-runtime")
        if emit_target_plugin
        else None
    )

    return DevelopRequest(
        raw=raw,
        summary=summary,
        spec_name=spec_name,
        complexity=complexity,
        emit_target_command=emit_target_command,
        emit_target_plugin=emit_target_plugin,
        target_command_name=command_name,
        target_plugin_file=plugin_file,
        target_plugin_id=plugin_id,
    )


def derive_expected_target_files(spec: dict[str, Any]) -> list[str]:
    outputs = spec.get("outputs", {}) if isinstance(spec.get("outputs"), dict) else {}
    required = list(outputs.get("required", []))
    for path in MANDATORY_TARGET_FILES:
        if path not in required:
            required.append(path)
    return required


def registry_commands(spec: dict[str, Any]) -> list[dict[str, Any]]:
    registry = spec.get("registry", {}) if isinstance(spec.get("registry"), dict) else {}
    commands = registry.get("commands", [])
    return [item for item in commands if isinstance(item, dict)]


def registry_plugins(spec: dict[str, Any]) -> list[dict[str, Any]]:
    registry = spec.get("registry", {}) if isinstance(spec.get("registry"), dict) else {}
    plugins = registry.get("plugins", [])
    return [item for item in plugins if isinstance(item, dict)]


def aggregate_verdicts(verdicts: list[str]) -> str:
    if any(verdict == "FAIL" for verdict in verdicts):
        return "FAIL"
    if any(verdict == "WARN" for verdict in verdicts):
        return "WARN"
    if any(verdict == "ENVIRONMENT-SKIP" for verdict in verdicts):
        return "ENVIRONMENT-SKIP"
    return "PASS"


def default_global_config_root() -> Path:
    config_dir = os.environ.get("OPENCODE_CONFIG_DIR")
    if config_dir:
        return Path(config_dir)
    userprofile = os.environ.get("USERPROFILE")
    if userprofile:
        return Path(userprofile) / ".config" / "opencode"
    return Path.home() / ".config" / "opencode"


def infer_package_root_from_runtime_dir(runtime_dir: Path) -> Path:
    resolved = runtime_dir.resolve()
    if resolved.name != "runtime":
        raise ValueError(f"Unsupported runtime directory: {resolved}")
    if resolved.parent.name == ".workflowprogram":
        return resolved.parent.parent
    if resolved.parent.name == "package" and resolved.parent.parent.name == ".workflowprogram":
        return resolved.parent.parent.parent
    raise ValueError(f"Unable to infer package root from runtime directory: {resolved}")


def detect_package_layout(package_root: Path) -> PackageLayout:
    root = package_root.resolve()
    config_path = root / "opencode.json"

    source_runtime = root / ".workflowprogram" / "runtime"
    deployed_runtime = root / ".workflowprogram" / "package" / "runtime"
    runtime_root = deployed_runtime if deployed_runtime.exists() else source_runtime
    validators_dir = runtime_root / "validators"

    local_commands = root / ".opencode" / "commands"
    local_plugins = root / ".opencode" / "plugins"
    global_commands = root / "commands"
    global_plugins = root / "plugins"

    if local_commands.exists() or local_plugins.exists():
        commands_dir = local_commands
        plugins_dir = local_plugins
        layout_kind = "project-local"
        if runtime_root == source_runtime:
            layout_kind = "source-package"
    else:
        commands_dir = global_commands
        plugins_dir = global_plugins
        layout_kind = "global"

    plugin_file = plugins_dir / PACKAGE_PLUGIN_FILE
    return PackageLayout(
        package_root=root,
        config_path=config_path,
        commands_dir=commands_dir,
        plugins_dir=plugins_dir,
        runtime_root=runtime_root,
        validators_dir=validators_dir,
        plugin_file=plugin_file,
        install_manifest=root / INSTALL_MANIFEST_PATH,
        layout_kind=layout_kind,
    )
