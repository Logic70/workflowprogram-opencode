#!/usr/bin/env python3
"""Build a clean WorkflowProgram OpenCode release package."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_EXCLUDED_PARTS = {
    "__pycache__",
    "node_modules",
    "runs",
    ".pytest_cache",
}
DEFAULT_EXCLUDED_SUFFIXES = {
    ".pyc",
    ".pyo",
    ".pyd",
    ".log",
}
DEFAULT_EXCLUDED_NAMES = {
    "package-lock.json",
    "package.json",
    "bun.lock",
    ".package-lock.json",
}


def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def source_commit(root: Path) -> str | None:
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=5,
        )
    except Exception:
        return None
    return proc.stdout.strip() if proc.returncode == 0 else None


def should_exclude(relative: Path) -> tuple[bool, str | None]:
    if any(part in DEFAULT_EXCLUDED_PARTS for part in relative.parts):
        return True, "excluded-part"
    if relative.name in DEFAULT_EXCLUDED_NAMES:
        return True, "excluded-name"
    if relative.suffix in DEFAULT_EXCLUDED_SUFFIXES:
        return True, "excluded-suffix"
    if relative.as_posix().startswith(".workflowprogram/runs/"):
        return True, "runtime-runs"
    if relative.as_posix().startswith(".workflowprogram/package/"):
        return True, "installed-package-layout"
    return False, None


def build_package(source_package_root: Path, output_root: Path, clean: bool) -> dict[str, Any]:
    source_root = source_package_root.resolve()
    output = output_root.resolve()
    if not source_root.is_dir():
        raise FileNotFoundError(f"source package root not found: {source_root}")
    if clean and output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True, exist_ok=True)

    included: list[str] = []
    excluded: list[dict[str, str]] = []
    checksums: dict[str, str] = {}
    for current_root, dirnames, filenames in os.walk(source_root):
        current = Path(current_root)
        for dirname in list(dirnames):
            relative_dir = (current / dirname).relative_to(source_root)
            excluded_flag, reason = should_exclude(relative_dir)
            if excluded_flag:
                excluded.append({"path": relative_dir.as_posix() + "/", "reason": str(reason)})
                dirnames.remove(dirname)
        for filename in sorted(filenames):
            path = current / filename
            relative = path.relative_to(source_root)
            excluded_flag, reason = should_exclude(relative)
            if excluded_flag:
                excluded.append({"path": relative.as_posix(), "reason": str(reason)})
                continue
            destination = output / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, destination)
            included_path = relative.as_posix()
            included.append(included_path)
            checksums[included_path] = sha256_file(destination)

    manifest = {
        "manifest_version": 1,
        "package_version": "opencode-v2",
        "source_package_root": str(source_root),
        "source_commit": source_commit(source_root.parent),
        "build_time": iso_now(),
        "output_root": str(output),
        "included_files": included,
        "excluded_files": excluded,
        "excluded_patterns": {
            "parts": sorted(DEFAULT_EXCLUDED_PARTS),
            "suffixes": sorted(DEFAULT_EXCLUDED_SUFFIXES),
            "names": sorted(DEFAULT_EXCLUDED_NAMES),
        },
        "checksums": checksums,
    }
    manifest_path = output / "release-manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    return manifest


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build WorkflowProgram OpenCode release package")
    parser.add_argument("--source-package-root", default="package")
    parser.add_argument("--output-root", default="dist/opencode")
    parser.add_argument("--clean", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    result = build_package(Path(args.source_package_root), Path(args.output_root), args.clean)
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=True))
    else:
        print(f"built {len(result['included_files'])} files to {result['output_root']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
