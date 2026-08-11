from pathlib import Path

import yaml


def compose_files() -> list[Path]:
    return sorted(Path("compose").glob("*/compose.yaml"))


def test_all_images_are_pinned_and_no_docker_socket_or_privileged_mode() -> None:
    assert compose_files()
    for path in compose_files():
        compose = yaml.safe_load(path.read_text(encoding="utf-8"))
        for service in compose["services"].values():
            image = service["image"]
            assert ":latest" not in image and ":release" not in image
            assert ":" in image or "@sha256:" in image
            assert service.get("privileged") is not True
            assert "/var/run/docker.sock" not in str(service.get("volumes", []))


def test_databases_and_caches_publish_no_ports() -> None:
    for path in compose_files():
        compose = yaml.safe_load(path.read_text(encoding="utf-8"))
        for name, service in compose["services"].items():
            if any(token in name for token in ("db", "redis", "valkey")):
                assert "ports" not in service, f"{path}:{name} publishes ports"


def test_only_private_ingress_and_dns_publish_host_ports() -> None:
    for path in compose_files():
        compose = yaml.safe_load(path.read_text(encoding="utf-8"))
        for service in compose["services"].values():
            if "ports" in service:
                assert path in {
                    Path("compose/proxy/compose.yaml"),
                    Path("compose/dns/compose.yaml"),
                }
                rendered_ports = str(service["ports"])
                assert "PNAS_SERVICE_LAN_BIND_IP" in rendered_ports or (
                    "dns-tailscale" in service.get("container_name", "")
                    or "PNAS_TAILSCALE_BIND_IP" in rendered_ports
                )
                assert "0.0.0.0" not in rendered_ports  # noqa: S104


def test_proxy_and_private_dns_bind_only_declared_private_addresses() -> None:
    proxy = yaml.safe_load(Path("compose/proxy/compose.yaml").read_text(encoding="utf-8"))
    ports = str(proxy["services"]["caddy"]["ports"])
    assert "PNAS_SERVICE_LAN_BIND_IP" in ports
    assert "PNAS_TAILSCALE_BIND_IP" in ports
    private_dns = yaml.safe_load(Path("compose/dns/compose.yaml").read_text(encoding="utf-8"))
    assert "PNAS_SERVICE_LAN_BIND_IP" in str(private_dns["services"]["dns-lan"]["ports"])
    assert "PNAS_TAILSCALE_BIND_IP" in str(private_dns["services"]["dns-tailscale"]["ports"])


def test_manager_isolated_on_dedicated_proxy_network() -> None:
    manager = yaml.safe_load(Path("compose/manager/compose.yaml").read_text(encoding="utf-8"))
    assert manager["services"]["pnas-manager"]["networks"] == ["pnas_management"]
    proxy = yaml.safe_load(Path("compose/proxy/compose.yaml").read_text(encoding="utf-8"))
    assert set(proxy["services"]["caddy"]["networks"]) == {
        "pnas_private",
        "pnas_management",
    }
