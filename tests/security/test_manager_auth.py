import base64
import hmac
import json
import sqlite3
import struct
from contextlib import closing
from hashlib import sha1
from pathlib import Path

from fastapi.testclient import TestClient

from pnas.manager.app import ManagerSettings, create_app
from pnas.manager.auth import hash_password

PASSWORD = "correct horse battery staple"  # noqa: S105 - deterministic test credential
TOTP_SECRET = base64.b32encode(b"01234567890123456789").decode()


def totp(secret: str, now: int) -> str:
    key = base64.b32decode(secret)
    digest = hmac.new(key, struct.pack(">Q", now // 30), sha1).digest()
    offset = digest[-1] & 15
    number = (struct.unpack(">I", digest[offset : offset + 4])[0] & 0x7FFFFFFF) % 1_000_000
    return f"{number:06d}"


def client(tmp_path: Path, *, totp_secret: str | None = None) -> TestClient:
    app = create_app(
        ManagerSettings(
            password_hash=hash_password(PASSWORD, salt=b"0123456789abcdef"),
            session_key=b"s" * 32,
            totp_secret=totp_secret,
            state_path=tmp_path / "manager.sqlite3",
            secure_cookie=False,
            allowed_networks=("testclient",),
        )
    )
    return TestClient(app)


def test_dashboard_requires_authentication(tmp_path: Path) -> None:
    response = client(tmp_path).get("/", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/login"


def test_login_and_read_only_dashboard(tmp_path: Path) -> None:
    browser = client(tmp_path)
    response = browser.post("/login", data={"password": PASSWORD, "totp": ""})
    assert response.status_code == 200
    assert "Read-only by default" in response.text
    assert "Mode: mock" in response.text
    assert "pnas_session" in browser.cookies


def test_mutation_requires_csrf_and_reauthentication(tmp_path: Path) -> None:
    browser = client(tmp_path)
    browser.post("/login", data={"password": PASSWORD, "totp": ""})
    assert (
        browser.post("/actions/backup/plan", data={"csrf": "bad", "password": PASSWORD}).status_code
        == 403
    )
    dashboard = browser.get("/").text
    marker = 'name="csrf" value="'
    csrf = dashboard.split(marker, 1)[1].split('"', 1)[0]
    assert (
        browser.post("/actions/backup/plan", data={"csrf": csrf, "password": "wrong"}).status_code
        == 401
    )
    response = browser.post("/actions/backup/plan", data={"csrf": csrf, "password": PASSWORD})
    assert response.json()["executed"] is False


def test_totp_is_enforced(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    now = 1_800_000_000
    monkeypatch.setattr("pnas.manager.auth.time.time", lambda: now)
    browser = client(tmp_path, totp_secret=TOTP_SECRET)
    assert browser.post("/login", data={"password": PASSWORD, "totp": "000000"}).status_code == 401
    assert (
        browser.post(
            "/login", data={"password": PASSWORD, "totp": totp(TOTP_SECRET, now)}
        ).status_code
        == 200
    )


def test_untrusted_forwarded_header_is_not_used_for_audit_identity(tmp_path: Path) -> None:
    browser = client(tmp_path)
    response = browser.post(
        "/login",
        data={"password": PASSWORD, "totp": ""},
        headers={"x-forwarded-for": "100.64.0.99"},
    )
    assert response.status_code == 200
    with closing(sqlite3.connect(tmp_path / "manager.sqlite3")) as database:
        details_raw = database.execute(
            "SELECT details_json FROM manager_audit WHERE action = 'login'"
        ).fetchone()[0]
    assert json.loads(details_raw)["source"] == "testclient"


def test_login_limiter_counts_failures_but_not_successes(tmp_path: Path) -> None:
    browser = client(tmp_path)
    for _ in range(6):
        assert browser.post("/login", data={"password": PASSWORD, "totp": ""}).status_code == 200
    for _ in range(5):
        assert browser.post("/login", data={"password": "wrong", "totp": ""}).status_code == 401
    assert browser.post("/login", data={"password": "wrong", "totp": ""}).status_code == 429
