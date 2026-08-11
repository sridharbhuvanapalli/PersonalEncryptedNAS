from __future__ import annotations

import ipaddress
import os
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from pathlib import Path

from fastapi import FastAPI, Form, HTTPException, Request, Response, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from pnas.config import load_config
from pnas.manager.auth import AuthFiles, Session, SessionCodec, verify_password, verify_totp
from pnas.manager.health import (
    HealthProvider,
    LiveHealthProvider,
    MockHealthProvider,
    safe_snapshot,
)
from pnas.manager.state import ManagerState
from pnas.truenas.real import RealTrueNASAdapter

templates = Jinja2Templates(directory=str(Path(__file__).with_name("templates")))


@dataclass(frozen=True)
class ManagerSettings:
    password_hash: str
    session_key: bytes
    totp_secret: str | None
    state_path: Path
    secure_cookie: bool = True
    allowed_networks: tuple[str, ...] = ("127.0.0.0/8",)
    trusted_proxy_networks: tuple[str, ...] = ()
    health_provider: HealthProvider | None = None


class LoginLimiter:
    def __init__(self, *, attempts: int = 5, window_seconds: int = 300):
        self.attempts = attempts
        self.window_seconds = window_seconds
        self.events: dict[str, deque[float]] = defaultdict(deque)

    def _events(self, identity: str, *, now: float | None = None) -> deque[float]:
        current = now if now is not None else time.monotonic()
        events = self.events[identity]
        while events and events[0] < current - self.window_seconds:
            events.popleft()
        return events

    def allow(self, identity: str, *, now: float | None = None) -> bool:
        return len(self._events(identity, now=now)) < self.attempts

    def failure(self, identity: str, *, now: float | None = None) -> None:
        current = now if now is not None else time.monotonic()
        self._events(identity, now=current).append(current)

    def reset(self, identity: str) -> None:
        self.events.pop(identity, None)


def _client_allowed(request: Request, networks: tuple[str, ...]) -> bool:
    if request.client is None:
        return False
    try:
        client = ipaddress.ip_address(request.client.host)
    except ValueError:
        return request.client.host == "testclient" and "testclient" in networks
    return any(client in ipaddress.ip_network(network) for network in networks)


def _request_identity(request: Request, trusted_proxies: tuple[str, ...]) -> str:
    if request.client is None:
        return "unknown"
    immediate = request.client.host
    try:
        proxy_ip = ipaddress.ip_address(immediate)
    except ValueError:
        return immediate
    if not any(proxy_ip in ipaddress.ip_network(network) for network in trusted_proxies):
        return immediate
    forwarded = request.headers.get("x-forwarded-for", "").split(",", 1)[0].strip()
    try:
        return str(ipaddress.ip_address(forwarded))
    except ValueError:
        return immediate


def _validated_networks(raw: str, *, name: str) -> tuple[str, ...]:
    values = tuple(value.strip() for value in raw.split(",") if value.strip())
    if not values:
        raise ValueError(f"{name} must contain at least one explicit network")
    return tuple(str(ipaddress.ip_network(value, strict=True)) for value in values)


