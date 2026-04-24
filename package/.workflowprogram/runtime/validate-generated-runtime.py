#!/usr/bin/env python3
"""Validate generated target runtime wrapper assets."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


REQUIRED = ("workflow-entry.py", "workflow-runner.py", "validate-run-state.py", "runtime-manifest.json")


def validate(target_root: Path) -> dict[str, object]:
    root = target_root.resolve()
    runtime = root / ".workflowprogram" / "runtime"
    checks = [{"id": f"GEN-{index:02d}", "passed": (runtime / name).is_file(), "detail": str(runtime / name)} for index, name in enumerate(REQUIRED, 1)]
    verdict = "PASS" if all(item["passed"] for item in checks) else "FAIL"
    return {"validator": "generated_runtime_validator", "target_root": str(root), "verdict": verdict, "checks": checks, "exit_code": 0 if verdict == "PASS" else 1}


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate generated target runtime")
    parser.add_argument("--target-root", required=True)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = validate(Path(args.target_root))
    print(json.dumps(result, indent=2, ensure_ascii=True) if args.json else result["verdict"])
    return int(result["exit_code"])


if __name__ == "__main__":
    raise SystemExit(main())

