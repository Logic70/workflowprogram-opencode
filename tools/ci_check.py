#!/usr/bin/env python3
"""Run local CI checks for WorkflowProgram OpenCode."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def run(cmd: list[str], cwd: Path) -> int:
    print("+", " ".join(cmd))
    return subprocess.run(cmd, cwd=str(cwd)).returncode


def main() -> int:
    parser = argparse.ArgumentParser(description="Run WorkflowProgram OpenCode CI checks")
    parser.add_argument("--skip-smoke", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    commands = [
        ["python3", "-m", "py_compile", *[str(path) for path in sorted((root / "package" / ".workflowprogram" / "runtime").glob("*.py"))], *[str(path) for path in sorted((root / "package" / ".workflowprogram" / "runtime" / "validators").glob("*.py"))], "tools/build_package.py", "tools/ci_check.py"],
        ["python3", "package/.workflowprogram/runtime/validators/package_contract_validator.py", "--package-root", "package", "--json"],
        ["python3", "tools/build_package.py", "--source-package-root", "package", "--output-root", "/tmp/workflowprogram-opencode-ci-dist", "--clean", "--json"],
        ["python3", "/tmp/workflowprogram-opencode-ci-dist/.workflowprogram/runtime/validators/package_contract_validator.py", "--package-root", "/tmp/workflowprogram-opencode-ci-dist", "--json"],
    ]
    if not args.skip_smoke:
        commands.append(["python3", "package/.workflowprogram/runtime/smoke-harness.py", "--package-root", "package", "--json"])
    for cmd in commands:
        code = run(cmd, root)
        if code != 0:
            return code
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
