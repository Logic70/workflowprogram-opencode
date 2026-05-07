#!/usr/bin/env python3
"""Generate or validate requirement-logic clarification review evidence."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def _candidate_roots(run_root: Path) -> list[Path]:
    return [run_root / "outputs" / "stages", run_root / "outputs" / "clarification"]


def _first_existing(run_root: Path, name: str) -> Path:
    for root in _candidate_roots(run_root):
        path = root / name
        if path.is_file():
            return path
    return run_root / "outputs" / "stages" / name


def review(run_root: Path, spec_path: Path | None = None) -> dict[str, object]:
    root = run_root.resolve()
    required = (
        "clarification-record.json",
        "open-questions.json",
        "question-backlog.json",
        "requirement-logic-map.json",
        "design-readiness-report.json",
        "clarification-challenge-report.json",
        "clarification-handoff.json",
        "clarification-evidence.json",
        "assumption-log.md",
    )
    missing = [name for name in required if not _first_existing(root, name).is_file()]
    open_questions_path = _first_existing(root, "open-questions.json")
    readiness_path = _first_existing(root, "design-readiness-report.json")
    handoff_path = _first_existing(root, "clarification-handoff.json")
    evidence_path = _first_existing(root, "clarification-evidence.json")
    question_backlog_path = _first_existing(root, "question-backlog.json")
    logic_map_path = _first_existing(root, "requirement-logic-map.json")
    method_ok = True
    logic_ok = False
    handoff_ok = False
    evidence_ok = False
    if open_questions_path.is_file():
        try:
            open_questions = json.loads(open_questions_path.read_text(encoding="utf-8"))
        except Exception:
            open_questions = {}
        method_ok = (
            isinstance(open_questions, dict)
            and open_questions.get("method") == "requirement-logic-interview"
            and isinstance(open_questions.get("question_groups"), dict)
        )
    if question_backlog_path.is_file() and logic_map_path.is_file() and readiness_path.is_file():
        try:
            question_backlog = json.loads(question_backlog_path.read_text(encoding="utf-8"))
            logic_map = json.loads(logic_map_path.read_text(encoding="utf-8"))
            readiness = json.loads(readiness_path.read_text(encoding="utf-8"))
        except Exception:
            question_backlog, logic_map, readiness = {}, {}, {}
        lenses = logic_map.get("logic_lenses", {}) if isinstance(logic_map, dict) else {}
        items = question_backlog.get("items", []) if isinstance(question_backlog, dict) else []
        logic_ok = (
            isinstance(lenses, dict)
            and set(lenses) >= {
                "purpose",
                "object_model",
                "process_model",
                "decision_model",
                "evidence_model",
                "acceptance_model",
                "boundary_model",
            }
            and isinstance(items, list)
            and len(items) >= 7
            and readiness.get("generic_questions_blocked") in {True, False}
        )
    if handoff_path.is_file():
        try:
            handoff = json.loads(handoff_path.read_text(encoding="utf-8"))
        except Exception:
            handoff = {}
        handoff_ok = (
            isinstance(handoff.get("s2_inputs"), dict)
            and isinstance(handoff.get("s3_inputs"), dict)
            and bool(handoff.get("logic_map_path"))
            and bool(handoff.get("question_backlog_path"))
        )
    if evidence_path.is_file():
        try:
            evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
        except Exception:
            evidence = {}
        evidence_ok = (
            evidence.get("readback_confirmed") in {True, False}
            and isinstance(evidence.get("challenge_rounds"), int)
            and evidence.get("logic_map_ready") in {True, False}
            and evidence.get("s2_handoff_ready") in {True, False}
            and evidence.get("s3_handoff_ready") in {True, False}
        )
    verdict = "PASS" if not missing else "WARN"
    if not method_ok or not logic_ok or not handoff_ok or not evidence_ok:
        verdict = "WARN"
    return {
        "validator": "clarification_review",
        "run_root": str(root),
        "spec": str(spec_path.resolve()) if spec_path else None,
        "status": verdict,
        "verdict": verdict,
        "missing": missing,
        "method_ok": method_ok,
        "logic_ok": logic_ok,
        "handoff_ok": handoff_ok,
        "evidence_ok": evidence_ok,
        "errors": [] if verdict == "PASS" else ["clarification package is incomplete or not requirement-logic ready"],
        "warnings": [],
        "summary": "Clarification package is requirement-logic ready." if verdict == "PASS" else "Clarification package is incomplete or not requirement-logic ready.",
        "exit_code": 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate clarification review")
    parser.add_argument("--run-root", required=True)
    parser.add_argument("--spec")
    parser.add_argument("--output")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = review(Path(args.run_root), Path(args.spec) if args.spec else None)
    if args.output:
        Path(args.output).write_text(json.dumps(result, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=True) if args.json else result["summary"])
    return int(result["exit_code"])


if __name__ == "__main__":
    raise SystemExit(main())
