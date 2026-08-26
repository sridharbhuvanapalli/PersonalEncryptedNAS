from pathlib import Path


def test_tailnet_policy_limits_family_and_admin_ports() -> None:
    policy = Path("config/tailscale/grants.hujson").read_text(encoding="utf-8")
    assert '"tcp:443", "tcp:53", "udp:53"' in policy
    assert '"tcp:22", "tcp:443", "tcp:53", "udp:53"' in policy
    assert '"ip": ["*"]' not in policy
    assert "example.invalid" in policy
