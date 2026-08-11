from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any

SENSITIVE_KEY = re.compile(
    r"(?:password|passphrase|secret|token|api[_-]?key|credential|authorization|cookie)", re.I
)
BEARER = re.compile(r"(?i)\b(bearer|basic)\s+[A-Za-z0-9._~+/=-]+")
TRUENAS_KEY = re.compile(r"\b\d+-[A-Za-z0-9]{20,}\b")


def redact(value: Any, *, key: str | None = None) -> Any:
    if key and SENSITIVE_KEY.search(key):
        return "[REDACTED]"
    if isinstance(value, str):
        value = BEARER.sub(r"\1 [REDACTED]", value)
        return TRUENAS_KEY.sub("[REDACTED]", value)
    if isinstance(value, Mapping):
        return {str(item_key): redact(item, key=str(item_key)) for item_key, item in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [redact(item) for item in value]
    return value
