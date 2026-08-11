from __future__ import annotations

import asyncio
import base64
import json
import os
import secrets
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

import typer
import yaml
from rich.console import Console

from pnas.config import HostingConfig, PNASConfig, load_config
from pnas.hosting.certificates import certificate_status
from pnas.hosting.planning import (
    create_hosting_plan,
    hosting_confirmation,
    load_hosting_plan,
    save_hosting_plan,
    validate_hosting_plan,
)
from pnas.hosting.providers import CloudflareProvider, provider_for
from pnas.hosting.render import (
    private_dns_records,
    render_caddyfile,
    rollback_hosting_revision,
    write_hosting_revision,
)
from pnas.manager.auth import hash_password
from pnas.tailscale.diagnostics import analyze_status

app = typer.Typer(no_args_is_help=True, help="Private Personal NAS operations CLI.")
console = Console()


@app.callback()
def main(
    ctx: typer.Context,
    state_dir: Path = typer.Option(Path("var")),
    config: Path = typer.Option(Path("config/pnas.yaml"), "--config"),
) -> None:
    ctx.obj = {"state_dir": state_dir, "config": config}


def _safe_status(command: str, **extra: object) -> None:
    console.print_json(
        json.dumps({"command": command, "mode": "read-only", "hardware_required": False, **extra})
    )


for command_name in (
    "status",
    "doctor",
    "services",
    "disks",
    "capacity",
    "snapshots",
    "scrub-status",
    "backup-status",
    "restore-test",
    "update-check",
):
    app.command(command_name)(lambda name=command_name: _safe_status(name))


@app.command("backup")
def backup() -> None:
    _safe_status("backup", approval_required=True, executed=False)


@app.command("update-plan")
def update_plan() -> None:
    _safe_status("update-plan", approval_required=True, executed=False)


@app.command("rotate-secret")
def rotate_secret() -> None:
    _safe_status("rotate-secret", approval_required=True, executed=False)


@app.command("recovery-bundle")
def recovery_bundle() -> None:
    _safe_status("recovery-bundle", approval_required=True, executed=False)


@app.command("support-bundle")
def support_bundle() -> None:
    _safe_status("support-bundle", redacted=True, executed=False)


def _hosting(ctx: typer.Context) -> HostingConfig:
    config = load_config(ctx.obj["config"])
    if config.hosting is None:
        raise typer.BadParameter("configuration does not contain a hosting section")
    return config.hosting


