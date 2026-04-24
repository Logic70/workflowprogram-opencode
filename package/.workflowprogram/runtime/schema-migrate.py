#!/usr/bin/env python3
"""Apply minimal WorkflowProgram schema version migrations."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import yaml


RUNTIME_DIR = Path(__file__).resolve().parent
import sys
if str(RUNTIME_DIR) not in sys.path:
    sys.path.insert(0, str(RUNTIME_DIR))

from runtime_common import SCHEMA_VERSION, iso_now, write_json  # noqa: E402


def _read_payload(path: Path) -> Any:
    if path.suffix in {".yaml", ".yml"}:
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return json.loads(path.read_text(encoding="utf-8"))


def _write_payload(path: Path, payload: Any) -> None:
    if path.suffix in {".yaml", ".yml"}:
        path.write_text(yaml.safe_dump(payload, sort_keys=False, allow_unicode=False), encoding="utf-8")
    else:
        write_json(path, payload)


def migrate(path: Path, dry_run: bool) -> dict[str, Any]:
    resolved = path.resolve()
    payload = _read_payload(resolved)
    if not isinstance(payload, dict):
        return {"path": str(resolved), "verdict": "FAIL", "summary": "Only object payloads can be migrated.", "exit_code": 1}
    before = payload.get("schema_version")
    changed = False
    if before is None:
        payload["schema_version"] = SCHEMA_VERSION
        changed = True
    report = {
        "schema_version": SCHEMA_VERSION,
        "path": str(resolved),
        "from_version": before or "legacy-v1",
        "to_version": payload.get("schema_version"),
        "changed": changed,
        "dry_run": dry_run,
        "migrated_at": iso_now(),
        "verdict": "PASS",
        "exit_code": 0,
    }
    if changed and not dry_run:
        backup = resolved.with_suffix(resolved.suffix + ".bak")
        backup.write_text(resolved.read_text(encoding="utf-8"), encoding="utf-8")
        _write_payload(resolved, payload)
        report["backup"] = str(backup)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Migrate WorkflowProgram schema-versioned files")
    parser.add_argument("--path", required=True)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = migrate(Path(args.path), args.dry_run)
    print(json.dumps(result, indent=2, ensure_ascii=True) if args.json else result["verdict"])
    return int(result["exit_code"])


if __name__ == "__main__":
    raise SystemExit(main())

