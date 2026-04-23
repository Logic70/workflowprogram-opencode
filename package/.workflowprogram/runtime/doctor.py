#!/usr/bin/env python3
"""Doctor command for WorkflowProgram OpenCode package diagnosis."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path
from typing import Any


RUNTIME_DIR = Path(__file__).resolve().parent
VALIDATORS_DIR = RUNTIME_DIR / "validators"
if str(RUNTIME_DIR) not in sys.path:
    sys.path.insert(0, str(RUNTIME_DIR))
if str(VALIDATORS_DIR) not in sys.path:
    sys.path.insert(0, str(VALIDATORS_DIR))

from runtime_common import detect_package_layout  # noqa: E402
from package_contract_validator import validate_package_contract  # noqa: E402


def _check(check_id: str, passed: bool, detail: str, category: str) -> dict[str, Any]:
    return {
        "id": check_id,
        "passed": passed,
        "detail": detail,
        "category": category,
    }


def _target_writable(target_root: Path | None) -> tuple[bool, str]:
    if target_root is None:
        return True, "target-root-not-requested"
    candidate = target_root.resolve()
    probe_root = candidate if candidate.exists() else candidate.parent
    if not probe_root.exists():
        return False, f"parent-not-found:{probe_root}"
    return os.access(probe_root, os.W_OK), f"probe_root={probe_root}"


def run_doctor(package_root: Path, target_root: Path | None) -> dict[str, Any]:
    layout = detect_package_layout(package_root)
    package_result = validate_package_contract(package_root)
    yaml_ok = True
    try:
        import yaml  # noqa: F401
    except Exception:
        yaml_ok = False

    opencode_bin = shutil.which("opencode")
    writable_ok, writable_detail = _target_writable(target_root)
    target_spec = target_root.resolve() / ".workflowprogram" / "design" / "workflow-spec.yaml" if target_root else None

    checks = [
        _check("DOC-01", package_result["verdict"] == "PASS", f"package_verdict={package_result['verdict']}", "package"),
        _check("DOC-02", layout.runtime_root.is_dir(), f"runtime_root={layout.runtime_root}", "package"),
        _check("DOC-03", bool(sys.executable), f"python={sys.executable}", "python"),
        _check("DOC-04", yaml_ok, "PyYAML importable" if yaml_ok else "PyYAML import failed", "python"),
        _check("DOC-05", opencode_bin is not None, f"opencode={opencode_bin}", "host"),
        _check("DOC-06", writable_ok, writable_detail, "target"),
        _check(
            "DOC-07",
            bool(target_spec and target_spec.is_file()) if target_root else True,
            f"target_spec={target_spec}" if target_spec else "target-root-not-requested",
            "target",
        ),
    ]
    hard_fail = any(not check["passed"] for check in checks if check["id"] in {"DOC-01", "DOC-03", "DOC-04", "DOC-05", "DOC-06"})
    warn_only = any(not check["passed"] for check in checks) and not hard_fail
    verdict = "FAIL" if hard_fail else "WARN" if warn_only else "PASS"
    return {
        "doctor": "workflowprogram-opencode-doctor",
        "package_root": str(layout.package_root),
        "target_root": str(target_root.resolve()) if target_root else None,
        "verdict": verdict,
        "checks": checks,
        "package_validation": package_result,
        "exit_code": 0 if verdict != "FAIL" else 1,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run WorkflowProgram package doctor")
    parser.add_argument("--package-root", required=True)
    parser.add_argument("--target-root")
    parser.add_argument("--json", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    result = run_doctor(
        Path(args.package_root),
        Path(args.target_root) if args.target_root else None,
    )
    if args.json:
        json.dump(result, sys.stdout, indent=2, ensure_ascii=True)
        sys.stdout.write("\n")
    else:
        sys.stdout.write(f"{result['verdict']} package_root={result['package_root']}\n")
        for check in result["checks"]:
            status = "PASS" if check["passed"] else "FAIL"
            sys.stdout.write(f"{status} {check['id']} {check['detail']}\n")
    return result["exit_code"]


if __name__ == "__main__":
    raise SystemExit(main())
