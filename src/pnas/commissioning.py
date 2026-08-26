from __future__ import annotations

import re
import shlex
import shutil
import stat
import sys
from ipaddress import IPv4Address, IPv4Network
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import Field, field_validator, model_validator

from pnas.config import PNASConfig
from pnas.models import StrictModel


class CommissioningValues(StrictModel):
    admin_username: str = Field(pattern=r"^[a-z_][a-z0-9_-]{0,31}$")
    management_ip: IPv4Address
    service_ip: IPv4Address
    lan_prefix: int = Field(default=24, ge=8, le=30)
    owner_email: str = Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    boot_serial: str
    apps_serial: str
    recovery_serial: str
    main_serials: tuple[str, str, str, str]
    archive_serials: tuple[str, str, str, str]
    nas_repo_path: Path = Path("/mnt/apps/pnas/repo")
    nas_state_path: Path = Path("/mnt/app-recovery/hosting-revisions/pnas-state")

    @field_validator(
        "boot_serial", "apps_serial", "recovery_serial", "main_serials", "archive_serials"
    )
    @classmethod
    def reject_placeholders(cls, value: str | tuple[str, ...]) -> str | tuple[str, ...]:
        serials = (value,) if isinstance(value, str) else value
        for serial in serials:
            candidate = serial.strip()
            if not candidate or re.fullmatch(
                r"(?:BOOTSSD|APPSSD|APPRECOVERY|DATA4T|ARCHIVE)[0-9]+", candidate.upper()
            ):
                raise ValueError("replace every example serial with the label from the device")
        return value.strip() if isinstance(value, str) else tuple(item.strip() for item in value)

    @model_validator(mode="after")
    def validate_boundaries(self) -> CommissioningValues:
        addresses = (self.management_ip, self.service_ip)
        if any(
            not address.is_private
            or address.is_loopback
            or address.is_link_local
            or address.is_multicast
            or address.is_unspecified
            for address in addresses
        ):
            raise ValueError("management and service addresses must be private IPv4 addresses")
        if self.management_ip == self.service_ip:
            raise ValueError("management and service addresses must be different")
        lan = IPv4Network(f"{self.management_ip}/{self.lan_prefix}", strict=False)
        if self.service_ip not in lan:
            raise ValueError("management and service addresses must be in the same LAN prefix")
        all_serials = (
            self.boot_serial,
            self.apps_serial,
            self.recovery_serial,
            *self.main_serials,
            *self.archive_serials,
        )
        if len(set(all_serials)) != len(all_serials):
            raise ValueError("every physical device must have a unique serial")
        for path in (self.nas_repo_path, self.nas_state_path):
            if not path.is_absolute() or not path.is_relative_to("/mnt"):
                raise ValueError("NAS repository and state paths must be absolute paths under /mnt")
        return self


class CommissioningCheck(StrictModel):
    name: str
    passed: bool
    detail: str


def parse_four_serials(value: str, *, label: str) -> tuple[str, str, str, str]:
    serials = tuple(item.strip() for item in value.split(",") if item.strip())
    if len(serials) != 4:
        raise ValueError(f"{label} requires exactly four comma-separated serials")
    return serials


def build_configs(
    template: Path, values: CommissioningValues
) -> tuple[dict[str, Any], dict[str, Any]]:
    raw = yaml.safe_load(template.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("configuration template root must be a mapping")
    raw["truenas"].update(
        {
            "url": f"https://{values.management_ip}",
            "verify_tls": True,
            "username": "pnas-observer",
            "credential_file": "/run/secrets/truenas_api_token",
            "adapter": "real",
        }
    )
    raw["storage"]["application_device_serials"] = [values.apps_serial, values.recovery_serial]
    raw["storage"]["boot_device_serials"] = [values.boot_serial]
    raw["hosting"]["private_addresses"]["management_lan"] = str(values.management_ip)
    raw["hosting"]["private_addresses"]["lan"] = str(values.service_ip)
    raw["hosting"]["certificates"]["email"] = values.owner_email
    PNASConfig.model_validate(raw)
    production = raw
    rehearsal = yaml.safe_load(yaml.safe_dump(raw))
    rehearsal["truenas"].update(
        {
            "username": "pnas-rehearsal",
            "credential_file": "/dev/null",
            "adapter": "mock",
        }
    )
    PNASConfig.model_validate(rehearsal)
    return production, rehearsal


def load_commissioning_values(path: Path) -> CommissioningValues:
    return CommissioningValues.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))


