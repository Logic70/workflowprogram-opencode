#!/usr/bin/env python3
"""Real OpenCode host integration smoke for the WorkflowProgram package."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from runtime_common import (
    PACKAGE_PLUGIN_FILE,
    REQUIRED_PACKAGE_AGENTS,
    REQUIRED_PACKAGE_COMMANDS,
    aggregate_verdicts,
    detect_package_layout,
    ensure_dir,
    iso_now,
    make_run_id,
    read_jsonl,
    write_json,
    write_text,
)
from runtime_host import invoke_runtime_host, probe_runtime_host


HOST_COMMAND_SPECS = (
    {
        "name": "wp-develop",
        "request": "host integration smoke --emit-target-command --emit-target-plugin",
        "markers": ("workflow-entry.py", " develop "),
    },
    {
        "name": "wp-validate",
        "request": "",
        "markers": ("workflow-entry.py", " validate "),
    },
)


def _build_check(check_id: str, status: str, detail: str, category: str) -> dict[str, Any]:
    return {
        "id": check_id,
        "status": status,
        "detail": detail,
        "category": category,
    }


def _record_path(run_dir: Path, name: str) -> Path:
    return run_dir / name


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [item for item in read_jsonl(path) if isinstance(item, dict)]


def _contains_command_event(records: list[dict[str, Any]], command_name: str) -> bool:
    for record in records:
        if command_name in json.dumps(record, ensure_ascii=True):
            return True
    return False


def _matching_runtime_records(records: list[dict[str, Any]], markers: tuple[str, ...]) -> list[dict[str, Any]]:
    matched: list[dict[str, Any]] = []
    for record in records:
        command = str(record.get("command", ""))
        if all(marker in command for marker in markers):
            matched.append(record)
    return matched


def _command_seen_in_logs(invocation: dict[str, Any], command_name: str) -> bool:
    haystack = f"{invocation.get('stdout', '')}\n{invocation.get('stderr', '')}"
    return f"command={command_name} command" in haystack


def _markdown_report(result: dict[str, Any]) -> str:
    lines = [
        "# Host Integration Smoke",
        "",
        f"- Verdict: `{result['verdict']}`",
        f"- Package root: `{result['package_root']}`",
        f"- Target root: `{result['target_root']}`",
        f"- Run dir: `{result['run_dir']}`",
        "",
        "## Checks",
        "",
    ]
    for check in result["checks"]:
        lines.append(f"- `{check['id']}` `{check['status']}` {check['detail']}")
    lines.extend(["", "## Command Runs", ""])
    for command_name, payload in result["commands"].items():
        invocation = payload["invocation"]
        lines.extend(
            [
                f"### {command_name}",
                "",
                f"- Invocation verdict: `{invocation['verdict']}`",
                f"- Exit code: `{invocation['exit_code']}`",
                f"- Timed out: `{invocation.get('timed_out', False)}`",
                f"- Plugin loaded: `{payload['plugin_loaded']}`",
                f"- Command observed: `{payload['command_observed']}`",
                f"- Runtime started: `{payload['runtime_started']}`",
                f"- Runtime completed: `{payload['runtime_completed']}`",
                "",
            ]
        )
    return "\n".join(lines) + "\n"


def run_host_integration_smoke(package_root: Path, target_root: Path, timeout_seconds: int) -> dict[str, Any]:
    layout = detect_package_layout(package_root)
    run_dir = ensure_dir(target_root / ".workflowprogram" / "runs" / make_run_id("host-integration"))
    command_dir = layout.commands_dir
    agents_dir = layout.agents_dir
    plugin_file = layout.plugin_file

    probe = probe_runtime_host("opencode_native")
    checks: list[dict[str, Any]] = []
    checks.append(
        _build_check(
            "HST-01",
            "PASS" if probe["ready"] else "ENVIRONMENT-SKIP",
            probe["message"],
            "host_probe",
        )
    )

    command_files = sorted(path.stem for path in command_dir.glob("*.md")) if command_dir.is_dir() else []
    missing_commands = sorted(set(REQUIRED_PACKAGE_COMMANDS) - set(command_files))
    checks.append(
        _build_check(
            "HST-02",
            "PASS" if not missing_commands else "FAIL",
            f"commands_dir={command_dir} missing_commands={missing_commands}",
            "package_contract",
        )
    )

    agent_files = sorted(path.stem for path in agents_dir.glob("*.md")) if agents_dir.is_dir() else []
    missing_agents = sorted(set(REQUIRED_PACKAGE_AGENTS) - set(agent_files))
    checks.append(
        _build_check(
            "HST-03",
            "PASS" if not missing_agents else "FAIL",
            f"agents_dir={agents_dir} missing_agents={missing_agents}",
            "package_contract",
        )
    )

    checks.append(
        _build_check(
            "HST-04",
            "PASS" if plugin_file.is_file() else "FAIL",
            f"plugin_file={plugin_file.name if plugin_file.exists() else PACKAGE_PLUGIN_FILE}",
            "package_contract",
        )
    )

    commands: dict[str, Any] = {}
    if probe["ready"]:
        for spec in HOST_COMMAND_SPECS:
            command_name = spec["name"]
            command_run_dir = ensure_dir(run_dir / command_name)
            extra_env = {
                "WORKFLOWPROGRAM_HOST_SMOKE_DIR": str(command_run_dir),
                "WORKFLOWPROGRAM_PACKAGE_ROOT": str(package_root.resolve()),
                "WORKFLOWPROGRAM_RUNTIME_ROOT": str(layout.runtime_root.resolve()),
            }
            invocation = invoke_runtime_host(
                "opencode_native",
                spec["request"],
                cwd=str(target_root.resolve()),
                command_name=command_name,
                timeout_seconds=timeout_seconds,
                extra_env=extra_env,
                print_logs=True,
            )
            plugin_loaded = _load_json(_record_path(command_run_dir, "plugin-loaded.json")) is not None
            command_events = _load_jsonl(_record_path(command_run_dir, "command-events.jsonl"))
            runtime_before = _matching_runtime_records(
                _load_jsonl(_record_path(command_run_dir, "runtime-before.jsonl")),
                spec["markers"],
            )
            runtime_after = _matching_runtime_records(
                _load_jsonl(_record_path(command_run_dir, "runtime-after.jsonl")),
                spec["markers"],
            )
            session_events = _load_jsonl(_record_path(command_run_dir, "session-events.jsonl"))
            commands[command_name] = {
                "invocation": invocation,
                "plugin_loaded": plugin_loaded,
                "command_observed": _contains_command_event(command_events, command_name)
                or _command_seen_in_logs(invocation, command_name),
                "runtime_started": bool(runtime_before),
                "runtime_completed": bool(runtime_after),
                "runtime_exit_codes": [record.get("exitCode") for record in runtime_after],
                "session_events": session_events,
            }
    else:
        for spec in HOST_COMMAND_SPECS:
            commands[spec["name"]] = {
                "invocation": {
                    "provider": "opencode_native",
                    "verdict": "ENVIRONMENT-SKIP",
                    "message": probe["message"],
                    "exit_code": 0,
                    "timed_out": False,
                },
                "plugin_loaded": False,
                "command_observed": False,
                "runtime_started": False,
                "runtime_completed": False,
                "runtime_exit_codes": [],
                "session_events": [],
            }

    plugin_loaded_all = all(item["plugin_loaded"] for item in commands.values()) if commands else False
    plugin_loaded_any = any(item["plugin_loaded"] for item in commands.values()) if commands else False
    timed_out_any = any(item["invocation"].get("timed_out", False) for item in commands.values()) if commands else False
    checks.append(
        _build_check(
            "HST-05",
            (
                "PASS"
                if plugin_loaded_all
                else ("ENVIRONMENT-SKIP" if plugin_loaded_any or not probe["ready"] else "FAIL")
            ),
            f"plugin_loaded={[name for name, item in commands.items() if item['plugin_loaded']]}",
            "host_integration",
        )
    )

    command_observed_all = all(item["command_observed"] for item in commands.values()) if commands else False
    command_observed_any = any(item["command_observed"] for item in commands.values()) if commands else False
    checks.append(
        _build_check(
            "HST-06",
            (
                "PASS"
                if command_observed_all
                else (
                    "ENVIRONMENT-SKIP"
                    if command_observed_any or plugin_loaded_any or timed_out_any or not probe["ready"]
                    else "FAIL"
                )
            ),
            f"command_observed={[name for name, item in commands.items() if item['command_observed']]}",
            "host_integration",
        )
    )

    runtime_started_all = all(item["runtime_started"] for item in commands.values()) if commands else False
    checks.append(
        _build_check(
            "HST-07",
            (
                "PASS"
                if runtime_started_all
                else ("ENVIRONMENT-SKIP" if probe["ready"] and command_observed_all else "ENVIRONMENT-SKIP")
            ),
            f"runtime_started={[name for name, item in commands.items() if item['runtime_started']]}",
            "host_execution",
        )
    )

    runtime_completed_all = all(item["runtime_completed"] for item in commands.values()) if commands else False
    completion_status = "PASS" if runtime_completed_all else ("ENVIRONMENT-SKIP" if not runtime_started_all else "FAIL")
    checks.append(
        _build_check(
            "HST-08",
            completion_status,
            f"runtime_completed={[name for name, item in commands.items() if item['runtime_completed']]}",
            "host_execution",
        )
    )

    verdict = aggregate_verdicts([check["status"] for check in checks])
    result = {
        "validator": "host_integration_smoke",
        "verdict": verdict,
        "package_root": str(package_root.resolve()),
        "target_root": str(target_root.resolve()),
        "run_dir": str(run_dir),
        "timestamp": iso_now(),
        "checks": checks,
        "commands": commands,
        "exit_code": 0 if verdict != "FAIL" else 1,
    }
    write_json(run_dir / "host-integration-report.json", result)
    write_text(run_dir / "host-integration-report.md", _markdown_report(result))
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run real OpenCode host integration smoke")
    parser.add_argument("--package-root", required=True)
    parser.add_argument("--target-root", required=True)
    parser.add_argument("--timeout-seconds", type=int, default=15)
    parser.add_argument("--json", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    result = run_host_integration_smoke(
        Path(args.package_root),
        Path(args.target_root),
        timeout_seconds=args.timeout_seconds,
    )
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=True))
    else:
        print(json.dumps(result, indent=2, ensure_ascii=True))
    return int(result["exit_code"])


if __name__ == "__main__":
    raise SystemExit(main())
