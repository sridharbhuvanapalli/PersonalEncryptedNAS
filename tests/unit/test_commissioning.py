import stat
from pathlib import Path

import yaml
from typer.testing import CliRunner

from pnas.cli.control import app


def test_commissioning_init_creates_valid_separate_configs_and_workstation_check(
    tmp_path: Path,
) -> None:
    production = tmp_path / "pnas.yaml"
    rehearsal = tmp_path / "pnas-rehearsal.yaml"
    values = tmp_path / "commissioning.yaml"
    runner = CliRunner()
    created = runner.invoke(
        app,
        [
            "commissioning-init",
            "--admin-username",
            "nasadmin",
            "--management-ip",
            "192.168.1.10",
            "--service-ip",
            "192.168.1.20",
            "--owner-email",
            "owner@example.com",
            "--boot-serial",
            "S3BOOTREAL123",
            "--apps-serial",
            "TN320REAL123",
            "--recovery-serial",
            "INLANDREAL512",
            "--main-serials",
            "HC550A,HC550B,HC550C,HC550D",
            "--archive-serials",
            "TOSHIBA1,TOSHIBA2,TOSHIBA3,TOSHIBA4",
            "--production-config",
            str(production),
            "--rehearsal-config",
            str(rehearsal),
            "--values-file",
            str(values),
        ],
    )
    assert created.exit_code == 0, created.output
    assert yaml.safe_load(production.read_text(encoding="utf-8"))["truenas"]["adapter"] == "real"
    assert yaml.safe_load(rehearsal.read_text(encoding="utf-8"))["truenas"]["adapter"] == "mock"
    outputs = (production, rehearsal, values)
    assert all(stat.S_IMODE(path.stat().st_mode) == 0o600 for path in outputs)

    checked = runner.invoke(
        app,
        [
            "commissioning-check",
            "--stage",
            "workstation",
            "--project-root",
            str(Path.cwd()),
            "--config",
            str(production),
            "--values",
            str(values),
        ],
    )
    assert checked.exit_code == 0, checked.output
    assert '"passed": true' in checked.output

    shell_values = tmp_path / ".commissioning.env"
    exported = runner.invoke(
        app,
        [
            "commissioning-export-shell",
            "--values",
            str(values),
            "--output",
            str(shell_values),
        ],
    )
    assert exported.exit_code == 0, exported.output
    assert "PNAS_MANAGEMENT_IP=192.168.1.10" in shell_values.read_text(encoding="utf-8")
    assert stat.S_IMODE(shell_values.stat().st_mode) == 0o600


def test_commissioning_init_rejects_example_serials(tmp_path: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "commissioning-init",
            "--admin-username",
            "nasadmin",
            "--management-ip",
            "192.168.1.10",
            "--service-ip",
            "192.168.1.20",
            "--owner-email",
            "owner@example.com",
            "--boot-serial",
            "BOOTSSD001",
            "--apps-serial",
            "TN320REAL123",
            "--recovery-serial",
            "INLANDREAL512",
            "--main-serials",
            "HC550A,HC550B,HC550C,HC550D",
            "--archive-serials",
            "TOSHIBA1,TOSHIBA2,TOSHIBA3,TOSHIBA4",
            "--production-config",
            str(tmp_path / "pnas.yaml"),
            "--rehearsal-config",
            str(tmp_path / "rehearsal.yaml"),
            "--values-file",
            str(tmp_path / "values.yaml"),
        ],
    )
    assert result.exit_code != 0
    assert "replace every example serial" in result.output


def test_commissioning_init_rejects_addresses_on_different_lans(tmp_path: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "commissioning-init",
            "--admin-username",
            "nasadmin",
            "--management-ip",
            "192.168.1.10",
            "--service-ip",
            "192.168.2.20",
            "--owner-email",
            "owner@example.com",
            "--boot-serial",
            "S3BOOTREAL123",
            "--apps-serial",
            "TN320REAL123",
            "--recovery-serial",
            "INLANDREAL512",
            "--main-serials",
            "HC550A,HC550B,HC550C,HC550D",
            "--archive-serials",
            "TOSHIBA1,TOSHIBA2,TOSHIBA3,TOSHIBA4",
            "--production-config",
            str(tmp_path / "pnas.yaml"),
            "--rehearsal-config",
            str(tmp_path / "rehearsal.yaml"),
            "--values-file",
            str(tmp_path / "values.yaml"),
        ],
    )
    assert result.exit_code != 0
    assert "commissioning values are invalid" in result.output
