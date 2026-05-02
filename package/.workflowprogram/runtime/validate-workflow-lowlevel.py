#!/usr/bin/env python3
"""Legacy optional validator for generated workflow lowlevel design assets."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def validate(target_root: Path) -> dict[str, object]:
    root = target_root.resolve()
    lowlevel = root / ".workflowprogram" / "design" / "workflow-lowlevel.md"
    text = lowlevel.read_text(encoding="utf-8") if lowlevel.is_file() else ""
    if not lowlevel.is_file():
        return {
            "validator": "workflow_lowlevel_validator",
            "target_root": str(root),
            "verdict": "WARN",
            "summary": "workflow-lowlevel.md is a legacy optional diagnostic view and is not required for core success",
            "checks": [
                {
                    "id": "LOW-LEGACY-01",
                    "passed": True,
                    "detail": "workflow-lowlevel.md absent by design",
                }
            ],
            "exit_code": 0,
        }
    checks = [
        {"id": "LOW-01", "passed": lowlevel.is_file(), "detail": str(lowlevel)},
        {"id": "LOW-02", "passed": "Runtime Contract" in text, "detail": "Runtime Contract section required"},
    ]
    verdict = "PASS" if all(item["passed"] for item in checks) else "FAIL"
    return {"validator": "workflow_lowlevel_validator", "target_root": str(root), "verdict": verdict, "checks": checks, "exit_code": 0 if verdict == "PASS" else 1}


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate workflow lowlevel assets")
    parser.add_argument("--target-root", required=True)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = validate(Path(args.target_root))
    print(json.dumps(result, indent=2, ensure_ascii=True) if args.json else result["verdict"])
    return int(result["exit_code"])


if __name__ == "__main__":
    raise SystemExit(main())
