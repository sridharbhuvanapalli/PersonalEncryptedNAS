from pathlib import Path

import yaml


def test_tailscale_fallback_uses_kernel_networking_and_no_embedded_auth_key() -> None:
    compose = yaml.safe_load(Path("compose/tailscale/compose.yaml").read_text(encoding="utf-8"))
    service = compose["services"]["tailscale"]
    assert service["environment"]["TS_USERSPACE"] == "false"
    assert service["environment"]["TS_ACCEPT_DNS"] == "false"
    assert "TS_AUTHKEY" not in service["environment"]
    assert service["network_mode"] == "host"
    assert "/dev/net/tun:/dev/net/tun" in service["devices"]
    assert set(service["cap_add"]) == {"NET_ADMIN", "NET_RAW"}


def test_tailnet_policy_limits_family_and_admin_ports() -> None:
    policy = Path("config/tailscale/grants.hujson").read_text(encoding="utf-8")
    assert '"tcp:443", "tcp:53", "udp:53"' in policy
    assert '"tcp:22", "tcp:443", "tcp:53", "udp:53"' in policy
    assert '"ip": ["*"]' not in policy
    assert "example.invalid" in policy
