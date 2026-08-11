from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Protocol

from pnas.backups.runner import CommandResult, require_secret_file


class Runner(Protocol):
    def run(
        self,
        command: Sequence[str],
        *,
        env: Mapping[str, str] | None = None,
        timeout: int = 3600,
    ) -> CommandResult: ...


def encrypt_recovery_bundle(
    runner: Runner, *, archive: Path, recipients_file: Path, output: Path
) -> None:
    if not archive.is_file():
        raise FileNotFoundError(archive)
    require_secret_file(recipients_file)
    if output.exists():
        raise FileExistsError(output)
    runner.run(
        ["age", "--recipients-file", str(recipients_file), "--output", str(output), str(archive)]
    )
