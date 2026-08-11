from pathlib import Path

import pytest
from pydantic import ValidationError

from pnas.config import PNASConfig, load_config


def test_example_configuration_is_valid() -> None:
    config = load_config(Path("config/pnas.example.yaml"))
    assert config.storage.drive_capacity_tb is None
    assert config.truenas.adapter == "mock"
    assert config.remote_access.tailscale.userspace_networking is False
    assert config.remote_access.tailscale.private_dns_suffix == "nas.cloudpathz.com"


def test_real_adapter_requires_https() -> None:
    config = load_config(Path("config/pnas.example.yaml"))
    raw = config.model_dump(mode="json")
    raw["truenas"]["adapter"] = "real"
    raw["truenas"]["url"] = "http://truenas.local"
    with pytest.raises(ValidationError, match="require HTTPS"):
        PNASConfig.model_validate(raw)


@pytest.mark.parametrize(
    ("field", "unsafe"),
    [
        ("userspace_networking", True),
        ("host_network", False),
        ("accept_dns", True),
        ("advertise_exit_node", True),
        ("funnel", True),
        ("public_ingress", True),
        ("router_port_forwarding", True),
        ("require_device_approval", False),
    ],
)
def test_remote_access_rejects_unsafe_modes(field: str, unsafe: bool) -> None:
    config = load_config(Path("config/pnas.example.yaml"))
    raw = config.model_dump(mode="json")
    raw["remote_access"]["tailscale"][field] = unsafe
    with pytest.raises(ValidationError):
        PNASConfig.model_validate(raw)


def test_enabled_hosting_requires_tailscale_address_and_matching_private_suffix() -> None:
    config = load_config(Path("config/pnas.example.yaml"))
    raw = config.model_dump(mode="json")
    raw["hosting"]["enabled"] = True
    with pytest.raises(ValidationError, match="requires a Tailscale address"):
        PNASConfig.model_validate(raw)
    raw["hosting"]["private_addresses"]["tailscale"] = "100.100.1.2"
    raw["hosting"]["base_domain"] = "other.cloudpathz.com"
    raw["hosting"]["services"] = {
        "nextcloud": "cloud.other.cloudpathz.com",
        "immich": "photos.other.cloudpathz.com",
        "manager": "ops.other.cloudpathz.com",
    }
    with pytest.raises(ValidationError, match="private DNS suffix"):
        PNASConfig.model_validate(raw)
