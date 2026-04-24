#!/usr/bin/env python3
"""Generate actionable remediation guidance from doctor output."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


RUNTIME_DIR = Path(__file__).resolve().parent
if str(RUNTIME_DIR) not in sys.path:
    sys.path.insert(0, str(RUNTIME_DIR))

from doctor import run_doctor  # noqa: E402


def remediation_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Environment Remediation",
        "",
        f"- Verdict: `{report['verdict']}`",
        "",
        "## Recommended Actions",
        "",
    ]
    for check in report.get("checks", []):
        if check.get("passed"):
            continue
        if check["id"] == "DOC-04":
            lines.append("- Install or repair `PyYAML`, or reinstall the package with `--create-venv`.")
        elif check["id"] == "DOC-05":
            lines.append("- Install or expose the `opencode` CLI in the current shell before using package commands in the host.")
        elif check["id"] == "DOC-06":
            lines.append("- Use a writable `TARGET_ROOT`, or adjust filesystem permissions for the current project.")
        elif check["id"] == "DOC-07":
            lines.append("- Run `/wp-develop` first, because the target workflow has not been generated yet.")
        elif check["id"] == "DOC-08":
            lines.append("- Resolve namespace shadowing by opening OpenCode from the intended project root or temporarily disabling conflicting global OpenCode/Claude/oh-my-opencode assets.")
        elif check["id"] == "DOC-10":
            lines.append("- Check the installed OpenCode version and upgrade or pin WorkflowProgram to a compatible OpenCode release.")
        elif check["id"] == "DOC-11":
            lines.append("- Restart OpenCode or reopen the project after plugin changes if commands/hooks appear stale.")
        else:
            lines.append(f"- Resolve `{check['id']}`: {check['detail']}")
    if lines[-1] == "":
        lines.append("- No remediation needed.")
    return "\n".join(lines).rstrip() + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate remediation guidance from WorkflowProgram doctor")
    parser.add_argument("--package-root", required=True)
    parser.add_argument("--target-root")
    parser.add_argument("--doctor-report")
    parser.add_argument("--json", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.doctor_report:
        report = json.loads(Path(args.doctor_report).read_text(encoding="utf-8"))
    else:
        report = run_doctor(
            Path(args.package_root),
            Path(args.target_root) if args.target_root else None,
        )
    payload = {
        "verdict": report["verdict"],
        "markdown": remediation_markdown(report),
    }
    if args.json:
        json.dump(payload, sys.stdout, indent=2, ensure_ascii=True)
        sys.stdout.write("\n")
    else:
        sys.stdout.write(payload["markdown"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
