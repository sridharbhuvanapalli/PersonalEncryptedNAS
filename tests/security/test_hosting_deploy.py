import json
from pathlib import Path

import pytest
import typer

from pnas.applications.truenas_compose import ComposeRenderError, read_strict_env
from pnas.cli.control import _active_hosting_revision


def test_deployment_env_rejects_keys_that_could_alter_process_execution(tmp_path: Path) -> None:
    env_file = tmp_path / "deployment.env"
    env_file.write_text("CADDY_DATA_PATH=/safe\nLD_PRELOAD=/untrusted/library\n", encoding="utf-8")
    with pytest.raises(ComposeRenderError, match="not allowed"):
        read_strict_env(env_file, {"CADDY_DATA_PATH"})


def test_deployment_env_does_not_evaluate_shell_substitution(tmp_path: Path) -> None:
    marker = tmp_path / "must-not-exist"
    env_file = tmp_path / "deployment.env"
    env_file.write_text(
        f"CADDY_DATA_PATH=$(touch {marker})\n",
        encoding="utf-8",
    )
    with pytest.raises(ComposeRenderError, match="invalid environment assignment"):
        read_strict_env(env_file, {"CADDY_DATA_PATH"})
    assert not marker.exists()


def test_active_revision_cannot_escape_managed_state(tmp_path: Path) -> None:
    hosting_dir = tmp_path / "hosting"
    hosting_dir.mkdir()
    (hosting_dir / "current.json").write_text(
        json.dumps({"revision": str(tmp_path.parent)}), encoding="utf-8"
    )
    with pytest.raises(typer.BadParameter, match="outside the managed state"):
        _active_hosting_revision(tmp_path)
