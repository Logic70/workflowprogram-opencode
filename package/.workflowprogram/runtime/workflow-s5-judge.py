#!/usr/bin/env python3
"""Contract-aware S5 judge for WorkflowProgram OpenCode package runs."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def _load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _failure_kind_from_layers(summary: dict[str, Any]) -> str | None:
    layers = summary.get("layers", {})
    for layer_name in ("package", "spec", "target", "run_state"):
        layer = layers.get(layer_name, {})
        if layer.get("verdict") != "FAIL":
            continue
        if layer_name in {"package", "spec"}:
            return "design"
        return "implementation"
    return None


def judge_run(run_root: Path, validation_summary: dict[str, Any] | None = None) -> dict[str, Any]:
    resolved = run_root.resolve()
    summary = validation_summary or _load_json(resolved / "validation-summary.json")
    state = _load_json(resolved / "state.json")
    layers = summary.get("layers", {})
    verdict = str(summary.get("verdict", "WARN")).strip() or "WARN"
    failure_kind = _failure_kind_from_layers(summary)
    first_failed_layer = next(
        (name for name in ("package", "spec", "target", "run_state") if layers.get(name, {}).get("verdict") == "FAIL"),
        None,
    )
    failure_code = f"S5_{str(first_failed_layer).upper()}_FAILED" if first_failed_layer else ""
    payload = {
        "run_root": str(resolved),
        "verdict": verdict,
        "failure_kind": failure_kind,
        "failure_code": failure_code,
        "state_verdict": state.get("verdict"),
        "first_failed_layer": first_failed_layer,
        "layers": {name: layer.get("verdict") for name, layer in layers.items()},
    }

    report_lines = [
        "# S5 Judge Report",
        "",
        f"- Verdict: `{payload['verdict']}`",
        f"- Failure kind: `{payload['failure_kind']}`",
        f"- Failure code: `{payload['failure_code']}`",
        "",
    ]
    if first_failed_layer:
        report_lines.append(f"- First failed layer: `{first_failed_layer}`")
    else:
        report_lines.append("- First failed layer: `none`")
    report_lines.extend(["", "## Layer Verdicts", ""])
    for layer_name, layer_verdict in payload["layers"].items():
        report_lines.append(f"- `{layer_name}`: `{layer_verdict}`")

    stage_payload_path = resolved / "outputs" / "stages" / "s5-judge-summary.json"
    report_path = resolved / "validation-runtime-report.md"
    stage_payload_path.parent.mkdir(parents=True, exist_ok=True)
    stage_payload_path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    report_path.write_text("\n".join(report_lines) + "\n", encoding="utf-8", newline="\n")
    return payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the WorkflowProgram S5 judge")
    parser.add_argument("--run-root", required=True)
    parser.add_argument("--json", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    result = judge_run(Path(args.run_root))
    if args.json:
        json.dump(result, sys.stdout, indent=2, ensure_ascii=True)
        sys.stdout.write("\n")
    else:
        sys.stdout.write(f"{result['verdict']} run_root={result['run_root']}\n")
    return 0 if result["verdict"] != "FAIL" else 1


if __name__ == "__main__":
    raise SystemExit(main())
