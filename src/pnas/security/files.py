from pathlib import Path


def require_secret_file(path: Path) -> Path:
    """Require a regular secret file that is inaccessible to group and other users."""
    if not path.is_file():
        raise FileNotFoundError(f"secret file does not exist: {path}")
    if path.stat().st_mode & 0o077:
        raise PermissionError(f"secret file must have mode 0600: {path}")
    return path
