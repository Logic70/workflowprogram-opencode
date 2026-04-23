#!/usr/bin/env python3
"""Deterministic intent routing for WorkflowProgram OpenCode package requests."""

from __future__ import annotations

import argparse
import json
import re
import sys
from typing import Any


ENTRY_COMMAND_BY_INTENT = {
    "develop": "wp-develop",
    "validate": "wp-validate",
    "preflight": "wp-preflight",
    "hotfix": "wp-hotfix",
    "iterate": "wp-iterate",
    "ship": "wp-ship",
}

INTENT_KEYWORDS = {
    "preflight": [("preflight", 4), ("readiness", 3), ("ready", 2), ("预检", 4), ("就绪", 3)],
    "hotfix": [("hotfix", 5), ("patch", 3), ("repair", 2), ("热修", 5), ("修复", 3)],
    "iterate": [("iterate", 4), ("improve", 2), ("optimize", 2), ("迭代", 4), ("优化", 2)],
    "ship": [("ship", 4), ("release", 4), ("publish", 3), ("发布", 4), ("交付", 3)],
    "validate": [("validate", 4), ("check", 2), ("verify", 3), ("验证", 4), ("校验", 4), ("检查", 2)],
    "develop": [("develop", 4), ("design", 3), ("build", 2), ("create", 2), ("设计", 4), ("创建", 3)],
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Route a product request to a WorkflowProgram intent")
    parser.add_argument("--request", required=True, help="User request text")
    parser.add_argument("--strict", action="store_true", help="Return exit code 2 when routing is ambiguous")
    parser.add_argument("--json", action="store_true", help="Print JSON output")
    return parser


def explicit_intent(request: str) -> str | None:
    match = re.match(r"^\s*/(wp-develop|wp-validate|wp-preflight|wp-hotfix|wp-iterate|wp-ship)\b", request)
    if not match:
        return None
    return match.group(1).removeprefix("wp-")


def score_request(request: str) -> dict[str, int]:
    text = request.lower()
    scores = {intent: 0 for intent in ENTRY_COMMAND_BY_INTENT}
    for intent, keywords in INTENT_KEYWORDS.items():
        for keyword, weight in keywords:
            if keyword.lower() in text:
                scores[intent] += int(weight)
    return scores


def route_request(request: str) -> dict[str, Any]:
    explicit = explicit_intent(request)
    if explicit:
        return {
            "intent": explicit,
            "entry_command": ENTRY_COMMAND_BY_INTENT[explicit],
            "confidence": 1.0,
            "reason": "explicit-command",
            "scores": {intent: 0 for intent in ENTRY_COMMAND_BY_INTENT},
            "ambiguous": False,
        }

    scores = score_request(request)
    ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    top_intent, top_score = ranked[0]
    second_score = ranked[1][1] if len(ranked) > 1 else 0
    ambiguous = top_score == 0 or top_score == second_score
    confidence = 0.0 if top_score == 0 else min(0.95, 0.5 + 0.1 * top_score)
    chosen_intent = "develop" if ambiguous else top_intent
    return {
        "intent": chosen_intent,
        "entry_command": ENTRY_COMMAND_BY_INTENT[chosen_intent],
        "confidence": confidence,
        "reason": "fallback-default" if ambiguous else "keyword-match",
        "scores": scores,
        "ambiguous": ambiguous,
    }


def main() -> int:
    args = build_parser().parse_args()
    result = route_request(args.request)
    if args.json:
        json.dump(result, sys.stdout, indent=2, ensure_ascii=True)
        sys.stdout.write("\n")
    else:
        sys.stdout.write(
            f"intent={result['intent']} entry_command={result['entry_command']} "
            f"confidence={result['confidence']:.2f} reason={result['reason']}\n"
        )
    return 2 if args.strict and result["ambiguous"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
