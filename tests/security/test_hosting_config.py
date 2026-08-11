from pathlib import Path

import pytest
from pydantic import ValidationError

from pnas.config import HostingConfig
from pnas.hosting.providers import ProviderError, read_cloudflare_token


def hosting_data() -> dict[str, object]:
    return {
        "enabled": True,
        "exposure": "private",
        "base_domain": "family.example.com",
        "services": {
            "nextcloud": "https://cloud.family.example.com",
            "immich": "photos.family.example.com",
            "manager": "nas.family.example.com",
        },
        "private_addresses": {
            "management_lan": "192.168.1.10",
            "lan": "192.168.1.20",
            "tailscale": "100.100.1.2",
        },
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


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("exposure",), "public"),
        (("private_addresses", "lan"), "8.8.8.8"),
        (("private_addresses", "lan"), "127.0.0.1"),
        (("dns", "manage_public_service_records"), True),
        (("private_addresses", "tailscale"), None),
        (("services", "nextcloud"), "http://cloud.family.example.com"),
        (("services", "nextcloud"), "https://cloud.family.example.com/path"),
    ],
)
def test_public_or_unsafe_hosting_settings_are_rejected(
    path: tuple[str, ...], value: object
) -> None:
    data = hosting_data()
    target = data
    for key in path[:-1]:
        target = target[key]  # type: ignore[index,assignment]
    target[path[-1]] = value  # type: ignore[index]
    with pytest.raises(ValidationError):
        HostingConfig.model_validate(data)


def test_service_names_cannot_escape_base_domain() -> None:
    data = hosting_data()
    data["services"]["manager"] = "nas.attacker.example"  # type: ignore[index]
    with pytest.raises(ValidationError, match="below the base domain"):
        HostingConfig.model_validate(data)


def test_management_and_service_addresses_must_be_separate() -> None:
    data = hosting_data()
    data["private_addresses"]["management_lan"] = "192.168.1.20"  # type: ignore[index]
    with pytest.raises(ValidationError, match="must be different"):
        HostingConfig.model_validate(data)


def test_cloudflare_token_requires_private_file_and_rejects_global_key(
    tmp_path: Path,
) -> None:
    token_file = tmp_path / "token"
    token_file.write_text("a" * 37, encoding="utf-8")
    token_file.chmod(0o600)
    with pytest.raises(ProviderError, match="Global API Keys"):
        read_cloudflare_token(token_file)
    token_file.write_text("scoped-token", encoding="utf-8")
    token_file.chmod(0o644)
    with pytest.raises(PermissionError, match="0600"):
        read_cloudflare_token(token_file)
