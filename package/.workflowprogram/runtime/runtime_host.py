#!/usr/bin/env python3
"""Minimal runtime host provider abstraction for WorkflowProgram OpenCode package."""

from __future__ import annotations

import argparse
import json
import os
import signal
import shlex
import shutil
import subprocess
import sys
from typing import Any

from privacy import redact_text


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


def _terminate_process_tree(proc: subprocess.Popen[str]) -> None:
    if proc.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        return

    try:
        os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
    except ProcessLookupError:
        return
    except Exception:
        proc.terminate()


def _kill_process_tree(proc: subprocess.Popen[str]) -> None:
    if proc.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        return

    try:
        os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
    except ProcessLookupError:
        return
    except Exception:
        proc.kill()


def _run_with_timeout(
    command: list[str],
    cwd: str,
    env: dict[str, str],
    timeout_seconds: int,
) -> dict[str, Any]:
    timeout = max(timeout_seconds, 1)
    popen_kwargs: dict[str, Any] = {
        "stdout": subprocess.PIPE,
        "stderr": subprocess.PIPE,
        "text": True,
        "cwd": cwd or None,
        "env": env,
    }
    if os.name == "nt":
        popen_kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        popen_kwargs["start_new_session"] = True

    proc = subprocess.Popen(command, **popen_kwargs)
    try:
        stdout, stderr = proc.communicate(timeout=timeout)
        return {
            "returncode": proc.returncode,
            "stdout": stdout,
            "stderr": stderr,
            "timed_out": False,
        }
    except subprocess.TimeoutExpired as exc:
        _terminate_process_tree(proc)
        stdout = _coerce_text(exc.stdout)
        stderr = _coerce_text(exc.stderr)
        try:
            more_stdout, more_stderr = proc.communicate(timeout=2)
            stdout += _coerce_text(more_stdout)
            stderr += _coerce_text(more_stderr)
        except subprocess.TimeoutExpired:
            _kill_process_tree(proc)
            try:
                more_stdout, more_stderr = proc.communicate(timeout=2)
                stdout += _coerce_text(more_stdout)
                stderr += _coerce_text(more_stderr)
            except subprocess.TimeoutExpired:
                pass
        return {
            "returncode": 124,
            "stdout": stdout,
            "stderr": stderr,
            "timed_out": True,
        }


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
        proc = _run_with_timeout(command, cwd=cwd, env=env, timeout_seconds=timeout_seconds)
        stdout = proc["stdout"]
        stderr = proc["stderr"]
        if proc["timed_out"]:
            return {
                "provider": provider,
                "verdict": "ENVIRONMENT-SKIP",
                "message": f"Command adapter invocation timed out after {timeout_seconds}s",
                "command": command,
                "stdout": redact_text(stdout),
                "stderr": redact_text(stderr),
                "exit_code": 124,
                "timed_out": True,
            }
        return {
            "provider": provider,
            "verdict": "PASS" if proc["returncode"] == 0 else "FAIL",
            "message": redact_text(stdout.strip() or stderr.strip() or f"exit_code={proc['returncode']}"),
            "command": command,
            "stdout": redact_text(stdout),
            "stderr": redact_text(stderr),
            "exit_code": proc["returncode"],
            "timed_out": False,
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
    proc = _run_with_timeout(command, cwd=cwd, env=env, timeout_seconds=timeout_seconds)
    if proc["timed_out"]:
        return {
            "provider": provider,
            "verdict": "ENVIRONMENT-SKIP",
            "message": f"OpenCode invocation timed out after {timeout_seconds}s",
            "command": command,
            "stdout": redact_text(proc["stdout"]),
            "stderr": redact_text(proc["stderr"]),
            "exit_code": 124,
            "timed_out": True,
        }
    stdout = proc["stdout"]
    stderr = proc["stderr"]
    verdict = "PASS" if proc["returncode"] == 0 else "FAIL"
    if proc["returncode"] != 0 and (stdout.strip() or stderr.strip()) == "":
        verdict = "WARN"
    return {
        "provider": provider,
        "verdict": verdict,
        "message": redact_text(stdout.strip() or stderr.strip() or f"exit_code={proc['returncode']}"),
        "command": command,
        "stdout": redact_text(stdout),
        "stderr": redact_text(stderr),
        "exit_code": proc["returncode"],
        "timed_out": False,
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
