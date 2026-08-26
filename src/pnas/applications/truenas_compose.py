from __future__ import annotations

import re
import shlex
from pathlib import Path
from typing import Any

import yaml

_ENV_KEY = re.compile(r"^[A-Z][A-Z0-9_]*$")
_INTERPOLATION = re.compile(r"\$\{([A-Z][A-Z0-9_]*)(?:(:[-?])(.*?))?\}")

PROJECT_ENV_KEYS: dict[str, set[str]] = {
    "nextcloud": {
        "NEXTCLOUD_CONFIG_PATH",
        "NEXTCLOUD_APPS_PATH",
        "NEXTCLOUD_DB_PATH",
        "NEXTCLOUD_DATA_PATH",
        "NEXTCLOUD_DB_PASSWORD_FILE",
        "NEXTCLOUD_REDIS_PASSWORD_FILE",
    },
    "immich": {
        "IMMICH_LIBRARY_PATH",
        "IMMICH_DB_PATH",
        "IMMICH_ML_CACHE_PATH",
        "IMMICH_DB_PASSWORD_FILE",
    },
    "manager": {
        "MANAGER_STATE_PATH",
        "MANAGER_PASSWORD_HASH_FILE",
        "MANAGER_SESSION_KEY_FILE",
        "MANAGER_TOTP_SECRET_FILE",
        "TRUENAS_API_TOKEN_FILE",
        "PNAS_CONFIG_FILE",
        "PNAS_MANAGER_ALLOWED_NETWORKS",
        "PNAS_MANAGER_TRUSTED_PROXY_NETWORKS",
        "PNAS_MANAGER_HEALTH_MODE",
        "TAILSCALE_STATUS_FILE",
    },
    "proxy": {
        "CADDY_DATA_PATH",
        "CADDY_CONFIG_PATH",
    },
}

DEPLOYMENT_ENV_KEYS = {
    "PNAS_SERVICE_LAN_BIND_IP",
    "PNAS_TAILSCALE_BIND_IP",
    "CADDYFILE_PATH",
    "COREDNS_LAN_COREFILE",
    "COREDNS_TAILSCALE_COREFILE",
    "COREDNS_LAN_ZONE",
    "COREDNS_TAILSCALE_ZONE",
    "PNAS_DNS_PROVIDER",
    "DNS_PROVIDER_CREDENTIAL_FILE",
}


class ComposeRenderError(RuntimeError):
    pass


def read_strict_env(
    path: Path, allowed_keys: set[str], *, required_keys: set[str] | None = None
) -> dict[str, str]:
    """Parse simple KEY=VALUE assignments without evaluating shell syntax."""
    if not path.is_file():
        raise ComposeRenderError(f"environment file does not exist: {path}")
    values: dict[str, str] = {}
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        try:
            fields = shlex.split(stripped, comments=True, posix=True)
        except ValueError as exc:
            raise ComposeRenderError(f"invalid environment syntax at {path}:{line_number}") from exc
        if len(fields) != 1 or "=" not in fields[0]:
            raise ComposeRenderError(f"invalid environment assignment at {path}:{line_number}")
        key, value = fields[0].split("=", 1)
        if not _ENV_KEY.fullmatch(key) or key not in allowed_keys:
            raise ComposeRenderError(f"environment key is not allowed at {path}:{line_number}")
        values[key] = value
    missing = (required_keys if required_keys is not None else allowed_keys) - values.keys()
    if missing:
        raise ComposeRenderError(
            f"environment file is missing required keys: {', '.join(sorted(missing))}"
        )
    return values


def _interpolate_string(value: str, environment: dict[str, str]) -> str:
    def replace(match: re.Match[str]) -> str:
        key, operator, fallback = match.groups()
        configured = environment.get(key)
        if configured:
            return configured
        if operator == ":-":
            return fallback or ""
        if operator == ":?":
            raise ComposeRenderError(f"required Compose value is missing: {key}")
        return ""

    return _INTERPOLATION.sub(replace, value)


def _interpolate(value: Any, environment: dict[str, str]) -> Any:
    if isinstance(value, str):
        return _interpolate_string(value, environment)
    if isinstance(value, list):
        return [_interpolate(item, environment) for item in value]
    if isinstance(value, dict):
        return {key: _interpolate(item, environment) for key, item in value.items()}
    return value


def _load_project(project_root: Path, name: str, environment: dict[str, str]) -> dict[str, Any]:
    source = project_root / "compose" / name / "compose.yaml"
    raw = yaml.safe_load(source.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or not isinstance(raw.get("services"), dict):
        raise ComposeRenderError(f"invalid Compose project: {source}")
    rendered = _interpolate(raw, environment)
    if not isinstance(rendered, dict):
        raise ComposeRenderError(f"invalid rendered Compose project: {source}")
    return rendered


def _rename_networks(service: dict[str, Any], old: str, new: str) -> None:
    networks = service.get("networks")
    if isinstance(networks, list):
        service["networks"] = [new if item == old else item for item in networks]
    elif isinstance(networks, dict) and old in networks:
        networks[new] = networks.pop(old)


def render_truenas_custom_app(
    *, project_root: Path, revision: Path, env_dir: Path | None = None
) -> str:
    """Render all private services as one TrueNAS-managed Custom App."""
    root = project_root.resolve()
    environment: dict[str, str] = {}
    environment_directory = (env_dir or root / "compose").resolve()
    for project, keys in PROJECT_ENV_KEYS.items():
        env_path = environment_directory / project / ".env"
        environment.update(read_strict_env(env_path, keys))
    environment.update(
        read_strict_env(revision / "deployment.env", DEPLOYMENT_ENV_KEYS)
    )

    combined: dict[str, Any] = {"services": {}, "networks": {}, "secrets": {}}
    projects = ("nextcloud", "immich", "manager", "dns", "proxy")
    for project in projects:
        rendered = _load_project(root, project, environment)
        services = rendered["services"]
        if project == "nextcloud":
            for service in services.values():
                _rename_networks(service, "backend", "nextcloud_backend")
        elif project == "immich":
            for service in services.values():
                _rename_networks(service, "backend", "immich_backend")
        overlap = set(combined["services"]) & set(services)
        if overlap:
            raise ComposeRenderError(f"duplicate service names: {', '.join(sorted(overlap))}")
        combined["services"].update(services)
        secrets = rendered.get("secrets", {})
        if isinstance(secrets, dict):
            combined["secrets"].update(secrets)

    combined["services"]["caddy"]["build"]["context"] = str(root / "compose" / "proxy")
    combined["services"]["pnas-manager"]["build"]["context"] = str(root)
    combined["networks"] = {
        "nextcloud_backend": {"internal": True},
        "immich_backend": {"internal": True},
        "pnas_private": {
            "name": "pnas_private",
            "driver": "bridge",
            "ipam": {"config": [{"subnet": "172.30.0.0/24"}]},
        },
        "pnas_management": {
            "name": "pnas_management",
            "driver": "bridge",
            "ipam": {"config": [{"subnet": "172.31.0.0/28"}]},
        },
    }
    if not combined["secrets"]:
        combined.pop("secrets")
    output = yaml.safe_dump(combined, sort_keys=False)
    if "${" in output:
        raise ComposeRenderError("rendered Custom App contains unresolved variables")
    return output
