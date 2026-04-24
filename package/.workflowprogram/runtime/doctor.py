#!/usr/bin/env python3
"""Doctor command for WorkflowProgram OpenCode package diagnosis."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


RUNTIME_DIR = Path(__file__).resolve().parent
VALIDATORS_DIR = RUNTIME_DIR / "validators"
if str(RUNTIME_DIR) not in sys.path:
    sys.path.insert(0, str(RUNTIME_DIR))
if str(VALIDATORS_DIR) not in sys.path:
    sys.path.insert(0, str(VALIDATORS_DIR))

from runtime_common import (  # noqa: E402
    PACKAGE_COMMAND_PREFIX,
    default_global_config_root,
    detect_package_layout,
)
from package_contract_validator import validate_package_contract  # noqa: E402
from error_codes import code_for, remediation_for  # noqa: E402


def _check(check_id: str, passed: bool, detail: str, category: str) -> dict[str, Any]:
    return {
        "id": check_id,
        "passed": passed,
        "detail": detail,
        "category": category,
        "error_code": None if passed else code_for(category, check_id),
        "remediation": None if passed else remediation_for(category),
    }


def _target_writable(target_root: Path | None) -> tuple[bool, str]:
    if target_root is None:
        return True, "target-root-not-requested"
    candidate = target_root.resolve()
    probe_root = candidate if candidate.exists() else candidate.parent
    if not probe_root.exists():
        return False, f"parent-not-found:{probe_root}"
    return os.access(probe_root, os.W_OK), f"probe_root={probe_root}"


def _safe_relative(path: Path) -> str:
    try:
        return str(path.resolve())
    except Exception:
        return str(path)


def _iter_files(root: Path, patterns: tuple[str, ...]) -> list[Path]:
    if not root.exists():
        return []
    files: list[Path] = []
    for pattern in patterns:
        files.extend(path for path in root.glob(pattern) if path.is_file())
    return sorted(set(files))


def _asset_inventory(package_root: Path, target_root: Path | None) -> dict[str, Any]:
    roots: list[dict[str, Any]] = []
    package_opencode = package_root.resolve() / ".opencode"
    roots.append({"kind": "package", "path": package_opencode, "owned": True})
    if target_root:
        target = target_root.resolve()
        roots.append({"kind": "project-opencode", "path": target / ".opencode", "owned": (target / ".opencode") == package_opencode})
        roots.append({"kind": "project-claude", "path": target / ".claude", "owned": False})

    global_root = default_global_config_root().resolve()
    roots.append({"kind": "global-opencode", "path": global_root, "owned": False})
    roots.append({"kind": "global-claude", "path": Path.home() / ".claude", "owned": False})
    roots.append({"kind": "oh-my-opencode", "path": global_root / "oh-my-opencode", "owned": False})

    inventory: list[dict[str, Any]] = []
    for item in roots:
        root = Path(item["path"])
        commands = _iter_files(root, ("commands/*.md", ".opencode/commands/*.md"))
        agents = _iter_files(root, ("agents/*.md", ".opencode/agents/*.md"))
        skills = _iter_files(root, ("skills/*/SKILL.md", ".opencode/skills/*/SKILL.md", ".claude/skills/*/SKILL.md"))
        plugins = _iter_files(root, ("plugins/*", ".opencode/plugins/*"))
        inventory.append(
            {
                "kind": item["kind"],
                "path": _safe_relative(root),
                "exists": root.exists(),
                "owned": item["owned"],
                "commands": [path.stem for path in commands],
                "agents": [path.stem for path in agents],
                "skills": [path.parent.name for path in skills],
                "plugins": [path.name for path in plugins],
            }
        )
    return {"sources": inventory}


def _shadowing_findings(inventory: dict[str, Any]) -> list[dict[str, Any]]:
    package_sources = [item for item in inventory["sources"] if item["owned"]]
    package_names: dict[str, set[str]] = {"commands": set(), "agents": set(), "skills": set(), "plugins": set()}
    for source in package_sources:
        for key in package_names:
            package_names[key].update(source.get(key, []))

    findings: list[dict[str, Any]] = []
    for source in inventory["sources"]:
        if source["owned"] or not source["exists"]:
            continue
        for key, owned_names in package_names.items():
            overlap = sorted(owned_names & set(source.get(key, [])))
            wp_like = sorted(
                name for name in source.get(key, []) if key == "commands" and str(name).startswith(PACKAGE_COMMAND_PREFIX)
            )
            if overlap or wp_like:
                findings.append(
                    {
                        "kind": source["kind"],
                        "path": source["path"],
                        "asset_type": key,
                        "overlap": overlap,
                        "wp_like": wp_like,
                    }
                )
    return findings


def _opencode_version(opencode_bin: str | None) -> dict[str, Any]:
    if not opencode_bin:
        return {"available": False, "version": None, "detail": "opencode CLI not found"}
    try:
        proc = subprocess.run(
            [opencode_bin, "--version"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        output = (proc.stdout or proc.stderr).strip()
        return {
            "available": True,
            "version": output or None,
            "detail": output or f"exit_code={proc.returncode}",
            "exit_code": proc.returncode,
        }
    except Exception as exc:
        return {"available": True, "version": None, "detail": str(exc), "exit_code": 1}


def _path_diagnostics(package_root: Path, target_root: Path | None) -> dict[str, Any]:
    paths = {
        "package_root": str(package_root.resolve()),
        "target_root": str(target_root.resolve()) if target_root else None,
    }
    return {
        "platform": sys.platform,
        "cwd": str(Path.cwd()),
        "paths": paths,
        "wsl_windows_path_mix": any(
            isinstance(value, str) and value.startswith("/mnt/") for value in paths.values() if value
        ),
    }


def run_doctor(package_root: Path, target_root: Path | None) -> dict[str, Any]:
    layout = detect_package_layout(package_root)
    package_result = validate_package_contract(package_root)
    yaml_ok = True
    try:
        import yaml  # noqa: F401
    except Exception:
        yaml_ok = False

    opencode_bin = shutil.which("opencode")
    opencode_version = _opencode_version(opencode_bin)
    writable_ok, writable_detail = _target_writable(target_root)
    target_spec = target_root.resolve() / ".workflowprogram" / "design" / "workflow-spec.yaml" if target_root else None
    inventory = _asset_inventory(layout.package_root, target_root)
    shadowing_findings = _shadowing_findings(inventory)
    path_diagnostics = _path_diagnostics(layout.package_root, target_root)
    external_sources_present = [
        source
        for source in inventory["sources"]
        if not source["owned"]
        and source["exists"]
        and (source["commands"] or source["agents"] or source["skills"] or source["plugins"])
    ]

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
        _check(
            "DOC-08",
            not shadowing_findings,
            f"namespace_shadowing={shadowing_findings}",
            "host_isolation",
        ),
        _check(
            "DOC-09",
            True,
            f"external_asset_sources={external_sources_present}",
            "host_isolation",
        ),
        _check(
            "DOC-10",
            bool(opencode_version.get("available")),
            f"opencode_version={opencode_version.get('detail')}",
            "host_compatibility",
        ),
        _check(
            "DOC-11",
            True,
            "After updating WorkflowProgram plugins, restart or reopen OpenCode if host-visible behavior is stale.",
            "host_reload",
        ),
        _check(
            "DOC-12",
            True,
            f"path_diagnostics={path_diagnostics}",
            "path_compatibility",
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
        "host_inventory": inventory,
        "namespace_shadowing": shadowing_findings,
        "opencode_version": opencode_version,
        "path_diagnostics": path_diagnostics,
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
