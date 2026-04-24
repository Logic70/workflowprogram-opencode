#!/usr/bin/env python3
"""Validate generated workflow draft design assets."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def validate(target_root: Path) -> dict[str, object]:
    root = target_root.resolve()
    view = root / ".workflowprogram" / "design" / "workflow-view.md"
    spec = root / ".workflowprogram" / "design" / "workflow-spec.yaml"
    checks = [
        {"id": "DRAFT-01", "passed": view.is_file(), "detail": str(view)},
        {"id": "DRAFT-02", "passed": spec.is_file(), "detail": str(spec)},
    ]
    verdict = "PASS" if all(item["passed"] for item in checks) else "FAIL"
    return {"validator": "workflow_draft_validator", "target_root": str(root), "verdict": verdict, "checks": checks, "exit_code": 0 if verdict == "PASS" else 1}


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate workflow draft assets")
    parser.add_argument("--target-root", required=True)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = validate(Path(args.target_root))
    print(json.dumps(result, indent=2, ensure_ascii=True) if args.json else result["verdict"])
    return int(result["exit_code"])


if __name__ == "__main__":
    raise SystemExit(main())

