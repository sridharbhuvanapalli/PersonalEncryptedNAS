from pathlib import Path

import pytest

from pnas.audit import AuditLog
from pnas.backups.runner import CommandFailed, CommandResult
from pnas.backups.workflow import BackupWorkflow, DatabaseTarget, ResticTarget


class FakeRunner:
    def __init__(self, *, fail: bool = False):
        self.fail = fail
        self.calls: list[tuple[list[str], dict[str, str]]] = []

    def run(self, command, *, env=None, timeout=3600):  # type: ignore[no-untyped-def]
        del timeout
        self.calls.append((list(command), dict(env or {})))
        if self.fail:
            raise CommandFailed("failed")
        return CommandResult(0, "-- PostgreSQL database dump\nSELECT 1;\n", "")


def secret(tmp_path: Path, name: str) -> Path:
    path = tmp_path / name
    path.write_text("not-a-real-secret\n", encoding="utf-8")
    path.chmod(0o600)
    return path


def test_database_dump_is_validated_and_password_is_not_in_command(tmp_path: Path) -> None:
    runner = FakeRunner()
    alerts: list[tuple[str, str]] = []
    workflow = BackupWorkflow(
        runner=runner,
        audit=AuditLog(tmp_path / "audit.jsonl"),
        alert=lambda level, message: alerts.append((level, message)),
    )
    output = workflow.dump_database(
        DatabaseTarget("nextcloud", "db", "nextcloud", "nextcloud", secret(tmp_path, "pgpass")),
        tmp_path / "dumps",
    )
    assert output.exists()
    assert "not-a-real-secret" not in " ".join(runner.calls[0][0])
    assert alerts == []


def test_failed_backup_generates_critical_alert(tmp_path: Path) -> None:
    runner = FakeRunner(fail=True)
    alerts: list[tuple[str, str]] = []
    workflow = BackupWorkflow(
        runner=runner,
        audit=AuditLog(tmp_path / "audit.jsonl"),
        alert=lambda level, message: alerts.append((level, message)),
    )
    target = ResticTarget("b2:test", secret(tmp_path, "restic-password"), (tmp_path,))
    with pytest.raises(CommandFailed):
        workflow.restic_backup(target)
    assert alerts == [("critical", "offsite backup failed")]


def test_restore_selected_uses_exact_include_and_target(tmp_path: Path) -> None:
    runner = FakeRunner()
    workflow = BackupWorkflow(
        runner=runner, audit=AuditLog(tmp_path / "audit.jsonl"), alert=lambda *_: None
    )
    target = ResticTarget("/backup", secret(tmp_path, "restic-password"), (tmp_path,))
    workflow.restore_selected(
        target, snapshot="latest", include="/photos/example.jpg", destination=tmp_path / "restore"
    )
    command = runner.calls[0][0]
    assert command[-4:] == [
        "--include",
        "/photos/example.jpg",
        "--target",
        str(tmp_path / "restore"),
    ]
