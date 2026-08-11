from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from pnas.config import HostingConfig
from pnas.hosting.planning import (
    HostingPlanError,
    create_hosting_plan,
    hosting_confirmation,
    validate_hosting_plan,
)
from pnas.hosting.render import (
    private_dns_records,
    render_caddyfile,
    render_corefile,
    render_dns_zone,
    rollback_hosting_revision,
    write_hosting_revision,
)


def hosting_config() -> HostingConfig:
    return HostingConfig.model_validate(
        {
            "enabled": True,
            "exposure": "private",
            "base_domain": "family.example.com",
            "services": {
                "nextcloud": "cloud.family.example.com",
                "immich": "photos.family.example.com",
                "manager": "nas.family.example.com",
            },
            "private_addresses": {"lan": "192.168.1.20", "tailscale": "fd7a:115c:a1e0::1"},
            "dns": {
                "provider": "manual",
                "zone": "example.com",
                "manage_public_service_records": False,
            },
            "certificates": {
                "issuer": "letsencrypt",
                "email": "owner@example.com",
                "environment": "staging",
            },
        }
    )


def test_plan_requires_exact_confirmation_and_current_config() -> None:
    config = hosting_config()
    plan = create_hosting_plan(config)
    validate_hosting_plan(plan, config, hosting_confirmation(plan))
    with pytest.raises(HostingPlanError, match="exactly match"):
        validate_hosting_plan(plan, config, "yes")
    expired = plan.model_copy(update={"expires_at": datetime.now(UTC) - timedelta(seconds=1)})
    with pytest.raises(HostingPlanError, match="expired"):
        validate_hosting_plan(expired, config, hosting_confirmation(expired))


def test_render_is_private_and_ipv6_records_are_aaaa() -> None:
    config = hosting_config()
    caddyfile = render_caddyfile(config)
    assert "local_certs" in caddyfile
    assert "reverse_proxy nextcloud:80" in caddyfile
    assert "0.0.0.0" not in caddyfile  # noqa: S104 - negative security assertion
    records = private_dns_records(config)
    assert all(record["scope"] in {"lan", "tailscale"} for record in records)
    assert {record["type"] for record in records if record["scope"] == "tailscale"} == {"AAAA"}
    tailscale_zone = render_dns_zone(config, scope="tailscale")
    assert "photos IN AAAA fd7a:115c:a1e0::1" in tailscale_zone
    assert "cloud.family.example.com" not in tailscale_zone
    assert "file /etc/coredns/db.tailscale" in render_corefile(config, zone_filename="db.tailscale")


def test_revision_history_supports_rollback(tmp_path: Path) -> None:
    config = hosting_config()
    first = write_hosting_revision(config, create_hosting_plan(config), tmp_path)
    second = write_hosting_revision(config, create_hosting_plan(config), tmp_path)
    assert second != first
    assert (second / "Corefile.lan").is_file()
    assert (second / "db.tailscale").is_file()
    deployment = (second / "deployment.env").read_text(encoding="utf-8")
    assert "PNAS_SERVICE_LAN_BIND_IP=192.168.1.20" in deployment
    assert "PNAS_TAILSCALE_BIND_IP=fd7a:115c:a1e0::1" in deployment
    assert rollback_hosting_revision(tmp_path) == first


def test_caddy_build_plugins_are_immutably_pinned() -> None:
    dockerfile = Path("compose/proxy/Dockerfile").read_text(encoding="utf-8")
    assert "caddy-dns/cloudflare@a8737d095ad5a48ca031cea6ab704057dbc2d250" in dockerfile
    assert "caddy-dns/rfc2136@e50b9f25dd68882c76758446195aca0507be3c05" in dockerfile
    assert ":latest" not in dockerfile
