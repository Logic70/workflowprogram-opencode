#!/usr/bin/env python3
"""CLI wrapper for WorkflowProgram managed apply."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from managed_assets_lib import apply_staged, ensure_candidate_root, plan_payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="WorkflowProgram managed apply")
    subparsers = parser.add_subparsers(dest="command", required=True)

    for name in ("plan", "apply-staged"):
        sub = subparsers.add_parser(name)
        sub.add_argument("--target-root", required=True)
        sub.add_argument("--run-root", required=True)
        sub.add_argument("--source-root", required=True)
        sub.add_argument("--producer-version", default="opencode-v2")
        sub.add_argument("--json", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    target_root = Path(args.target_root).resolve()
    run_root = Path(args.run_root).resolve()
    source_root = Path(args.source_root).resolve()
    ensure_candidate_root(source_root)

    if args.command == "plan":
        payload = plan_payload(target_root, source_root, run_root, args.producer_version)
        if args.json:
            json.dump(payload, sys.stdout, indent=2, ensure_ascii=True)
            sys.stdout.write("\n")
        else:
            print(f"status={payload['status']} summary={payload['summary']}")
        return 0 if payload["status"] != "conflict" else 2

    _, result = apply_staged(target_root, source_root, run_root, args.producer_version)
    if args.json:
        json.dump(result, sys.stdout, indent=2, ensure_ascii=True)
        sys.stdout.write("\n")
    else:
        print(f"status={result['status']} applied={len(result['applied'])} conflicts={len(result['conflicts'])}")
    return 0 if result["status"] != "conflict" else 2


if __name__ == "__main__":
    raise SystemExit(main())
