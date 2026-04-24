#!/usr/bin/env python3
"""Best-effort redaction helpers for WorkflowProgram evidence."""

from __future__ import annotations

import re
from typing import Any


SECRET_PATTERNS = (
    re.compile(r"(?i)(api[_-]?key|token|secret|password)\s*[:=]\s*([^\s\"']+)"),
)


def redact_text(value: str) -> str:
    redacted = value
    for pattern in SECRET_PATTERNS:
        redacted = pattern.sub(lambda match: f"{match.group(1)}=<redacted>", redacted)
    return redacted


def redact_payload(payload: Any) -> Any:
    if isinstance(payload, str):
        return redact_text(payload)
    if isinstance(payload, list):
        return [redact_payload(item) for item in payload]
    if isinstance(payload, dict):
        result = {}
        for key, value in payload.items():
            if any(marker in str(key).upper() for marker in ("TOKEN", "API_KEY", "SECRET", "PASSWORD")):
                result[key] = "<redacted>"
            else:
                result[key] = redact_payload(value)
        return result
    return payload

