from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import struct
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pnas.backups.runner import require_secret_file


def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode().rstrip("=")


def _b64decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def hash_password(password: str, *, salt: bytes | None = None) -> str:
    if len(password) < 14:
        raise ValueError("administrator password must contain at least 14 characters")
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1, dklen=32)
    return f"scrypt${_b64encode(salt)}${_b64encode(digest)}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, salt_text, digest_text = encoded.strip().split("$", 2)
        if algorithm != "scrypt":
            return False
        digest = hashlib.scrypt(
            password.encode(), salt=_b64decode(salt_text), n=2**14, r=8, p=1, dklen=32
        )
        return hmac.compare_digest(digest, _b64decode(digest_text))
    except (ValueError, TypeError):
        return False


def verify_totp(secret_b32: str, supplied: str, *, now: int | None = None) -> bool:
    if len(supplied) != 6 or not supplied.isdigit():
        return False
    key = base64.b32decode(secret_b32.strip().upper(), casefold=True)
    counter = int((now if now is not None else time.time()) // 30)
    for offset in (-1, 0, 1):
        digest = hmac.new(key, struct.pack(">Q", counter + offset), hashlib.sha1).digest()
        index = digest[-1] & 0x0F
        number = (struct.unpack(">I", digest[index : index + 4])[0] & 0x7FFFFFFF) % 1_000_000
        if hmac.compare_digest(f"{number:06d}", supplied):
            return True
    return False


@dataclass(frozen=True)
class Session:
    subject: str
    issued_at: int
    expires_at: int
    csrf: str
    reauthenticated_at: int


class SessionCodec:
    def __init__(self, key: bytes, *, lifetime_seconds: int = 3600):
        if len(key) < 32:
            raise ValueError("session signing key must contain at least 32 bytes")
        self.key = key
        self.lifetime_seconds = lifetime_seconds

    def create(self, subject: str, *, now: int | None = None) -> tuple[str, Session]:
        issued_at = now if now is not None else int(time.time())
        session = Session(
            subject=subject,
            issued_at=issued_at,
            expires_at=issued_at + self.lifetime_seconds,
            csrf=secrets.token_urlsafe(24),
            reauthenticated_at=issued_at,
        )
        payload = _b64encode(json.dumps(session.__dict__, separators=(",", ":")).encode())
        signature = _b64encode(hmac.new(self.key, payload.encode(), hashlib.sha256).digest())
        return f"{payload}.{signature}", session

    def decode(self, token: str, *, now: int | None = None) -> Session | None:
        try:
            payload, signature = token.split(".", 1)
            expected = _b64encode(hmac.new(self.key, payload.encode(), hashlib.sha256).digest())
            if not hmac.compare_digest(expected, signature):
                return None
            raw: dict[str, Any] = json.loads(_b64decode(payload))
            session = Session(**raw)
            current = now if now is not None else int(time.time())
            return session if current < session.expires_at else None
        except (ValueError, TypeError, KeyError, json.JSONDecodeError):
            return None


@dataclass(frozen=True)
class AuthFiles:
    password_hash: Path
    session_key: Path
    totp_secret: Path | None

    def load(self) -> tuple[str, bytes, str | None]:
        password_hash = require_secret_file(self.password_hash).read_text(encoding="utf-8").strip()
        session_key = require_secret_file(self.session_key).read_bytes().strip()
        totp = (
            require_secret_file(self.totp_secret).read_text(encoding="utf-8").strip()
            if self.totp_secret
            else None
        )
        return password_hash, session_key, totp
