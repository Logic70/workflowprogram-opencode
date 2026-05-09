#!/usr/bin/env python3
"""Resolve semantic change context for existing WorkflowProgram target mutations."""

from __future__ import annotations

import argparse
import json
import shlex
import sys
from pathlib import Path
from typing import Any


RUNTIME_DIR = Path(__file__).resolve().parent
if str(RUNTIME_DIR) not in sys.path:
    sys.path.insert(0, str(RUNTIME_DIR))

from managed_assets_lib import ALLOWED_MANAGED_PREFIXES  # noqa: E402
from runtime_common import SCHEMA_VERSION, ensure_dir, iso_now, sha256_file, write_json  # noqa: E402


CHANGE_POLICY_INTENTS = {"evolve", "iterate", "hotfix"}


def _summary_tokens(raw: str) -> list[str]:
    try:
        tokens = shlex.split(raw)
    except ValueError:
        tokens = raw.split()
    summary: list[str] = []
    skip_next_for = {"--name", "--complexity", "--command-name", "--plugin-name", "--plugin-id", "--spec", "--draft"}
    skip_next = False
    for token in tokens:
        if skip_next:
            skip_next = False
            continue
        if token in skip_next_for:
            skip_next = True
            continue
        if token.startswith("--"):
            continue
        if token.startswith("/wp-"):
            continue
        summary.append(token)
    return summary


def normalize_change_request(raw: str) -> str:
    return " ".join(_summary_tokens(raw)).strip()


def infer_change_mode(intent: str, change_request: str) -> str:
    text = change_request.lower()
    if intent == "hotfix":
        return "repair"
    if intent == "iterate":
        return "incremental"
    if any(word in text for word in ("redesign", "restructure", "re-architect", "重构", "重新设计")):
        return "redesign"
    return "redesign" if intent == "evolve" else "incremental"


def _candidate_files(candidate_root: Path | None) -> list[str]:
    if candidate_root is None or not candidate_root.is_dir():
        return []
    files: list[str] = []
    for path in sorted(candidate_root.rglob("*")):
        if path.is_file():
            files.append(path.relative_to(candidate_root).as_posix())
    return files


def _declared_scope_for(candidate_files: list[str]) -> list[str]:
    scope: list[str] = []
    for prefix in ALLOWED_MANAGED_PREFIXES:
        if any(path.startswith(prefix) for path in candidate_files):
            scope.append(f"{prefix}**")
    if not scope:
        scope = [f"{prefix}**" for prefix in ALLOWED_MANAGED_PREFIXES]
    return scope


def resolve_change_context(
    *,
    intent: str,
    target_root: Path,
    run_root: Path,
    user_arguments: str,
    confirmed: bool,
    candidate_root: Path | None = None,
) -> dict[str, Any]:
    resolved_target = target_root.resolve()
    base_spec_path = resolved_target / ".workflowprogram" / "design" / "workflow-spec.yaml"
    candidate_rel_files = _candidate_files(candidate_root)
    change_request = normalize_change_request(user_arguments)
    context = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": iso_now(),
        "intent": intent,
        "target_root": str(resolved_target),
        "target_workflow_exists": base_spec_path.is_file(),
        "base_spec_path": ".workflowprogram/design/workflow-spec.yaml",
        "base_spec_absolute_path": str(base_spec_path),
        "base_spec_sha256": sha256_file(base_spec_path) if base_spec_path.is_file() else None,
        "change_request": change_request,
        "change_mode": infer_change_mode(intent, change_request),
        "declared_write_scope": _declared_scope_for(candidate_rel_files),
        "allowed_target_files": candidate_rel_files,
        "requires_user_confirmation": True,
        "confirmed": confirmed,
        "policy_applies": intent in CHANGE_POLICY_INTENTS,
    }
    policy_root = ensure_dir(run_root / "outputs" / "change-policy")
    write_json(policy_root / "change-context.json", context)
    return context


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Resolve WorkflowProgram change context")
    parser.add_argument("--intent", required=True, choices=sorted(CHANGE_POLICY_INTENTS))
    parser.add_argument("--target-root", required=True)
    parser.add_argument("--run-root", required=True)
    parser.add_argument("--user-arguments", default="")
    parser.add_argument("--confirmed", action="store_true")
    parser.add_argument("--candidate-root", default="")
    parser.add_argument("--json", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    candidate_root = Path(args.candidate_root) if args.candidate_root else None
    result = resolve_change_context(
        intent=args.intent,
        target_root=Path(args.target_root),
        run_root=Path(args.run_root),
        user_arguments=args.user_arguments,
        confirmed=args.confirmed,
        candidate_root=candidate_root,
    )
    if args.json:
        json.dump(result, sys.stdout, indent=2, ensure_ascii=True)
        sys.stdout.write("\n")
    else:
        sys.stdout.write(f"change_mode={result['change_mode']} confirmed={result['confirmed']}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
