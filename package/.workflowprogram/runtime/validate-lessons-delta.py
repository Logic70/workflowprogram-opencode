#!/usr/bin/env python3
"""Validate lessons delta evidence for a WorkflowProgram run."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


REQUIRED_LIST_KEYS = (
    "observations",
    "failure_patterns",
    "reusable_constraints",
    "residual_risks",
    "evolve_recommendations",
)
REQUIRED_TOP_KEYS = set(REQUIRED_LIST_KEYS) | {"schema_version", "intent", "source_verdicts"}


def _load_json(path: Path) -> dict[str, object]:
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _check(check_id: str, passed: bool, detail: str) -> dict[str, object]:
    return {"id": check_id, "passed": passed, "detail": detail}


def validate(run_root: Path) -> dict[str, object]:
    root = run_root.resolve()
    lessons = root / "outputs" / "stages" / "s6-lessons-summary.json"
    payload = _load_json(lessons)
    checks: list[dict[str, object]] = []
    checks.append(_check("LESSON-01", lessons.is_file(), str(lessons)))

    missing = sorted(REQUIRED_TOP_KEYS - set(payload.keys()))
    checks.append(_check("LESSON-02", not missing, f"missing={missing}"))

    list_shape_ok = all(isinstance(payload.get(key), list) for key in REQUIRED_LIST_KEYS)
    checks.append(_check("LESSON-03", list_shape_ok, f"list_keys={list(REQUIRED_LIST_KEYS)}"))

    source_verdicts = payload.get("source_verdicts", {})
    source_ok = isinstance(source_verdicts, dict) and isinstance(source_verdicts.get("validation"), str) and isinstance(source_verdicts.get("judge"), str)
    checks.append(_check("LESSON-04", source_ok, f"source_verdicts={source_verdicts}"))

    validation_summary = _load_json(root / "validation-summary.json")
    judge_summary = _load_json(root / "outputs" / "stages" / "s5-judge-summary.json")
    consistency_ok = True
    if source_ok and validation_summary:
        consistency_ok = consistency_ok and source_verdicts.get("validation") == validation_summary.get("verdict")
    if source_ok and judge_summary:
        consistency_ok = consistency_ok and source_verdicts.get("judge") == judge_summary.get("verdict")
    checks.append(_check("LESSON-05", consistency_ok, "source verdicts match validation/judge evidence when present"))

    actionable_ok = bool(payload.get("observations")) and bool(payload.get("evolve_recommendations"))
    checks.append(_check("LESSON-06", actionable_ok, "observations and evolve recommendations must not be empty"))

    verdict = "PASS" if all(bool(item["passed"]) for item in checks) else "WARN"
    return {
        "validator": "lessons_delta_validator",
        "run_root": str(root),
        "verdict": verdict,
        "checks": checks,
        "exit_code": 0,
    }


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
