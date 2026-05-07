#!/usr/bin/env python3
"""Validate the S1 requirement-logic clarification package for OpenCode runs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def _load_json(path: Path) -> dict[str, object]:
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _first_existing(run_root: Path, name: str) -> Path:
    for root in (run_root / "outputs" / "stages", run_root / "outputs" / "clarification"):
        path = root / name
        if path.is_file():
            return path
    return run_root / "outputs" / "stages" / name


def validate_package(run_root: Path, spec_path: Path | None = None) -> dict[str, object]:
    root = run_root.resolve()
    required = (
        "clarification-record.json",
        "open-questions.json",
        "question-backlog.json",
        "requirement-logic-map.json",
        "design-readiness-report.json",
        "assumption-log.md",
    )
    missing = [name for name in required if not _first_existing(root, name).is_file()]
    record = _load_json(_first_existing(root, "clarification-record.json"))
    questions = _load_json(_first_existing(root, "open-questions.json"))
    backlog = _load_json(_first_existing(root, "question-backlog.json"))
    logic_map = _load_json(_first_existing(root, "requirement-logic-map.json"))
    readiness = _load_json(_first_existing(root, "design-readiness-report.json"))
    lens_names = set(logic_map.get("logic_lenses", {}).keys()) if isinstance(logic_map.get("logic_lenses"), dict) else set()
    required_lenses = {
        "purpose",
        "object_model",
        "process_model",
        "decision_model",
        "evidence_model",
        "acceptance_model",
        "boundary_model",
    }
    semantic_ok = (
        record.get("lead_role") == "requirement-clarification-lead"
        and questions.get("method") == "requirement-logic-interview"
        and isinstance(backlog.get("items"), list)
        and len(backlog.get("items", [])) >= 7
        and required_lenses.issubset(lens_names)
        and readiness.get("requirement_logic_interview_ready") in {True, False}
    )
    status = "PASS" if not missing and semantic_ok else "FAIL"
    return {
        "validator": "clarification_package",
        "status": status,
        "verdict": status,
        "spec": str(spec_path.resolve()) if spec_path else None,
        "run_root": str(root),
        "missing": missing,
        "semantic_ok": semantic_ok,
        "errors": [] if status == "PASS" else [f"missing={missing}; semantic_ok={semantic_ok}"],
        "warnings": [],
        "exit_code": 0 if status == "PASS" else 1,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate WorkflowProgram clarification package")
    parser.add_argument("--run-root", required=True)
    parser.add_argument("--spec")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = validate_package(Path(args.run_root), Path(args.spec) if args.spec else None)
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=True))
    else:
        print(result["status"])
    return int(result["exit_code"])


if __name__ == "__main__":
    raise SystemExit(main())
