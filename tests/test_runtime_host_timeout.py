#!/usr/bin/env python3
"""Regression checks for runtime host timeout cleanup."""

from __future__ import annotations

import sys
import tempfile
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNTIME_DIR = ROOT / "package" / ".workflowprogram" / "runtime"
if str(RUNTIME_DIR) not in sys.path:
    sys.path.insert(0, str(RUNTIME_DIR))

from runtime_host import invoke_runtime_host  # noqa: E402


def assert_timeout_cleans_child_pipe() -> None:
    with tempfile.TemporaryDirectory(prefix="wp-runtime-host-timeout-") as tmp:
        helper = Path(tmp) / "host_hangs.py"
        helper.write_text(
            "\n".join(
                [
                    "import subprocess",
                    "import sys",
                    "import time",
                    "subprocess.Popen([sys.executable, '-c', \"import time; print('child-ready', flush=True); time.sleep(60)\"])",
                    "print('parent-ready', flush=True)",
                    "time.sleep(60)",
                    "",
                ]
            ),
            encoding="utf-8",
            newline="\n",
        )

        started = time.monotonic()
        result = invoke_runtime_host(
            "command_adapter",
            "",
            provider_command=f'"{sys.executable}" "{helper}"',
            timeout_seconds=1,
        )
        elapsed = time.monotonic() - started

        if result["verdict"] != "ENVIRONMENT-SKIP":
            raise AssertionError(f"expected timeout ENVIRONMENT-SKIP, got {result}")
        if result["exit_code"] != 124 or not result.get("timed_out"):
            raise AssertionError(f"timeout metadata missing: {result}")
        if elapsed > 10:
            raise AssertionError(f"timeout cleanup took too long: {elapsed:.2f}s")


def main() -> int:
    assert_timeout_cleans_child_pipe()
    print("runtime host timeout regression checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
