from __future__ import annotations

import json
import os
import shlex
from ipaddress import IPv6Address
from pathlib import Path

from pnas.config import HostingConfig
from pnas.hosting.planning import HostingExecutionPlan


def _acme_dns(config: HostingConfig) -> str:
    if config.dns.provider == "cloudflare":
        return "acme_dns cloudflare {env.CLOUDFLARE_API_TOKEN}"
    if config.dns.provider == "rfc2136":
        return "\n".join(
            [
                "acme_dns rfc2136 {",
                f'  key_name "{config.dns.rfc2136_key_name}"',
                f'  key_alg "{config.dns.rfc2136_key_algorithm}"',
                '  key "{env.RFC2136_TSIG_KEY}"',
                f'  server "{config.dns.rfc2136_server}"',
                "}",
            ]
        )
    return "local_certs"


def render_caddyfile(config: HostingConfig) -> str:
    acme = _acme_dns(config)
    ca_line = (
        "acme_ca https://acme-staging-v02.api.letsencrypt.org/directory"
        if config.certificates.environment == "staging" and config.dns.provider != "manual"
        else ""
    )
    return (
        f"""{{
  admin off
  auto_https disable_redirects
  email {config.certificates.email}
  {acme}
  {ca_line}
}}

{config.services.nextcloud} {{
  encode zstd gzip
  reverse_proxy nextcloud:80
  request_body {{ max_size 10GB }}
  header {{
    Strict-Transport-Security "max-age=31536000"
    X-Content-Type-Options "nosniff"
    X-Frame-Options "SAMEORIGIN"
    Referrer-Policy "no-referrer"
  }}
}}

{config.services.immich} {{
  encode zstd gzip
  reverse_proxy immich-server:2283
  header {{
    Strict-Transport-Security "max-age=31536000"
    X-Content-Type-Options "nosniff"
    Referrer-Policy "no-referrer"
  }}
}}

{config.services.manager} {{
  reverse_proxy pnas-manager:8000
  header {{
    Strict-Transport-Security "max-age=31536000"
    X-Content-Type-Options "nosniff"
    X-Frame-Options "DENY"
    Referrer-Policy "no-referrer"
  }}
}}
""".replace("  \n", "").strip()
        + "\n"
    )


def private_dns_records(config: HostingConfig) -> list[dict[str, str]]:
    records: list[dict[str, str]] = []
    for hostname in config.hostnames:
        records.append(
            {
                "scope": "lan",
                "type": ("AAAA" if isinstance(config.private_addresses.lan, IPv6Address) else "A"),
                "name": hostname,
                "value": str(config.private_addresses.lan),
            }
        )
        if config.private_addresses.tailscale is not None:
            records.append(
                {
                    "scope": "tailscale",
                    "type": (
                        "AAAA"
                        if isinstance(config.private_addresses.tailscale, IPv6Address)
                        else "A"
                    ),
                    "name": hostname,
                    "value": str(config.private_addresses.tailscale),
                }
            )
    return records


def render_dns_zone(config: HostingConfig, *, scope: str) -> str:
    if scope not in {"lan", "tailscale"}:
        raise ValueError("DNS scope must be lan or tailscale")
    address = config.private_addresses.lan if scope == "lan" else config.private_addresses.tailscale
    if address is None:
        raise ValueError("Tailscale DNS rendering requires a Tailscale address")
    record_type = "AAAA" if isinstance(address, IPv6Address) else "A"
    serial = 1
    lines = [
        f"$ORIGIN {config.base_domain}.",
        "$TTL 60",
        f"@ IN SOA ns.{config.base_domain}. hostmaster.{config.base_domain}. (",
        f"  {serial} 3600 600 86400 60 )",
        f"@ IN NS ns.{config.base_domain}.",
        f"ns IN {record_type} {address}",
    ]
    for hostname in config.hostnames:
        relative = hostname.removesuffix(f".{config.base_domain}")
        lines.append(f"{relative} IN {record_type} {address}")
    return "\n".join(lines) + "\n"


def render_corefile(config: HostingConfig, *, zone_filename: str) -> str:
    if "/" in zone_filename or not zone_filename:
        raise ValueError("zone filename must be a simple file name")
    return f"""{config.base_domain}:53 {{
  errors
  file /etc/coredns/{zone_filename}
}}
"""


def write_hosting_revision(
    config: HostingConfig, plan: HostingExecutionPlan, state_dir: Path
) -> Path:
    revision = state_dir / "hosting" / "revisions" / plan.plan_id
    revision.mkdir(parents=True, exist_ok=False)
    files = {
        "Caddyfile": render_caddyfile(config),
        "private-dns.json": json.dumps(private_dns_records(config), indent=2) + "\n",
        "Corefile.lan": render_corefile(config, zone_filename="db.lan"),
        "Corefile.tailscale": render_corefile(config, zone_filename="db.tailscale"),
        "db.lan": render_dns_zone(config, scope="lan"),
        "db.tailscale": render_dns_zone(config, scope="tailscale"),
        "manifest.json": plan.model_dump_json(indent=2) + "\n",
        "deployment.env": "\n".join(
            [
                "PNAS_SERVICE_LAN_BIND_IP=" + shlex.quote(str(config.private_addresses.lan)),
                "PNAS_TAILSCALE_BIND_IP=" + shlex.quote(str(config.private_addresses.tailscale)),
                f"CADDYFILE_PATH={shlex.quote(str((revision / 'Caddyfile').resolve()))}",
                f"COREDNS_LAN_COREFILE={shlex.quote(str((revision / 'Corefile.lan').resolve()))}",
                "COREDNS_TAILSCALE_COREFILE="
                + shlex.quote(str((revision / "Corefile.tailscale").resolve())),
                f"COREDNS_LAN_ZONE={shlex.quote(str((revision / 'db.lan').resolve()))}",
                "COREDNS_TAILSCALE_ZONE=" + shlex.quote(str((revision / "db.tailscale").resolve())),
                f"PNAS_DNS_PROVIDER={shlex.quote(config.dns.provider)}",
                "DNS_PROVIDER_CREDENTIAL_FILE="
                + shlex.quote(
                    str(config.dns.credential_file)
                    if config.dns.credential_file is not None
                    else "/dev/null"
                ),
                "",
            ]
        ),
    }
    for name, content in files.items():
        descriptor = os.open(revision / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(content)
    current = state_dir / "hosting" / "current.json"
    history: list[str] = []
    if current.exists():
        existing = json.loads(current.read_text(encoding="utf-8"))
        history = [str(existing["revision"]), *existing.get("history", [])]
    pointer = {"revision": str(revision), "history": history[:9]}
    temporary = current.with_suffix(".tmp")
    temporary.write_text(json.dumps(pointer, indent=2) + "\n", encoding="utf-8")
    temporary.chmod(0o600)
    temporary.replace(current)
    return revision


def rollback_hosting_revision(state_dir: Path) -> Path:
    current = state_dir / "hosting" / "current.json"
    if not current.exists():
        raise FileNotFoundError("no hosting revision is active")
    pointer = json.loads(current.read_text(encoding="utf-8"))
    history = pointer.get("history", [])
    if not history:
        raise RuntimeError("no prior hosting revision is available")
    previous = Path(history[0])
    if not (previous / "manifest.json").is_file():
        raise RuntimeError("prior hosting revision is incomplete")
    updated = {"revision": str(previous), "history": [pointer["revision"], *history[1:]]}
    temporary = current.with_suffix(".tmp")
    temporary.write_text(json.dumps(updated, indent=2) + "\n", encoding="utf-8")
    temporary.chmod(0o600)
    temporary.replace(current)
    return previous
