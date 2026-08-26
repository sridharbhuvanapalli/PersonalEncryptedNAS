import shutil
from pathlib import Path

import yaml

from pnas.applications.truenas_compose import render_truenas_custom_app
from pnas.config import HostingConfig
from pnas.hosting.planning import create_hosting_plan
from pnas.hosting.render import write_hosting_revision


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
            "private_addresses": {"lan": "192.168.1.20", "tailscale": "100.100.1.2"},
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


def test_unified_truenas_compose_is_fully_rendered_and_keeps_secrets_in_files(
    tmp_path: Path,
) -> None:
    env_root = tmp_path / "compose"
    for name in ("nextcloud", "immich", "manager", "proxy"):
        destination = env_root / name
        destination.mkdir(parents=True)
        shutil.copyfile(Path("compose") / name / "env.example", destination / ".env")
    revision = write_hosting_revision(
        hosting_config(), create_hosting_plan(hosting_config()), tmp_path / "state"
    )
    rendered = render_truenas_custom_app(
        project_root=Path.cwd(), revision=revision, env_dir=env_root
    )
    compose = yaml.safe_load(rendered)
    assert "${" not in rendered
    assert set(compose["networks"]) == {
        "nextcloud_backend",
        "immich_backend",
        "pnas_private",
        "pnas_management",
    }
    assert compose["services"]["nextcloud-db"]["networks"] == ["nextcloud_backend"]
    assert compose["services"]["immich-db"]["networks"] == ["immich_backend"]
    assert (
        compose["services"]["immich-server"]["environment"]["DB_PASSWORD_FILE"]
        == "/run/secrets/immich_db_password"  # noqa: S105 - file path, not a password
    )
    assert compose["secrets"]["immich_db_password"]["file"].endswith(
        "/mnt/apps/secrets/immich-db-password"
    )
    assert "provider-token" not in rendered