def check_commissioning(
    *,
    stage: Literal["workstation", "deployment"],
    project_root: Path,
    config_path: Path,
    values_path: Path,
) -> list[CommissioningCheck]:
    checks: list[CommissioningCheck] = []

    def add(name: str, passed: bool, detail: str) -> None:
        checks.append(CommissioningCheck(name=name, passed=passed, detail=detail))

    try:
        values = load_commissioning_values(values_path)
        add("commissioning-values", True, "values are complete and internally consistent")
    except Exception as exc:
        add("commissioning-values", False, f"values are invalid ({type(exc).__name__})")
        return checks
    try:
        load = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        PNASConfig.model_validate(load)
        add("pnas-config", True, "production configuration validates")
    except Exception as exc:
        add("pnas-config", False, f"production configuration is invalid ({type(exc).__name__})")
    required_repo_files = (
        "pyproject.toml",
        "compose/nextcloud/compose.yaml",
        "compose/immich/compose.yaml",
        "compose/manager/compose.yaml",
        "compose/dns/compose.yaml",
        "compose/proxy/compose.yaml",
    )
    missing_repo = [name for name in required_repo_files if not (project_root / name).is_file()]
    add(
        "repository-layout",
        not missing_repo,
        (
            "required repository files exist"
            if not missing_repo
            else f"missing: {', '.join(missing_repo)}"
        ),
    )
    add(
        "python-version",
        sys.version_info >= (3, 12),
        f"running Python {sys.version_info.major}.{sys.version_info.minor}; 3.12+ is required",
    )
    for command in ("git", "curl", "ssh", "rsync"):
        available = shutil.which(command) is not None
        availability = "available" if available else "missing"
        add(f"command-{command}", available, f"{command} is {availability}")
    if stage == "deployment":
        expected_env = tuple(
            project_root / "compose" / name / ".env"
            for name in ("nextcloud", "immich", "manager", "proxy")
        )
        missing_env = [str(path) for path in expected_env if not path.is_file()]
        add(
            "application-env-files",
            not missing_env,
            "all application environment files exist"
            if not missing_env
            else f"missing: {', '.join(missing_env)}",
        )
        secret_paths = (
            Path("/mnt/apps/secrets/nextcloud-db-password"),
            Path("/mnt/apps/secrets/nextcloud-redis-password"),
            Path("/mnt/apps/secrets/immich-db-password"),
            Path("/mnt/apps/secrets/cloudflare-dns-token"),
            Path("/mnt/apps/secrets/truenas-readonly-api-token"),
            Path("/mnt/apps/secrets/truenas-deployer-api-token"),
            Path("/mnt/apps/secrets/manager/manager-password-hash"),
            Path("/mnt/apps/secrets/manager/manager-session-key"),
            Path("/mnt/apps/secrets/manager/manager-totp-secret"),
        )
        invalid_secrets = [
            str(path)
            for path in secret_paths
            if not path.is_file() or stat.S_IMODE(path.stat().st_mode) != 0o600
        ]
        add(
            "secret-files",
            not invalid_secrets,
            "all required secret files exist with mode 0600"
            if not invalid_secrets
            else f"missing or wrong mode: {', '.join(invalid_secrets)}",
        )
        add(
            "nas-repository-path",
            values.nas_repo_path.resolve() == project_root.resolve(),
            f"expected deployment repository: {values.nas_repo_path}",
        )
    return checks


def render_shell_values(values: CommissioningValues) -> str:
    """Render validated, non-secret commissioning values as safely quoted shell assignments."""
    assignments = {
        "PNAS_ADMIN_USER": values.admin_username,
        "PNAS_MANAGEMENT_IP": str(values.management_ip),
        "PNAS_SERVICE_IP": str(values.service_ip),
        "PNAS_LAN_PREFIX": str(values.lan_prefix),
        "PNAS_OWNER_EMAIL": values.owner_email,
        "PNAS_NAS_REPO_PATH": str(values.nas_repo_path),
        "PNAS_NAS_STATE_PATH": str(values.nas_state_path),
        "PNAS_BOOT_SERIAL": values.boot_serial,
        "PNAS_APPS_SERIAL": values.apps_serial,
        "PNAS_RECOVERY_SERIAL": values.recovery_serial,
    }
    for index, serial in enumerate(values.main_serials, start=1):
        assignments[f"PNAS_MAIN_SERIAL_{index}"] = serial
    for index, serial in enumerate(values.archive_serials, start=1):
        assignments[f"PNAS_ARCHIVE_SERIAL_{index}"] = serial
    return "\n".join(f"{key}={shlex.quote(value)}" for key, value in assignments.items()) + "\n"
