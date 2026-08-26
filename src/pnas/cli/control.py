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

from pnas.applications.truenas_compose import ComposeRenderError, render_truenas_custom_app
from pnas.applications.truenas_deploy import deploy_custom_app
from pnas.commissioning import (
    CommissioningValues,
    build_configs,
    check_commissioning,
    load_commissioning_values,
    parse_four_serials,
    render_shell_values,
)
from pnas.config import HostingConfig, PNASConfig, load_config
from pnas.hosting.certificates import certificate_status
from pnas.hosting.planning import (
    HostingExecutionPlan,
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
from pnas.truenas.real import RealTrueNASAdapter

app = typer.Typer(no_args_is_help=True, help="Private Personal NAS operations CLI.")
console = Console()

@app.callback()
def main(
    ctx: typer.Context,
    state_dir: Path = typer.Option(Path("var")),
    config: Path = typer.Option(Path("config/pnas.yaml"), "--config"),
) -> None:
    ctx.obj = {"state_dir": state_dir, "config": config}


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


def _write_yaml_new(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        yaml.safe_dump(value, handle, sort_keys=False)


def _write_secret_new(path: Path, value: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(value)


def _write_text_atomic(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        handle.write(value)
    temporary.replace(path)


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


def _active_hosting_revision(state_dir: Path) -> tuple[Path, HostingExecutionPlan]:
    hosting_dir = (state_dir / "hosting").resolve()
    pointer_path = hosting_dir / "current.json"
    if not pointer_path.is_file():
        raise typer.BadParameter(
            "no approved hosting revision is active; run hosting-plan/apply first"
        )
    pointer = json.loads(pointer_path.read_text(encoding="utf-8"))
    if not isinstance(pointer, dict) or not isinstance(pointer.get("revision"), str):
        raise typer.BadParameter("active hosting revision pointer is invalid")
    revision = Path(pointer["revision"]).resolve()
    revisions_dir = hosting_dir / "revisions"
    if not revision.is_relative_to(revisions_dir):
        raise typer.BadParameter(
            "active hosting revision points outside the managed state directory"
        )
    required = {
        "Caddyfile",
        "Corefile.lan",
        "Corefile.tailscale",
        "db.lan",
        "db.tailscale",
        "deployment.env",
        "manifest.json",
    }
    missing = sorted(name for name in required if not (revision / name).is_file())
    if missing:
        raise typer.BadParameter(f"active hosting revision is incomplete: {', '.join(missing)}")
    plan = HostingExecutionPlan.model_validate_json(
        (revision / "manifest.json").read_text(encoding="utf-8")
    )
    if not plan.approved or not plan.applied or revision.name != plan.plan_id:
        raise typer.BadParameter("active hosting revision is not an approved, applied plan")
    return revision, plan


@app.command("commissioning-init")
def commissioning_init(
    admin_username: str = typer.Option(..., prompt="Named TrueNAS administrator username"),
    management_ip: str = typer.Option(..., prompt="TrueNAS management IPv4 address"),
    service_ip: str = typer.Option(..., prompt="Private service IPv4 address"),
    lan_prefix: int = typer.Option(24, min=8, max=30),
    owner_email: str = typer.Option(..., prompt="Owner email"),
    boot_serial: str = typer.Option(..., prompt="Samsung PM830 serial"),
    apps_serial: str = typer.Option(..., prompt="Inland TN320 serial"),
    recovery_serial: str = typer.Option(..., prompt="Inland 512 GB SATA SSD serial"),
    main_serials: str = typer.Option(
        ..., prompt="Four HC550 serials, separated by commas"
    ),
    archive_serials: str = typer.Option(
        ..., prompt="Four Toshiba serials, separated by commas"
    ),
    template: Path = typer.Option(
        Path("config/pnas.example.yaml"), exists=True, dir_okay=False
    ),
    production_config: Path = typer.Option(Path("config/pnas.yaml")),
    rehearsal_config: Path = typer.Option(Path("config/pnas-rehearsal.yaml")),
    values_file: Path = typer.Option(Path("config/commissioning.yaml")),
) -> None:
    """Interactively create validated, non-secret commissioning configuration files."""
    outputs = (production_config, rehearsal_config, values_file)
    existing = [str(path) for path in outputs if path.exists()]
    if existing:
        raise typer.BadParameter(f"refusing to overwrite existing files: {', '.join(existing)}")
    try:
        values = CommissioningValues.model_validate(
            {
                "management_ip": management_ip,
                "admin_username": admin_username,
                "service_ip": service_ip,
                "lan_prefix": lan_prefix,
                "owner_email": owner_email,
                "boot_serial": boot_serial,
                "apps_serial": apps_serial,
                "recovery_serial": recovery_serial,
                "main_serials": parse_four_serials(main_serials, label="main pool"),
                "archive_serials": parse_four_serials(
                    archive_serials, label="archive pool"
                ),
            }
        )
        production, rehearsal = build_configs(template, values)
    except Exception as exc:
        raise typer.BadParameter(f"commissioning values are invalid: {exc}") from exc
    _write_yaml_new(production_config, production)
    _write_yaml_new(rehearsal_config, rehearsal)
    _write_yaml_new(values_file, values.model_dump(mode="json"))
    console.print_json(
        json.dumps(
            {
                "created": True,
                "contains_secrets": False,
                "production_config": str(production_config),
                "rehearsal_config": str(rehearsal_config),
                "values_file": str(values_file),
                "next": "run commissioning-check --stage workstation",
            }
        )
    )


@app.command("commissioning-check")
def commissioning_check(
    stage: Literal["workstation", "deployment"] = typer.Option("workstation"),
    project_root: Path = typer.Option(Path("."), exists=True, file_okay=False),
    config: Path = typer.Option(Path("config/pnas.yaml"), exists=True, dir_okay=False),
    values: Path = typer.Option(
        Path("config/commissioning.yaml"), exists=True, dir_okay=False
    ),
) -> None:
    """Run read-only prerequisites and print beginner-friendly pass/fail results."""
    checks = check_commissioning(
        stage=stage,
        project_root=project_root.resolve(),
        config_path=config,
        values_path=values,
    )
    passed = all(check.passed for check in checks)
    console.print_json(
        json.dumps(
            {
                "stage": stage,
                "passed": passed,
                "checks": [check.model_dump(mode="json") for check in checks],
            }
        )
    )
    if not passed:
        raise typer.Exit(2)


@app.command("commissioning-export-shell")
def commissioning_export_shell(
    values: Path = typer.Option(
        Path("config/commissioning.yaml"), exists=True, dir_okay=False
    ),
    output: Path = typer.Option(Path(".commissioning.env")),
) -> None:
    """Export validated non-secret values for copy-safe runbook commands."""
    if output.exists():
        raise typer.BadParameter(f"refusing to overwrite existing file: {output}")
    try:
        rendered = render_shell_values(load_commissioning_values(values))
    except Exception as exc:
        raise typer.BadParameter(f"commissioning values are invalid: {type(exc).__name__}") from exc
    _write_secret_new(output, rendered.encode())
    console.print_json(
        json.dumps(
            {
                "created": True,
                "contains_secrets": False,
                "output": str(output),
                "mode": "0600",
                "next": f". ./{output.name}",
            }
        )
    )


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


@app.command("hosting-deploy")
def hosting_deploy(
    ctx: typer.Context,
    execute: bool = typer.Option(
        False,
        "--execute",
        help="Deploy the rendered application; default is a read-only preview.",
    ),
    confirmation: str | None = typer.Option(
        None,
        help="Exact revision-specific confirmation required with --execute.",
    ),
    target: Literal["truenas-api"] = typer.Option(
        "truenas-api",
        help="Supported TrueNAS Custom App API deployment.",
    ),
    project_root: Path = typer.Option(Path("."), exists=True, file_okay=False),
    env_dir: Path | None = typer.Option(
        None,
        help="Directory containing nextcloud/immich/manager/proxy .env files.",
    ),
    api_username: str = typer.Option("pnas-deployer"),
    api_key_file: Path | None = typer.Option(None, dir_okay=False),
) -> None:
    """Preview or deploy the active approved private-hosting revision."""
    state_dir: Path = ctx.obj["state_dir"]
    revision, plan = _active_hosting_revision(state_dir)
    root = project_root.resolve()
    required_project_files = (
        *(
            root / "compose" / name / "compose.yaml"
            for name in ("nextcloud", "immich", "manager", "dns", "proxy")
        ),
        root / "compose" / "manager" / "Dockerfile",
        root / "compose" / "proxy" / "Dockerfile",
    )
    missing = [str(path) for path in required_project_files if not path.is_file()]
    if missing:
        raise typer.BadParameter(f"project root is missing deployment files: {', '.join(missing)}")
    expected = f"DEPLOY PRIVATE HOSTING REVISION {plan.plan_id}"
    try:
        custom_app_yaml = render_truenas_custom_app(
            project_root=root,
            revision=revision,
            env_dir=(env_dir.resolve() if env_dir is not None else None),
        )
    except ComposeRenderError as exc:
        raise typer.BadParameter(str(exc)) from exc
    rendered_path = revision / "truenas-custom-app.yaml"
    _write_text_atomic(rendered_path, custom_app_yaml)
    if not execute:
        console.print_json(
            json.dumps(
                {
                    "executed": False,
                    "target": target,
                    "revision": str(revision),
                    "custom_app": "pnas-services",
                    "rendered_compose": str(rendered_path),
                    "confirmation": expected,
                    "public_service_records": False,
                }
            )
        )
        return
    if confirmation != expected:
        raise typer.BadParameter(f"confirmation must exactly equal: {expected}")
    if api_key_file is None:
        raise typer.BadParameter("--api-key-file is required for TrueNAS API deployment")
    config = load_config(ctx.obj["config"])
    if config.truenas.adapter != "real":
        raise typer.BadParameter("TrueNAS API deployment requires truenas.adapter: real")
    adapter = RealTrueNASAdapter(
        base_url=str(config.truenas.url),
        username=api_username,
        credential_file=api_key_file,
        api_version_name="25.10",
        verify_tls=config.truenas.verify_tls,
    )
    try:
        result = asyncio.run(deploy_custom_app(adapter, custom_app_yaml))
    except Exception as exc:
        _audit_hosting(
            state_dir,
            "hosting-deploy",
            status="failed",
            target=target,
            revision=plan.plan_id,
            error_type=type(exc).__name__,
        )
        raise typer.BadParameter(
            "TrueNAS Custom App deployment failed; inspect the app job in the TrueNAS UI"
        ) from exc
    _audit_hosting(
        state_dir,
        "hosting-deploy",
        status="succeeded",
        target=target,
        revision=plan.plan_id,
        application=result["application"],
        action=result["action"],
        public_service_records=False,
    )
    console.print_json(
        json.dumps(
            {
                "executed": True,
                "target": target,
                "revision": str(revision),
                **result,
                "public_service_records": False,
                "next": "run split-DNS, HTTPS, certificate, and exposure tests",
            }
        )
    )


@app.command("hosting-status")
def hosting_status(ctx: typer.Context) -> None:
    current = ctx.obj["state_dir"] / "hosting" / "current.json"
    if not current.exists():
        console.print_json(json.dumps({"configured": False, "exposure": "private"}))
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
