#!/usr/bin/env python3
"""Discover host capabilities relevant to the WorkflowProgram OpenCode package."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import Any


RUNTIME_DIR = Path(__file__).resolve().parent
if str(RUNTIME_DIR) not in sys.path:
    sys.path.insert(0, str(RUNTIME_DIR))

from runtime_common import detect_package_layout  # noqa: E402


def discover_capabilities(package_root: Path, target_root: Path | None) -> dict[str, Any]:
    layout = detect_package_layout(package_root)
    target = target_root.resolve() if target_root else None
    target_spec = target / ".workflowprogram" / "design" / "workflow-spec.yaml" if target else None
    return {
        "package_root": str(layout.package_root),
        "layout_kind": layout.layout_kind,
        "runtime_root": str(layout.runtime_root),
        "commands_dir": str(layout.commands_dir),
        "plugin_file": str(layout.plugin_file),
        "install_manifest_present": layout.install_manifest.is_file(),
        "python_executable": sys.executable,
        "pyyaml_importable": _yaml_importable(),
        "opencode_cli": shutil.which("opencode"),
        "target_root": str(target) if target else None,
        "target_workflow_present": bool(target_spec and target_spec.is_file()),
    }


def _yaml_importable() -> bool:
    try:
        import yaml  # noqa: F401
    except Exception:
        return False
    return True


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Discover WorkflowProgram host capabilities")
    parser.add_argument("--package-root", required=True)
    parser.add_argument("--target-root")
    parser.add_argument("--json", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    result = discover_capabilities(
        Path(args.package_root),
        Path(args.target_root) if args.target_root else None,
    )
    if args.json:
        json.dump(result, sys.stdout, indent=2, ensure_ascii=True)
        sys.stdout.write("\n")
    else:
        for key, value in result.items():
            sys.stdout.write(f"{key}={value}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
