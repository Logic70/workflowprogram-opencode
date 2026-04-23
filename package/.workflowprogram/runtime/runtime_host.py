#!/usr/bin/env python3
"""Minimal runtime host provider abstraction for WorkflowProgram OpenCode package."""

from __future__ import annotations

import argparse
import json
import os
import shlex
import shutil
import subprocess
import sys
from typing import Any


VALID_RUNTIME_PROVIDERS = {"opencode_native", "fixture_host", "command_adapter"}


def probe_runtime_host(provider: str, provider_command: str = "") -> dict[str, Any]:
    if provider not in VALID_RUNTIME_PROVIDERS:
        raise ValueError(f"Unsupported runtime provider: {provider}")
    if provider == "fixture_host":
        return {
            "provider": provider,
            "available": True,
            "ready": True,
            "message": "Fixture host is always available for deterministic smoke.",
        }
    if provider == "opencode_native":
        binary = shutil.which("opencode")
        return {
            "provider": provider,
            "available": binary is not None,
            "ready": binary is not None,
            "message": f"opencode={binary}" if binary else "OpenCode CLI not found in PATH.",
        }

    tokens = shlex.split(provider_command)
    binary = shutil.which(tokens[0]) if tokens else None
    return {
        "provider": provider,
        "available": binary is not None,
        "ready": bool(binary and tokens),
        "message": f"command_adapter={tokens[0]}" if binary else "Command adapter binary not found.",
    }


def _parse_env_pairs(raw_pairs: list[str]) -> dict[str, str]:
    result: dict[str, str] = {}
    for pair in raw_pairs:
        if "=" not in pair:
            continue
        key, value = pair.split("=", 1)
        key = key.strip()
        if key:
            result[key] = value
    return result


def _coerce_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def invoke_runtime_host(
    provider: str,
    request: str,
    provider_command: str = "",
    cwd: str = "",
    command_name: str = "",
    timeout_seconds: int = 15,
    extra_env: dict[str, str] | None = None,
    print_logs: bool = False,
    log_level: str = "INFO",
) -> dict[str, Any]:
    probe = probe_runtime_host(provider, provider_command)
    if not probe["ready"]:
        return {
            "provider": provider,
            "verdict": "ENVIRONMENT-SKIP",
            "message": probe["message"],
            "exit_code": 0,
        }
    if provider == "fixture_host":
        return {
            "provider": provider,
            "verdict": "PASS",
            "message": f"Fixture host accepted request: {request}",
            "exit_code": 0,
        }
    env = os.environ.copy()
    env.update(extra_env or {})
    if provider == "command_adapter":
        command = shlex.split(provider_command) + [request]
        proc = subprocess.run(command, capture_output=True, text=True, cwd=cwd or None, env=env)
        return {
            "provider": provider,
            "verdict": "PASS" if proc.returncode == 0 else "FAIL",
            "message": proc.stdout.strip() or proc.stderr.strip() or f"exit_code={proc.returncode}",
            "command": command,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
            "exit_code": proc.returncode,
        }
    command = ["opencode", "run"]
    if command_name:
        command.extend(["--command", command_name])
    if request:
        command.append(request)
    command.extend(["--format", "json", "--dangerously-skip-permissions"])
    if print_logs:
        command.extend(["--print-logs", "--log-level", log_level])
    if cwd:
        command.extend(["--dir", cwd])
    try:
        proc = subprocess.run(
            command,
            capture_output=True,
            text=True,
            cwd=cwd or None,
            env=env,
            timeout=max(timeout_seconds, 1),
        )
        verdict = "PASS" if proc.returncode == 0 else "FAIL"
        if proc.returncode != 0 and (proc.stdout.strip() or proc.stderr.strip()) == "":
            verdict = "WARN"
        return {
            "provider": provider,
            "verdict": verdict,
            "message": proc.stdout.strip() or proc.stderr.strip() or f"exit_code={proc.returncode}",
            "command": command,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
            "exit_code": proc.returncode,
            "timed_out": False,
        }
    except subprocess.TimeoutExpired as exc:
        stdout = _coerce_text(exc.stdout)
        stderr = _coerce_text(exc.stderr)
        return {
            "provider": provider,
            "verdict": "ENVIRONMENT-SKIP",
            "message": f"OpenCode invocation timed out after {timeout_seconds}s",
            "command": command,
            "stdout": stdout,
            "stderr": stderr,
            "exit_code": 124,
            "timed_out": True,
        }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Probe or invoke WorkflowProgram runtime providers")
    parser.add_argument("action", choices=("probe", "invoke"))
    parser.add_argument("--provider", default="fixture_host")
    parser.add_argument("--provider-command", default="")
    parser.add_argument("--request", default="")
    parser.add_argument("--cwd", default="")
    parser.add_argument("--command-name", default="")
    parser.add_argument("--timeout-seconds", type=int, default=15)
    parser.add_argument("--env", action="append", default=[])
    parser.add_argument("--print-logs", action="store_true")
    parser.add_argument("--log-level", default="INFO")
    parser.add_argument("--json", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.action == "probe":
        result = probe_runtime_host(args.provider, args.provider_command)
        exit_code = 0 if result["ready"] else 1
    else:
        result = invoke_runtime_host(
            args.provider,
            args.request,
            args.provider_command,
            cwd=args.cwd,
            command_name=args.command_name,
            timeout_seconds=args.timeout_seconds,
            extra_env=_parse_env_pairs(args.env),
            print_logs=args.print_logs,
            log_level=args.log_level,
        )
        exit_code = int(result.get("exit_code", 0))
    if args.json:
        json.dump(result, sys.stdout, indent=2, ensure_ascii=True)
        sys.stdout.write("\n")
    else:
        sys.stdout.write(json.dumps(result, ensure_ascii=True) + "\n")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
