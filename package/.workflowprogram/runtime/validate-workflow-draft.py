#!/usr/bin/env python3
"""Validate WorkflowProgram S1 draft and requirement-logic interview evidence."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


REQUIRED_SECTIONS = (
    "User Intent",
    "Clarification Summary",
    "Requirement Logic Interview",
    "Open Questions",
    "Assumptions and Boundaries",
    "Target Workflow Graph Readback",
    "File Plan",
    "Readback Confirmation",
)
LOGIC_LENSES = (
    "Purpose",
    "Object Model",
    "Process Model",
    "Decision Model",
    "Evidence",
    "Acceptance",
    "Boundary",
)
GENERIC_ONLY_PATTERNS = (
    "还有哪些边界",
    "还有什么边界",
    "输入输出",
    "其他约束",
    "anything else",
    "edge cases",
)


def _section_present(text: str, section: str) -> bool:
    return bool(re.search(rf"^##+\s+{re.escape(section)}\s*$", text, flags=re.MULTILINE))


def _rounds(text: str) -> int:
    match = re.search(r"澄清轮次\s*[:：]\s*(\d+)", text)
    return int(match.group(1)) if match else 0


def _validate_draft_text(draft: Path, spec: Path | None, run_root: Path | None) -> tuple[list[dict[str, object]], list[str]]:
    draft_text = draft.read_text(encoding="utf-8") if draft.is_file() else ""
    checks: list[dict[str, object]] = []
    warnings: list[str] = []
    checks.append({"id": "DRAFT-01", "passed": draft.is_file(), "detail": str(draft)})
    checks.append({"id": "DRAFT-02", "passed": draft_text.strip().startswith("#"), "detail": "workflow-spec.md must be markdown"})
    checks.append(
        {
            "id": "DRAFT-03",
            "passed": all(_section_present(draft_text, section) for section in REQUIRED_SECTIONS),
            "detail": f"required_sections={list(REQUIRED_SECTIONS)}",
        }
    )
    checks.append(
        {
            "id": "DRAFT-04",
            "passed": _rounds(draft_text) >= 2,
            "detail": "Clarification Summary.澄清轮次 must be >= 2",
        }
    )
    checks.append(
        {
            "id": "DRAFT-05",
            "passed": all(lens.lower() in draft_text.lower() for lens in LOGIC_LENSES),
            "detail": f"logic_lenses={list(LOGIC_LENSES)}",
        }
    )
    generic_hits = [pattern for pattern in GENERIC_ONLY_PATTERNS if pattern.lower() in draft_text.lower()]
    has_specific_logic = "Requirement Logic Interview" in draft_text and "Evidence Lens" in draft_text
    checks.append(
        {
            "id": "DRAFT-06",
            "passed": not generic_hits or has_specific_logic,
            "detail": f"generic_question_markers={generic_hits}",
        }
    )
    if spec is not None:
        checks.append({"id": "DRAFT-07", "passed": spec.is_file(), "detail": str(spec)})
    if run_root is not None:
        stages_root = run_root / "outputs" / "stages"
        required = (
            "clarification-record.json",
            "open-questions.json",
            "question-backlog.json",
            "requirement-logic-map.json",
            "design-readiness-report.json",
            "clarification-challenge-report.json",
            "clarification-handoff.json",
            "clarification-evidence.json",
        )
        missing = [name for name in required if not (stages_root / name).is_file()]
        checks.append(
            {
                "id": "DRAFT-08",
                "passed": not missing,
                "detail": f"missing_stage_clarification_artifacts={missing}",
            }
        )
    if draft.is_file() and "TBD" in draft_text:
        warnings.append("draft contains TBD")
    if draft.is_file() and "待补" in draft_text:
        warnings.append("draft contains 待补")
    return checks, warnings


def validate(target_root: Path | None = None, spec_path: Path | None = None, run_root: Path | None = None) -> dict[str, object]:
    if spec_path is not None:
        draft = spec_path.resolve()
        spec = (run_root / "workflow-spec.yaml") if run_root is not None else None
        root = run_root.resolve() if run_root is not None else draft.parent
    else:
        if target_root is None:
            raise ValueError("target_root or spec_path is required")
        root = target_root.resolve()
        draft = root / ".workflowprogram" / "design" / "workflow-spec.md"
        spec = root / ".workflowprogram" / "design" / "workflow-spec.yaml"
    checks, warnings = _validate_draft_text(draft, spec, run_root)
    verdict = "PASS" if all(item["passed"] for item in checks) else "FAIL"
    return {
        "validator": "workflow_draft_validator",
        "target_root": str(root),
        "spec": str(draft),
        "status": verdict,
        "verdict": verdict,
        "errors": [str(check["detail"]) for check in checks if not check["passed"]],
        "warnings": warnings,
        "checks": checks,
        "exit_code": 0 if verdict == "PASS" else 1,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate workflow draft assets")
    parser.add_argument("--target-root")
    parser.add_argument("--spec")
    parser.add_argument("--run-root")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = validate(
        Path(args.target_root) if args.target_root else None,
        Path(args.spec) if args.spec else None,
        Path(args.run_root) if args.run_root else None,
    )
    print(json.dumps(result, indent=2, ensure_ascii=True) if args.json else result["verdict"])
    return int(result["exit_code"])


if __name__ == "__main__":
    raise SystemExit(main())
