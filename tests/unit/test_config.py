from pathlib import Path

import pytest
from pydantic import ValidationError

from pnas.config import PNASConfig, load_config


def test_example_configuration_is_valid() -> None:
    config = load_config(Path("config/pnas.example.yaml"))
    assert config.storage.drive_capacity_tb == 18
    assert config.storage.required_transport == "sas"
    assert config.storage.chassis_bays == 12
    assert config.storage.solid_state.apps_primary_capacity_gb == 1000
    assert config.storage.solid_state.apps_target_layout == "mirror"
    assert config.storage.solid_state.recovery_capacity_gb == 512
    assert "APPRECOVERY001" in config.storage.application_device_serials
    assert config.storage.archive_pool.drive_capacity_tb == 3
    assert config.storage.archive_pool.required_transport == "sata"
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
