#!/usr/bin/env python3
"""WorkflowProgram package runtime entry point."""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path


RUNTIME_DIR = Path(__file__).resolve().parent
if str(RUNTIME_DIR) not in sys.path:
    sys.path.insert(0, str(RUNTIME_DIR))

from runtime_common import SUPPORTED_PACKAGE_INTENTS


def _load_runner_module():
    runner_path = RUNTIME_DIR / "workflow-runner.py"
    spec = importlib.util.spec_from_file_location("workflow_runner_runtime", runner_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load runtime module from {runner_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="WorkflowProgram runtime entry point"
    )
    parser.add_argument(
        "intent",
        choices=SUPPORTED_PACKAGE_INTENTS,
        help="WorkflowProgram product intent",
    )
    parser.add_argument(
        "--package-root",
        required=True,
        help="Absolute or relative WP_PACKAGE_ROOT",
    )
    parser.add_argument(
        "--target-root",
        required=True,
        help="Absolute or relative TARGET_ROOT",
    )
    parser.add_argument(
        "--user-arguments",
        default="",
        help="Raw command arguments passed from the package command",
    )
    parser.add_argument(
        "--ai-evidence",
        default="",
        help=(
            "Deprecated legacy host evidence note. It is recorded for diagnostics only "
            "and is not accepted as workflow design proof."
        ),
    )
    parser.add_argument(
        "--spec",
        default="",
        help="Path to the accepted workflow-spec.yaml produced by the design/readback step",
    )
    parser.add_argument(
        "--draft",
        default="",
        help="Path to the matching workflow-spec.md design draft/readback; required for develop with --spec",
    )
    parser.add_argument(
        "--allow-template-fallback",
        action="store_true",
        help="Allow deterministic template generation for fixtures/smoke tests; normal runs should pass --spec",
    )
    parser.add_argument(
        "--confirmed",
        action="store_true",
        help="Confirm that interactive clarification and design readback are complete",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print machine readable output",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    runner_module = _load_runner_module()

    result = runner_module.run_intent(
        intent=args.intent,
        package_root=Path(args.package_root),
        target_root=Path(args.target_root),
        user_arguments=args.user_arguments,
        ai_evidence=args.ai_evidence,
        confirmed=args.confirmed,
        source_spec=args.spec,
        source_draft=args.draft,
        allow_template_fallback=args.allow_template_fallback,
    )

    if args.json:
        json.dump(result, sys.stdout, indent=2, ensure_ascii=True)
        sys.stdout.write("\n")
    else:
        sys.stdout.write(
            f"[{result['verdict']}] intent={result['intent']} "
            f"run_root={result['run_root']}\n"
        )
        sys.stdout.write(f"{result['summary']}\n")
    return 0 if result["exit_code"] == 0 else result["exit_code"]


if __name__ == "__main__":
    raise SystemExit(main())
