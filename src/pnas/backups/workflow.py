from __future__ import annotations

import gzip
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from pnas.audit import AuditLog
from pnas.backups.runner import CommandResult, require_secret_file


class Runner(Protocol):
    def run(
        self,
        command: Sequence[str],
        *,
        env: Mapping[str, str] | None = None,
        timeout: int = 3600,
    ) -> CommandResult: ...


@dataclass(frozen=True)
class DatabaseTarget:
    name: str
    host: str
    database: str
    username: str
    pgpass_file: Path


@dataclass(frozen=True)
class ResticTarget:
    repository: str
    password_file: Path
    include_paths: tuple[Path, ...]


class BackupWorkflow:
    def __init__(
        self,
        *,
        runner: Runner,
        audit: AuditLog,
        alert: Callable[[str, str], None],
    ):
        self.runner = runner
        self.audit = audit
        self.alert = alert

    def dump_database(self, target: DatabaseTarget, output_dir: Path) -> Path:
        require_secret_file(target.pgpass_file)
        output_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        output = output_dir / f"{target.name}-{stamp}.sql.gz"
        try:
            result = self.runner.run(
                [
                    "pg_dump",
                    "--host",
                    target.host,
                    "--username",
                    target.username,
                    "--dbname",
                    target.database,
                    "--format=plain",
                    "--no-password",
                ],
                env={"PGPASSFILE": str(target.pgpass_file)},
            )
            if not result.stdout.strip():
                raise ValueError("pg_dump returned empty output")
            with gzip.open(output, "wt", encoding="utf-8") as handle:
                handle.write(result.stdout)
            self.validate_dump(output)
        except Exception as exc:
            self.alert("critical", f"database backup failed for {target.name}")
            self.audit.append(
                "backup.database",
                actor="backup-service",
                outcome="failure",
                details={"database": target.name, "error_type": type(exc).__name__},
            )
            raise
        self.audit.append(
            "backup.database",
            actor="backup-service",
            outcome="success",
            details={"database": target.name, "output": str(output)},
        )
        return output

    @staticmethod
    def validate_dump(path: Path) -> None:
        with gzip.open(path, "rt", encoding="utf-8") as handle:
            prefix = handle.read(4096)
        if not prefix.strip() or "PostgreSQL database dump" not in prefix:
            raise ValueError("database dump did not contain a PostgreSQL header")

    def restic_backup(self, target: ResticTarget) -> None:
        require_secret_file(target.password_file)
        command = ["restic", "-r", target.repository, "backup"]
        command.extend(str(path) for path in target.include_paths)
        env = {"RESTIC_PASSWORD_FILE": str(target.password_file)}
        try:
            self.runner.run(command, env=env, timeout=86_400)
        except Exception as exc:
            self.alert("critical", "offsite backup failed")
            self.audit.append(
                "backup.restic",
                actor="backup-service",
                outcome="failure",
                details={"repository": target.repository, "error_type": type(exc).__name__},
            )
            raise
        self.audit.append(
            "backup.restic",
            actor="backup-service",
            outcome="success",
            details={"repository": target.repository},
        )

    def restic_check(self, target: ResticTarget) -> None:
        require_secret_file(target.password_file)
        self.runner.run(
            ["restic", "-r", target.repository, "check", "--read-data-subset=5%"],
            env={"RESTIC_PASSWORD_FILE": str(target.password_file)},
            timeout=86_400,
        )

    def restore_selected(
        self, target: ResticTarget, *, snapshot: str, include: str, destination: Path
    ) -> None:
        require_secret_file(target.password_file)
        self.runner.run(
            [
                "restic",
                "-r",
                target.repository,
                "restore",
                snapshot,
                "--include",
                include,
                "--target",
                str(destination),
            ],
            env={"RESTIC_PASSWORD_FILE": str(target.password_file)},
            timeout=86_400,
        )
        self.audit.append(
            "restore.test",
            actor="backup-service",
            outcome="success",
            details={"snapshot": snapshot, "include": include},
        )

    def forget(self, target: ResticTarget) -> None:
        require_secret_file(target.password_file)
        self.runner.run(
            [
                "restic",
                "-r",
                target.repository,
                "forget",
                "--keep-daily",
                "30",
                "--keep-weekly",
                "12",
                "--keep-monthly",
                "12",
                "--prune",
            ],
            env={"RESTIC_PASSWORD_FILE": str(target.password_file)},
            timeout=86_400,
        )
