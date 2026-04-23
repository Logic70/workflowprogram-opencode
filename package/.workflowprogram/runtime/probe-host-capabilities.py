#!/usr/bin/env python3
"""Probe host readiness for the WorkflowProgram OpenCode package."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path
from typing import Any


RUNTIME_DIR = Path(__file__).resolve().parent
if str(RUNTIME_DIR) not in sys.path:
    sys.path.insert(0, str(RUNTIME_DIR))

from runtime_common import detect_package_layout  # noqa: E402


def _check(check_id: str, available: bool, ready: bool, message: str) -> dict[str, Any]:
    return {
        "id": check_id,
        "available": available,
        "ready": ready,
        "message": message,
    }


def _target_writable(target_root: Path | None) -> tuple[bool, str]:
    if target_root is None:
        return True, "target-root-not-requested"
    candidate = target_root.resolve()
    probe_root = candidate if candidate.exists() else candidate.parent
    if not probe_root.exists():
        return False, f"parent-not-found:{probe_root}"
    return os.access(probe_root, os.W_OK), f"probe_root={probe_root}"


def probe_capabilities(package_root: Path, target_root: Path | None) -> dict[str, Any]:
    layout = detect_package_layout(package_root)
    yaml_ready = False
    try:
        import yaml  # noqa: F401

        yaml_ready = True
    except Exception:
        yaml_ready = False

    target_spec = target_root.resolve() / ".workflowprogram" / "design" / "workflow-spec.yaml" if target_root else None
    writable_ready, writable_message = _target_writable(target_root)
    probes = [
        _check("HOST-01", True, layout.config_path.is_file(), f"config_path={layout.config_path}"),
        _check("HOST-02", True, layout.commands_dir.is_dir(), f"commands_dir={layout.commands_dir}"),
        _check("HOST-03", True, layout.plugin_file.is_file(), f"plugin_file={layout.plugin_file}"),
        _check("HOST-04", bool(sys.executable), bool(sys.executable), f"python={sys.executable}"),
        _check("HOST-05", True, yaml_ready, "PyYAML import" if yaml_ready else "PyYAML import failed"),
        _check("HOST-06", shutil.which("opencode") is not None, shutil.which("opencode") is not None, "opencode CLI lookup"),
        _check("HOST-07", target_root is not None, writable_ready, writable_message),
        _check(
            "HOST-08",
            target_root is not None,
            bool(target_spec and target_spec.is_file()),
            f"target_workflow_spec={target_spec}" if target_spec else "target-root-not-requested",
        ),
    ]
    verdict = "PASS" if all(item["ready"] for item in probes if item["available"]) else "FAIL"
    return {
        "package_root": str(layout.package_root),
        "target_root": str(target_root.resolve()) if target_root else None,
        "verdict": verdict,
        "probes": probes,
        "exit_code": 0 if verdict == "PASS" else 1,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Probe WorkflowProgram host capabilities")
    parser.add_argument("--package-root", required=True)
    parser.add_argument("--target-root")
    parser.add_argument("--json", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    result = probe_capabilities(
        Path(args.package_root),
        Path(args.target_root) if args.target_root else None,
    )
    if args.json:
        json.dump(result, sys.stdout, indent=2, ensure_ascii=True)
        sys.stdout.write("\n")
    else:
        sys.stdout.write(f"{result['verdict']} package_root={result['package_root']}\n")
        for probe in result["probes"]:
            status = "READY" if probe["ready"] else "NOT-READY"
            sys.stdout.write(f"{status} {probe['id']} {probe['message']}\n")
    return result["exit_code"]


if __name__ == "__main__":
    raise SystemExit(main())
