#!/usr/bin/env python3
"""Validate lessons delta evidence for a WorkflowProgram run."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def validate(run_root: Path) -> dict[str, object]:
    root = run_root.resolve()
    lessons = root / "outputs" / "stages" / "s6-lessons-summary.json"
    checks = [{"id": "LESSON-01", "passed": lessons.is_file(), "detail": str(lessons)}]
    verdict = "PASS" if all(item["passed"] for item in checks) else "WARN"
    return {"validator": "lessons_delta_validator", "run_root": str(root), "verdict": verdict, "checks": checks, "exit_code": 0}


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate lessons delta evidence")
    parser.add_argument("--run-root", required=True)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = validate(Path(args.run_root))
    print(json.dumps(result, indent=2, ensure_ascii=True) if args.json else result["verdict"])
    return int(result["exit_code"])


if __name__ == "__main__":
    raise SystemExit(main())

