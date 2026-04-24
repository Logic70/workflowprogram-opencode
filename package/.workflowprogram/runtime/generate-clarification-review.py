#!/usr/bin/env python3
"""Generate a clarification review from WorkflowProgram run evidence."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def review(run_root: Path) -> dict[str, object]:
    root = run_root.resolve()
    clarification = root / "outputs" / "clarification"
    required = ("clarification-record.json", "open-questions.json", "design-readiness-report.json", "assumption-log.md")
    missing = [name for name in required if not (clarification / name).is_file()]
    verdict = "PASS" if not missing else "WARN"
    return {
        "validator": "clarification_review",
        "run_root": str(root),
        "verdict": verdict,
        "missing": missing,
        "summary": "Clarification package is complete." if not missing else "Clarification package is incomplete or not required for this intent.",
        "exit_code": 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate clarification review")
    parser.add_argument("--run-root", required=True)
    parser.add_argument("--output")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = review(Path(args.run_root))
    if args.output:
        Path(args.output).write_text(json.dumps(result, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=True) if args.json else result["summary"])
    return int(result["exit_code"])


if __name__ == "__main__":
    raise SystemExit(main())

