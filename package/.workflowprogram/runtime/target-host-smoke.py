#!/usr/bin/env python3
"""Validate generated target workflow visibility in OpenCode host terms."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


RUNTIME_DIR = Path(__file__).resolve().parent
if str(RUNTIME_DIR) not in sys.path:
    sys.path.insert(0, str(RUNTIME_DIR))

from runtime_common import (  # noqa: E402
    aggregate_verdicts,
    ensure_dir,
    iso_now,
    make_run_id,
    read_yaml,
    registry_commands,
    registry_plugins,
    write_json,
    write_text,
)
from runtime_host import invoke_runtime_host, probe_runtime_host  # noqa: E402
from error_codes import code_for, remediation_for  # noqa: E402


def _check(check_id: str, status: str, detail: str, category: str) -> dict[str, Any]:
    return {
        "id": check_id,
        "status": status,
        "detail": detail,
        "category": category,
        "error_code": None if status == "PASS" else code_for(category, check_id),
        "remediation": None if status == "PASS" else remediation_for(category),
    }


def _markdown(result: dict[str, Any]) -> str:
    lines = [
        "# Target Host Smoke",
        "",
        f"- Verdict: `{result['verdict']}`",
        f"- Target root: `{result['target_root']}`",
        f"- Run dir: `{result['run_dir']}`",
        "",
        "## Checks",
        "",
    ]
    for check in result["checks"]:
        lines.append(f"- `{check['id']}` `{check['status']}` {check['detail']}")
    return "\n".join(lines) + "\n"


def run_target_host_smoke(target_root: Path, timeout_seconds: int) -> dict[str, Any]:
    target = target_root.resolve()
    run_dir = ensure_dir(target / ".workflowprogram" / "runs" / make_run_id("target-host-smoke"))
    spec_path = target / ".workflowprogram" / "design" / "workflow-spec.yaml"
    checks: list[dict[str, Any]] = []
    if not spec_path.is_file():
        checks.append(_check("THS-01", "FAIL", f"spec_path={spec_path}", "target_contract"))
        result = {
            "validator": "target_host_smoke",
            "verdict": "FAIL",
            "target_root": str(target),
            "run_dir": str(run_dir),
            "timestamp": iso_now(),
            "checks": checks,
            "host_invocations": [],
            "exit_code": 1,
        }
        write_json(run_dir / "target-host-smoke-report.json", result)
        write_text(run_dir / "target-host-smoke-report.md", _markdown(result))
        return result

    spec = read_yaml(spec_path)
    spec = spec if isinstance(spec, dict) else {}
    commands = registry_commands(spec)
    plugins = registry_plugins(spec)
    missing_commands = [item for item in commands if not (target / str(item.get("file", ""))).is_file()]
    missing_plugins = [item for item in plugins if not (target / str(item.get("file", ""))).is_file()]
    checks.append(_check("THS-01", "PASS", f"spec_path={spec_path}", "target_contract"))
    checks.append(
        _check(
            "THS-02",
            "PASS" if commands and not missing_commands else ("WARN" if not commands else "FAIL"),
            f"commands={commands} missing={missing_commands}",
            "target_command_discovery",
        )
    )
    checks.append(
        _check(
            "THS-03",
            "PASS" if plugins and not missing_plugins else ("WARN" if not plugins else "FAIL"),
            f"plugins={plugins} missing={missing_plugins}",
            "target_plugin_discovery",
        )
    )

    probe = probe_runtime_host("opencode_native")
    checks.append(
        _check(
            "THS-04",
            "PASS" if probe["ready"] else "ENVIRONMENT-SKIP",
            probe["message"],
            "host_probe",
        )
    )
    host_invocations: list[dict[str, Any]] = []
    if probe["ready"] and commands:
        for command in commands:
            command_name = str(command.get("name", ""))
            if not command_name:
                continue
            invocation = invoke_runtime_host(
                "opencode_native",
                "",
                cwd=str(target),
                command_name=command_name,
                timeout_seconds=timeout_seconds,
                print_logs=True,
            )
            host_invocations.append({"command": command_name, "invocation": invocation})
        host_status = "PASS" if all(item["invocation"]["verdict"] == "PASS" for item in host_invocations) else "ENVIRONMENT-SKIP"
    else:
        host_status = "ENVIRONMENT-SKIP"
    checks.append(
        _check(
            "THS-05",
            host_status,
            f"host_invocations={len(host_invocations)}",
            "host_execution",
        )
    )

    verdict = aggregate_verdicts([check["status"] for check in checks])
    result = {
        "validator": "target_host_smoke",
        "verdict": verdict,
        "target_root": str(target),
        "run_dir": str(run_dir),
        "timestamp": iso_now(),
        "checks": checks,
        "commands": commands,
        "plugins": plugins,
        "host_invocations": host_invocations,
        "exit_code": 0 if verdict != "FAIL" else 1,
    }
    write_json(run_dir / "target-host-smoke-report.json", result)
    write_text(run_dir / "target-host-smoke-report.md", _markdown(result))
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run generated target host reload smoke")
    parser.add_argument("--target-root", required=True)
    parser.add_argument("--timeout-seconds", type=int, default=15)
    parser.add_argument("--json", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    result = run_target_host_smoke(Path(args.target_root), args.timeout_seconds)
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=True))
    else:
        print(json.dumps(result, indent=2, ensure_ascii=True))
    return int(result["exit_code"])


if __name__ == "__main__":
    raise SystemExit(main())
