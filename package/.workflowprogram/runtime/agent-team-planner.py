#!/usr/bin/env python3
"""Plan WorkflowProgram package agent teams without executing subagents."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import yaml


RUNTIME_DIR = Path(__file__).resolve().parent
if str(RUNTIME_DIR) not in sys.path:
    sys.path.insert(0, str(RUNTIME_DIR))

from runtime_common import detect_package_layout, write_json  # noqa: E402


def _frontmatter(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return {}
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}
    payload = yaml.safe_load(parts[1]) or {}
    return payload if isinstance(payload, dict) else {}


def load_agent_roles(package_root: Path) -> list[dict[str, Any]]:
    layout = detect_package_layout(package_root)
    roles: list[dict[str, Any]] = []
    if not layout.agents_dir.is_dir():
        return roles
    for path in sorted(layout.agents_dir.glob("*.md")):
        frontmatter = _frontmatter(path)
        roles.append(
            {
                "agent": path.stem,
                "file": str(path),
                "role": frontmatter.get("workflowprogram_role", path.stem),
                "stage_affinity": frontmatter.get("workflowprogram_stage_affinity", []),
                "capabilities": frontmatter.get("workflowprogram_capabilities", []),
                "trigger": frontmatter.get("workflowprogram_trigger"),
                "priority": frontmatter.get("workflowprogram_priority", 100),
                "fan_in": frontmatter.get("workflowprogram_fan_in", "optional"),
            }
        )
    return roles


def plan_team(package_root: Path, intent: str) -> dict[str, Any]:
    roles = load_agent_roles(package_root)
    selected = [
        role for role in roles if intent in role.get("stage_affinity", []) or intent in {"audit", "ship"}
    ]
    selected = sorted(selected, key=lambda item: (int(item.get("priority", 100)), item["agent"]))
    fan_in_required = [role["agent"] for role in selected if role.get("fan_in") == "required"]
    return {
        "planner": "workflowprogram-agent-team-planner",
        "intent": intent,
        "execution_model": "team-plan-only",
        "subagent_execution": "host-mediated",
        "selected_agents": selected,
        "fan_out": [role["agent"] for role in selected],
        "fan_in": {
            "required_agents": fan_in_required,
            "strategy": "summarize-required-findings-first",
        },
        "notes": [
            "Agentteam describes roles and review topology.",
            "OpenCode subagents remain the execution mechanism; this planner does not invoke them directly.",
        ],
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Plan WorkflowProgram agent teams")
    parser.add_argument("--package-root", required=True)
    parser.add_argument("--intent", required=True)
    parser.add_argument("--output")
    parser.add_argument("--json", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    result = plan_team(Path(args.package_root), args.intent)
    if args.output:
        write_json(Path(args.output), result)
    if args.json or not args.output:
        json.dump(result, sys.stdout, indent=2, ensure_ascii=True)
        sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