def create_app(settings: ManagerSettings) -> FastAPI:
    app = FastAPI(title="Personal NAS Operations Manager", docs_url=None, redoc_url=None)
    codec = SessionCodec(settings.session_key)
    state_store = ManagerState(settings.state_path)
    limiter = LoginLimiter()
    health_provider = settings.health_provider or MockHealthProvider()

    @app.middleware("http")
    async def private_network_only(request: Request, call_next):  # type: ignore[no-untyped-def]
        if not _client_allowed(request, settings.allowed_networks):
            return Response(status_code=status.HTTP_403_FORBIDDEN)
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response

    def current_session(request: Request) -> Session | None:
        return codec.decode(request.cookies.get("pnas_session", ""))

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok", "mode": "read-only"}

    @app.get("/login", response_class=HTMLResponse)
    def login_page(request: Request) -> HTMLResponse:
        return templates.TemplateResponse(request, "login.html", {"error": None})

    @app.post("/login")
    def login(
        request: Request,
        password: str = Form(...),
        totp: str = Form(""),
    ) -> Response:
        identity = _request_identity(request, settings.trusted_proxy_networks)
        if not limiter.allow(identity):
            raise HTTPException(status_code=429, detail="too many login attempts")
        password_ok = verify_password(password, settings.password_hash)
        totp_ok = settings.totp_secret is None or verify_totp(settings.totp_secret, totp)
        if not (password_ok and totp_ok):
            limiter.failure(identity)
            state_store.audit("anonymous", "login", "failure", {"source": identity})
            return templates.TemplateResponse(
                request, "login.html", {"error": "Invalid credentials"}, status_code=401
            )
        limiter.reset(identity)
        token, _ = codec.create("administrator")
        response = RedirectResponse("/", status_code=303)
        response.set_cookie(
            "pnas_session",
            token,
            secure=settings.secure_cookie,
            httponly=True,
            samesite="strict",
            max_age=3600,
        )
        state_store.audit("administrator", "login", "success", {"source": identity})
        return response

    @app.post("/logout")
    def logout(request: Request, csrf: str = Form(...)) -> Response:
        session = current_session(request)
        if session is None or not secrets_compare(session.csrf, csrf):
            raise HTTPException(status_code=403)
        response = RedirectResponse("/login", status_code=303)
        response.delete_cookie("pnas_session")
        return response

    @app.get("/", response_class=HTMLResponse)
    def dashboard(request: Request) -> Response:
        session = current_session(request)
        if session is None:
            return RedirectResponse("/login", status_code=303)
        return templates.TemplateResponse(
            request,
            "dashboard.html",
            {"snapshot": safe_snapshot(health_provider), "csrf": session.csrf},
        )

    @app.post("/actions/{action}/plan")
    def mutation_plan(
        action: str,
        request: Request,
        csrf: str = Form(...),
        password: str = Form(...),
    ) -> dict[str, object]:
        session = current_session(request)
        allowed_actions = {"backup", "restore-test", "update", "expansion"}
        if session is None or not secrets_compare(session.csrf, csrf):
            raise HTTPException(status_code=403)
        if action not in allowed_actions:
            raise HTTPException(status_code=404)
        if not verify_password(password, settings.password_hash):
            raise HTTPException(status_code=401, detail="reauthentication failed")
        state_store.audit("administrator", f"plan.{action}", "success", {})
        return {
            "action": action,
            "status": "planned",
            "executed": False,
            "message": "Review and approve through the corresponding CLI workflow.",
        }

    return app


def secrets_compare(left: str, right: str) -> bool:
    import hmac

    return hmac.compare_digest(left, right)


def settings_from_environment() -> ManagerSettings:
    files = AuthFiles(
        password_hash=Path(os.environ["PNAS_MANAGER_PASSWORD_HASH_FILE"]),
        session_key=Path(os.environ["PNAS_MANAGER_SESSION_KEY_FILE"]),
        totp_secret=Path(os.environ["PNAS_MANAGER_TOTP_SECRET_FILE"]),
    )
    password_hash, session_key, totp_secret = files.load()
    allowed_networks = _validated_networks(
        os.environ["PNAS_MANAGER_ALLOWED_NETWORKS"], name="PNAS_MANAGER_ALLOWED_NETWORKS"
    )
    trusted_proxies = _validated_networks(
        os.environ["PNAS_MANAGER_TRUSTED_PROXY_NETWORKS"],
        name="PNAS_MANAGER_TRUSTED_PROXY_NETWORKS",
    )
    health_provider: HealthProvider = MockHealthProvider()
    if os.environ.get("PNAS_MANAGER_HEALTH_MODE", "mock") == "live":
        config = load_config(Path(os.environ["PNAS_CONFIG_FILE"]))
        if config.truenas.adapter != "real":
            raise ValueError("live manager health requires the real TrueNAS adapter")
        adapter = RealTrueNASAdapter(
            base_url=str(config.truenas.url),
            username=config.truenas.username,
            credential_file=config.truenas.credential_file,
            api_version_name="25.10",
            verify_tls=config.truenas.verify_tls,
        )
        tailscale_status = os.environ.get("PNAS_TAILSCALE_STATUS_FILE")
        health_provider = LiveHealthProvider(
            adapter.call,
            tailscale_status_file=Path(tailscale_status) if tailscale_status else None,
        )
    return ManagerSettings(
        password_hash=password_hash,
        session_key=session_key,
        totp_secret=totp_secret,
        state_path=Path(os.environ.get("PNAS_MANAGER_STATE", "/var/lib/pnas/manager.sqlite3")),
        allowed_networks=allowed_networks,
        trusted_proxy_networks=trusted_proxies,
        health_provider=health_provider,
    )


def main() -> None:
    import uvicorn

    uvicorn.run(create_app(settings_from_environment()), host="0.0.0.0", port=8000)  # noqa: S104