def _write_yaml_atomic(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        yaml.safe_dump(value, handle, sort_keys=False)
    temporary.replace(path)


def _write_secret_new(path: Path, value: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(value)


def _audit_hosting(state_dir: Path, event: str, **details: object) -> None:
    audit_dir = state_dir / "hosting"
    audit_dir.mkdir(parents=True, exist_ok=True)
    destination = audit_dir / "audit.jsonl"
    descriptor = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    entry = {
        "timestamp": datetime.now(UTC).isoformat(),
        "event": event,
        **details,
    }
    with os.fdopen(descriptor, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, sort_keys=True) + "\n")


@app.command("hosting-configure")
def hosting_configure(
    ctx: typer.Context,
    base_domain: str = typer.Option(..., help="Private HTTPS base domain or URL."),
    nextcloud_url: str = typer.Option(...),
    immich_url: str = typer.Option(...),
    manager_url: str = typer.Option(...),
    lan_address: str = typer.Option(...),
    management_lan_address: str | None = typer.Option(None),
    email: str = typer.Option(...),
    provider: Literal["cloudflare", "rfc2136", "manual"] = typer.Option(...),
    zone: str = typer.Option(...),
    credential_file: Path | None = typer.Option(None),
    tailscale_address: str = typer.Option(...),
    certificate_environment: Literal["staging", "production"] = typer.Option("staging"),
    rfc2136_server: str | None = typer.Option(None),
    rfc2136_key_name: str | None = typer.Option(None),
) -> None:
    """Validate and save private-only hosting settings; never accepts secret values."""
    path: Path = ctx.obj["config"]
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise typer.BadParameter("configuration root must be a mapping")
    hosting = HostingConfig.model_validate(
        {
            "enabled": True,
            "exposure": "private",
            "base_domain": base_domain,
            "services": {
                "nextcloud": nextcloud_url,
                "immich": immich_url,
                "manager": manager_url,
            },
            "private_addresses": {
                "management_lan": management_lan_address,
                "lan": lan_address,
                "tailscale": tailscale_address,
            },
            "dns": {
                "provider": provider,
                "zone": zone,
                "credential_file": credential_file,
                "manage_public_service_records": False,
                "rfc2136_server": rfc2136_server,
                "rfc2136_key_name": rfc2136_key_name,
            },
            "certificates": {
                "issuer": "letsencrypt",
                "email": email,
                "environment": certificate_environment,
            },
        }
    )
    raw["hosting"] = hosting.model_dump(mode="json")
    try:
        raw["remote_access"]["tailscale"]["private_dns_suffix"] = hosting.base_domain
    except (KeyError, TypeError) as exc:
        raise typer.BadParameter("configuration requires remote_access.tailscale") from exc
    PNASConfig.model_validate(raw)
    _write_yaml_atomic(path, raw)
    console.print_json(
        json.dumps(
            {
                "configured": True,
                "provider": provider,
                "hostnames": list(hosting.hostnames),
                "exposure": "private",
                "public_service_records": False,
            }
        )
    )


@app.command("hosting-plan")
def hosting_plan(ctx: typer.Context, lifetime_minutes: int = typer.Option(30, min=5)) -> None:
    hosting = _hosting(ctx)
    plan = create_hosting_plan(hosting, lifetime_minutes=lifetime_minutes)
    destination = save_hosting_plan(plan, ctx.obj["state_dir"])
    console.print_json(
        json.dumps(
            {
                "plan": str(destination),
                "expires_at": plan.expires_at.isoformat(),
                "confirmation": hosting_confirmation(plan),
                "persistent_public_records": False,
            }
        )
    )


async def _provider_operation(config: HostingConfig, *, write_test: bool) -> dict[str, object]:
    provider = provider_for(config.dns)
    try:
        result = await (provider.write_test() if write_test else provider.verify())
        return dict(result)
    finally:
        if isinstance(provider, CloudflareProvider):
            await provider.close()


@app.command("hosting-provider-check")
def hosting_provider_check(ctx: typer.Context) -> None:
    result = asyncio.run(_provider_operation(_hosting(ctx), write_test=False))
    _audit_hosting(ctx.obj["state_dir"], "provider-check", status="succeeded", **result)
    console.print_json(json.dumps(result))


@app.command("hosting-dns-write-test")
def hosting_dns_write_test(ctx: typer.Context, confirmation: str = typer.Option(...)) -> None:
    hosting = _hosting(ctx)
    expected = f"TEST DNS WRITES IN {hosting.dns.zone} USING {hosting.dns.provider}"
    if confirmation != expected:
        raise typer.BadParameter(f"confirmation must exactly equal: {expected}")
    try:
        result = asyncio.run(_provider_operation(hosting, write_test=True))
    except Exception as exc:
        _audit_hosting(
            ctx.obj["state_dir"],
            "dns-write-test",
            status="failed",
            provider=hosting.dns.provider,
            zone=hosting.dns.zone,
            error_type=type(exc).__name__,
        )
        raise
    _audit_hosting(ctx.obj["state_dir"], "dns-write-test", status="succeeded", **result)
    console.print_json(json.dumps(result))


@app.command("hosting-render")
def hosting_render(ctx: typer.Context, output: Path | None = typer.Option(None)) -> None:
    hosting = _hosting(ctx)
    rendered = render_caddyfile(hosting)
    if output is None:
        console.print(rendered, markup=False)
        return
    descriptor = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        handle.write(rendered)
    console.print_json(
        json.dumps({"caddyfile": str(output), "private_dns": private_dns_records(hosting)})
    )


@app.command("hosting-apply")
def hosting_apply(
    ctx: typer.Context,
    plan: Path = typer.Option(...),
    confirmation: str = typer.Option(...),
) -> None:
    hosting = _hosting(ctx)
    execution_plan = load_hosting_plan(plan)
    validate_hosting_plan(execution_plan, hosting, confirmation)
    applied = execution_plan.model_copy(update={"approved": True, "applied": True})
    revision = write_hosting_revision(hosting, applied, ctx.obj["state_dir"])
    console.print_json(
        json.dumps(
            {
                "applied": True,
                "revision": str(revision),
                "caddyfile": str(revision / "Caddyfile"),
                "public_service_records": False,
            }
        )
    )


@app.command("hosting-status")
def hosting_status(ctx: typer.Context) -> None:
    current = ctx.obj["state_dir"] / "hosting" / "current.json"
    if not current.exists():
        _safe_status("hosting-status", configured=False)
        return
    pointer = json.loads(current.read_text(encoding="utf-8"))
    console.print_json(
        json.dumps(
            {
                "configured": True,
                "active_revision": pointer["revision"],
                "rollback_revisions": len(pointer.get("history", [])),
                "exposure": "private",
            }
        )
    )


@app.command("hosting-renewal-check")
def hosting_renewal_check(
    ctx: typer.Context,
    service: Literal["nextcloud", "immich", "manager"] = typer.Option("nextcloud"),
) -> None:
    hosting = _hosting(ctx)
    result = certificate_status(
        getattr(hosting.services, service), str(hosting.private_addresses.lan)
    )
    console.print_json(json.dumps(result))


@app.command("hosting-rollback")
def hosting_rollback(ctx: typer.Context, confirmation: str = typer.Option(...)) -> None:
    expected = "ROLL BACK PRIVATE HOSTING"
    if confirmation != expected:
        raise typer.BadParameter(f"confirmation must exactly equal: {expected}")
    revision = rollback_hosting_revision(ctx.obj["state_dir"])
    console.print_json(json.dumps({"rolled_back": True, "revision": str(revision)}))


@app.command("tailscale-status")
def tailscale_status(
    status_file: Path = typer.Option(
        ..., exists=True, dir_okay=False, help="Output captured from `tailscale status --json`."
    ),
) -> None:
    """Report node and peer connection modes without contacting the control plane."""
    raw = json.loads(status_file.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise typer.BadParameter("Tailscale status root must be an object")
    console.print_json(analyze_status(raw).model_dump_json())


@app.command("tailscale-doctor")
def tailscale_doctor(
    ctx: typer.Context,
    status_file: Path = typer.Option(..., exists=True, dir_okay=False),
) -> None:
    """Compare a captured live node identity with the approved configuration."""
    raw = json.loads(status_file.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise typer.BadParameter("Tailscale status root must be an object")
    report = analyze_status(raw)
    expected = load_config(ctx.obj["config"]).remote_access.tailscale.hostname
    observed = report.self_dns_name.split(".", 1)[0]
    warnings = list(report.warnings)
    if observed != expected:
        warnings.append(f"node hostname is {observed!r}; expected {expected!r}")
    console.print_json(
        json.dumps(
            {
                "ok": report.self_online and bool(report.tailscale_ips) and observed == expected,
                "expected_hostname": expected,
                "observed_hostname": observed,
                "direct_peers": report.direct_peers,
                "relayed_peers": report.relayed_peers,
                "warnings": warnings,
            }
        )
    )


@app.command("manager-init-secrets")
def manager_init_secrets(
    output_dir: Path = typer.Option(..., file_okay=False),
    password: str = typer.Option(
        ..., prompt=True, hide_input=True, confirmation_prompt=True, help="Administrator password."
    ),
) -> None:
    """Create manager secrets once without retaining the plaintext password."""
    totp_secret = base64.b32encode(secrets.token_bytes(20)).decode("ascii").rstrip("=")
    values = {
        "manager-password-hash": (hash_password(password) + "\n").encode(),
        "manager-session-key": (secrets.token_urlsafe(48) + "\n").encode(),
        "manager-totp-secret": (totp_secret + "\n").encode(),
        "manager-totp-enrollment-uri": (
            "otpauth://totp/PersonalNAS:administrator"
            f"?secret={totp_secret}&issuer=PersonalNAS&digits=6&period=30\n"
        ).encode(),
    }
    existing = [name for name in values if (output_dir / name).exists()]
    if existing:
        raise typer.BadParameter(
            "secret initialization refuses to overwrite existing files: " + ", ".join(existing)
        )
    for name, value in values.items():
        _write_secret_new(output_dir / name, value)
    console.print_json(
        json.dumps(
            {
                "created": sorted(values),
                "directory": str(output_dir),
                "permissions": "0600",
                "next": "enroll TOTP, verify login, then securely remove the enrollment URI file",
            }
        )
    )


if __name__ == "__main__":
    app()
