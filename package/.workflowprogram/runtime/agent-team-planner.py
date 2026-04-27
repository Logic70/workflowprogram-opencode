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


def _dispatch_prompt(intent: str, role: dict[str, Any]) -> str:
    agent = role["agent"]
    return (
        f"Act as @{agent} for the current WorkflowProgram `{intent}` run. "
        "Read RUN_ROOT/context.json, RUN_ROOT/state.json, RUN_ROOT/outputs/stages/*.json, "
        "and the target .workflowprogram/design/workflow-spec.yaml when it exists. "
        "Return concrete findings, blockers, and evidence paths; do not redefine the stage plan."
    )


def plan_team(package_root: Path, intent: str) -> dict[str, Any]:
    roles = load_agent_roles(package_root)
    selected = [
        role for role in roles if intent in role.get("stage_affinity", []) or intent in {"audit", "ship"}
    ]
    selected = sorted(selected, key=lambda item: (int(item.get("priority", 100)), item["agent"]))
    fan_in_required = [role["agent"] for role in selected if role.get("fan_in") == "required"]
    recommended_dispatch = [
        {
            "agent": role["agent"],
            "role": role.get("role"),
            "priority": role.get("priority", 100),
            "stage_affinity": role.get("stage_affinity", []),
            "capabilities": role.get("capabilities", []),
            "fan_in": role.get("fan_in", "optional"),
            "dispatch_prompt": _dispatch_prompt(intent, role),
            "expected_output": "finding summary with evidence paths and blockers",
        }
        for role in selected
    ]
    return {
        "planner": "workflowprogram-agent-team-planner",
        "intent": intent,
        "execution_model": "team-plan-with-manual-host-dispatch",
        "subagent_execution": "host-mediated",
        "dispatch_policy": {
            "mode": "manual-host-dispatch",
            "runtime_invokes_subagents": False,
            "host_action": "OpenCode may call the recommended subagents after runtime output is available.",
            "evidence_rule": "Do not claim a subagent ran unless a separate agent response or dispatch trace exists.",
        },
        "stage_contract": {
            "runtime_authority": "RUN_ROOT/outputs/stages/*.json defines the current WorkflowProgram stage state.",
            "agent_authority": "Package agents review or extend evidence for their assigned stage; they do not choose product intent.",
            "target_boundary": "Agents must distinguish WorkflowProgram package files from generated target workflow files.",
        },
        "selected_agents": selected,
        "recommended_dispatch": recommended_dispatch,
        "fan_out": [role["agent"] for role in selected],
        "fan_in": {
            "required_agents": fan_in_required,
            "strategy": "summarize-required-findings-first",
        },
        "notes": [
            "Agentteam describes roles and review topology.",
            "OpenCode subagents remain the execution mechanism; this planner does not invoke them directly.",
            "Stage guidance is effective only when the host follows recommended_dispatch or records equivalent evidence.",
        ],
    }


def team_plan_markdown(plan: dict[str, Any]) -> str:
    lines = [
        "# WorkflowProgram Agent Team Plan",
        "",
        f"- Intent: `{plan.get('intent')}`",
        f"- Execution model: `{plan.get('execution_model')}`",
        f"- Runtime invokes subagents: `{plan.get('dispatch_policy', {}).get('runtime_invokes_subagents')}`",
        "",
        "## Stage Contract",
        "",
    ]
    stage_contract = plan.get("stage_contract", {})
    for key in ("runtime_authority", "agent_authority", "target_boundary"):
        lines.append(f"- {stage_contract.get(key)}")
    lines.extend(["", "## Recommended Dispatch", ""])
    dispatch = plan.get("recommended_dispatch", [])
    if not dispatch:
        lines.append("- No package agent dispatch is recommended for this intent.")
    for item in dispatch:
        lines.append(f"- `@{item.get('agent')}`: {item.get('dispatch_prompt')}")
    lines.extend(
        [
            "",
            "## Evidence Rule",
            "",
            "- This file is a dispatch guide, not proof of execution.",
            "- Do not report that an agent ran unless its response or a dispatch trace exists.",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Plan WorkflowProgram agent teams")
    parser.add_argument("--package-root", required=True)
    parser.add_argument("--intent", required=True)
    parser.add_argument("--output")
    parser.add_argument("--markdown-output")
    parser.add_argument("--json", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    result = plan_team(Path(args.package_root), args.intent)
    if args.output:
        write_json(Path(args.output), result)
    if args.markdown_output:
        markdown_output = Path(args.markdown_output)
        markdown_output.parent.mkdir(parents=True, exist_ok=True)
        markdown_output.write_text(team_plan_markdown(result), encoding="utf-8", newline="\n")
    if args.json or not args.output:
        json.dump(result, sys.stdout, indent=2, ensure_ascii=True)
        sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
