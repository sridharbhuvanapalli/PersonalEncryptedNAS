import shutil
import stat
from pathlib import Path

import yaml
from pytest import MonkeyPatch
from typer.testing import CliRunner

from pnas.cli.control import app


def test_manager_secret_initialization_is_exclusive_and_private(tmp_path: Path) -> None:
    destination = tmp_path / "secrets"
    runner = CliRunner()
    password = "an intentionally long manager password"  # noqa: S105 - test-only input
    created = runner.invoke(
        app,
        ["manager-init-secrets", "--output-dir", str(destination)],
        input=f"{password}\n{password}\n",
    )
    assert created.exit_code == 0, created.output
    assert password not in created.output
    expected = {
        "manager-password-hash",
        "manager-session-key",
        "manager-totp-secret",
        "manager-totp-enrollment-uri",
    }
    assert {path.name for path in destination.iterdir()} == expected
    assert all(stat.S_IMODE(path.stat().st_mode) == 0o600 for path in destination.iterdir())
    refused = runner.invoke(
        app,
        ["manager-init-secrets", "--output-dir", str(destination)],
        input=f"{password}\n{password}\n",
    )
    assert refused.exit_code != 0
    assert "refuses to overwrite" in refused.output


def test_manual_hosting_cli_configure_plan_apply_and_deploy_guard(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    config = tmp_path / "pnas.yaml"
    state = tmp_path / "state"
    shutil.copyfile("config/pnas.example.yaml", config)
    runner = CliRunner()
    common = ["--config", str(config), "--state-dir", str(state)]
    configured = runner.invoke(
        app,
        [
            *common,
            "hosting-configure",
            "--base-domain",
            "family.example.com",
            "--nextcloud-url",
            "https://cloud.family.example.com",
            "--immich-url",
            "photos.family.example.com",
            "--manager-url",
            "nas.family.example.com",
            "--lan-address",
            "192.168.1.20",
            "--management-lan-address",
            "192.168.1.10",
            "--tailscale-address",
            "100.100.1.2",
            "--email",
            "owner@example.com",
            "--provider",
            "manual",
            "--zone",
            "example.com",
        ],
    )
    assert configured.exit_code == 0, configured.output
    planned = runner.invoke(app, [*common, "hosting-plan"])
    assert planned.exit_code == 0, planned.output
    plan = next((state / "hosting" / "plans").glob("*.json"))
    confirmation = (
        "CONFIGURE PRIVATE HTTPS FOR cloud.family.example.com, "
        "photos.family.example.com, nas.family.example.com USING manual"
    )
    applied = runner.invoke(
        app,
        [
            *common,
            "hosting-apply",
            "--plan",
            str(plan),
            "--confirmation",
            confirmation,
        ],
    )
    assert applied.exit_code == 0, applied.output
    revision = next((state / "hosting" / "revisions").iterdir())
    assert (revision / "deployment.env").is_file()
    assert "DNS_PROVIDER_CREDENTIAL_FILE=/dev/null" in (revision / "deployment.env").read_text(
        encoding="utf-8"
    )
    expected = f"DEPLOY PRIVATE HOSTING REVISION {revision.name}"
    env_root = tmp_path / "unified-env"
    for name in ("nextcloud", "immich", "manager", "proxy"):
        destination = env_root / name
        destination.mkdir(parents=True)
        shutil.copyfile(Path("compose") / name / "env.example", destination / ".env")
    api_preview = runner.invoke(
        app,
        [
            *common,
            "hosting-deploy",
            "--project-root",
            str(Path.cwd()),
            "--env-dir",
            str(env_root),
        ],
    )
    assert api_preview.exit_code == 0, api_preview.output
    assert '"target": "truenas-api"' in api_preview.output
    assert (revision / "truenas-custom-app.yaml").is_file()

    refused = runner.invoke(
        app,
        [
            *common,
            "hosting-deploy",
            "--execute",
            "--confirmation",
            "yes",
            "--project-root",
            str(Path.cwd()),
            "--env-dir",
            str(env_root),
        ],
    )
    assert refused.exit_code != 0
    assert "confirmation must exactly equal" in refused.output

    raw_config = yaml.safe_load(config.read_text(encoding="utf-8"))
    raw_config["truenas"]["adapter"] = "real"
    config.write_text(yaml.safe_dump(raw_config, sort_keys=False), encoding="utf-8")
    api_key = tmp_path / "deployer-api-key"
    api_key.write_text("test-only-api-key", encoding="utf-8")
    api_key.chmod(0o600)

    async def fake_api_deploy(adapter: object, compose_yaml: str) -> dict[str, str]:
        assert "pnas-manager:" in compose_yaml
        return {
            "application": "pnas-services",
            "action": "created",
            "state": "RUNNING",
            "api_version": "25.10",
        }

    monkeypatch.setattr("pnas.cli.control.deploy_custom_app", fake_api_deploy)
    api_deployed = runner.invoke(
        app,
        [
            *common,
            "hosting-deploy",
            "--execute",
            "--confirmation",
            expected,
            "--project-root",
            str(Path.cwd()),
            "--env-dir",
            str(env_root),
            "--api-key-file",
            str(api_key),
        ],
    )
    assert api_deployed.exit_code == 0, api_deployed.output
    assert '"state": "RUNNING"' in api_deployed.output
