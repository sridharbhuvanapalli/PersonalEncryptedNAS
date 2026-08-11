from __future__ import annotations

import os
import subprocess
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class CommandResult:
    returncode: int
    stdout: str
    stderr: str


class CommandFailed(RuntimeError):
    pass


class SubprocessRunner:
    def run(
        self,
        command: Sequence[str],
        *,
        env: Mapping[str, str] | None = None,
        timeout: int = 3600,
    ) -> CommandResult:
        safe_env = os.environ.copy()
        if env:
            safe_env.update(env)
        completed = subprocess.run(  # noqa: S603 - callers construct fixed argv, never a shell
            list(command),
            env=safe_env,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        result = CommandResult(completed.returncode, completed.stdout, completed.stderr)
        if result.returncode:
            raise CommandFailed(f"command failed with exit code {result.returncode}")
        return result


def require_secret_file(path: Path) -> Path:
    if not path.is_file():
        raise FileNotFoundError(f"secret file does not exist: {path}")
    if path.stat().st_mode & 0o077:
        raise PermissionError(f"secret file must have mode 0600: {path}")
    return path
