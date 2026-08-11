from __future__ import annotations

from ipaddress import IPv4Address, IPv6Address, ip_address, ip_network
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

import yaml
from pydantic import AnyHttpUrl, Field, model_validator

from pnas.models import StrictModel


class SystemConfig(StrictModel):
    name: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{1,62}$")
    environment: Literal["home", "lab"] = "home"
    timezone: str


class TrueNASConfig(StrictModel):
    url: AnyHttpUrl
    verify_tls: bool = True
    api_version: str = "auto"
    username: str
    credential_file: Path
    adapter: Literal["mock", "real"] = "mock"

    @model_validator(mode="after")
    def require_https_for_real(self) -> TrueNASConfig:
        if self.adapter == "real" and self.url.scheme != "https":
            raise ValueError("real TrueNAS connections require HTTPS")
        return self


class StorageConfig(StrictModel):
    chassis_bays: int = Field(ge=8)
    deployment_phase: Literal[1, 2]
    expected_drive_count: int = Field(ge=4, le=8)
    drive_capacity_tb: float | None = Field(default=None, gt=0)
    pool_name: str = Field(pattern=r"^[A-Za-z][A-Za-z0-9_.:-]*$")
    vdev_layout: Literal["raidz2"] = "raidz2"
    vdev_width: Literal[4] = 4
    expected_final_vdev_count: Literal[2] = 2
    maximum_utilization_percent: int = Field(default=80, ge=50, le=90)
    warning_utilization_percent: int = Field(default=70, ge=40, le=85)
    require_cmr: bool = True
    require_smart_extended_test: bool = True
    require_serial_confirmation: bool = True
    allow_asymmetric_vdev: bool = False
    application_device_serials: tuple[str, ...]
    boot_device_serials: tuple[str, ...]

    @model_validator(mode="after")
    def validate_thresholds(self) -> StorageConfig:
        if self.warning_utilization_percent >= self.maximum_utilization_percent:
            raise ValueError("warning utilization must be below maximum utilization")
        expected = 4 if self.deployment_phase == 1 else 8
        if self.expected_drive_count != expected:
            raise ValueError(f"phase {self.deployment_phase} requires {expected} expected drives")
        return self


class EnabledConfig(StrictModel):
    enabled: bool = True


class ApplicationsConfig(StrictModel):
    nextcloud: EnabledConfig
    immich: EnabledConfig
    tailscale: EnabledConfig
    reverse_proxy: EnabledConfig


class TailscaleRemoteAccessConfig(StrictModel):
    """Fail-closed settings for the NAS tailnet identity.

    Enrollment credentials are intentionally absent. A short-lived auth key is
    supplied directly to the supported TrueNAS App during commissioning and is
    removed after the persistent node state has been created.
    """

    enabled: Literal[True] = True
    deployment: Literal["truenas-app"] = "truenas-app"
    hostname: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{1,62}$")
    device_tag: str = Field(pattern=r"^tag:[a-z0-9][a-z0-9-]{1,62}$")
    private_dns_suffix: str
    host_network: Literal[True] = True
    userspace_networking: Literal[False] = False
    accept_dns: Literal[False] = False
    advertise_exit_node: Literal[False] = False
    funnel: Literal[False] = False
    public_ingress: Literal[False] = False
    router_port_forwarding: Literal[False] = False
    require_device_approval: Literal[True] = True

    @model_validator(mode="after")
    def normalize_dns_suffix(self) -> TailscaleRemoteAccessConfig:
        object.__setattr__(self, "private_dns_suffix", normalize_hostname(self.private_dns_suffix))
        return self


class RemoteAccessConfig(StrictModel):
    tailscale: TailscaleRemoteAccessConfig


class RetentionConfig(StrictModel):
    daily: int = Field(ge=1)
    weekly: int = Field(ge=1)
    monthly: int = Field(ge=1)


class BackupConfig(StrictModel):
    provider: Literal["backblaze-b2", "external-usb"]
    critical_data_target_tb: float = Field(gt=0)
    retention: RetentionConfig


def normalize_hostname(value: str) -> str:
    candidate = value.strip().lower().rstrip(".")
    if "://" in candidate:
        parsed = urlsplit(candidate)
        if parsed.scheme != "https" or not parsed.hostname:
            raise ValueError("service URLs must use HTTPS")
        try:
            port = parsed.port
        except ValueError as exc:
            raise ValueError("service URL contains an invalid port") from exc
        if parsed.path not in ("", "/") or parsed.query or parsed.fragment or port:
            raise ValueError("service URLs must contain only an HTTPS hostname")
        candidate = parsed.hostname.rstrip(".")
    if "*" in candidate or len(candidate) > 253:
        raise ValueError("wildcard or oversized hostnames are not allowed")
    labels = candidate.split(".")
    if len(labels) < 2 or any(
        not label
        or len(label) > 63
        or label.startswith("-")
        or label.endswith("-")
        or not label.replace("-", "").isalnum()
        for label in labels
    ):
        raise ValueError("invalid DNS hostname")
    return candidate.encode("idna").decode("ascii")


class HostingServicesConfig(StrictModel):
    nextcloud: str
    immich: str
    manager: str

    @model_validator(mode="before")
    @classmethod
    def normalize_services(cls, value: object) -> object:
        if isinstance(value, dict):
            return {key: normalize_hostname(str(host)) for key, host in value.items()}
        return value


class PrivateAddressesConfig(StrictModel):
    management_lan: IPv4Address | IPv6Address | None = None
    lan: IPv4Address | IPv6Address
    tailscale: IPv4Address | IPv6Address | None = None

    @model_validator(mode="after")
    def require_private_addresses(self) -> PrivateAddressesConfig:
        private_networks = (
            ip_network("10.0.0.0/8"),
            ip_network("172.16.0.0/12"),
            ip_network("192.168.0.0/16"),
            ip_network("fc00::/7"),
        )
        shared_tailnet = ip_network("100.64.0.0/10")
        if not any(self.lan in network for network in private_networks):
            raise ValueError("LAN address must be RFC1918 IPv4 or unique-local IPv6")
        if self.management_lan is not None:
            if not any(self.management_lan in network for network in private_networks):
                raise ValueError("management LAN address must be RFC1918 IPv4 or unique-local IPv6")
            if self.management_lan == self.lan:
                raise ValueError("management and service LAN addresses must be different")
        if self.tailscale is not None and not (
            any(self.tailscale in network for network in private_networks)
            or self.tailscale in shared_tailnet
        ):
            raise ValueError("Tailscale address must be private or in 100.64.0.0/10")
        return self


class HostingDNSConfig(StrictModel):
    provider: Literal["cloudflare", "rfc2136", "manual"]
    zone: str
    credential_file: Path | None = None
    manage_public_service_records: Literal[False] = False
    rfc2136_server: str | None = None
    rfc2136_key_name: str | None = None
    rfc2136_key_algorithm: Literal["hmac-sha256", "hmac-sha384", "hmac-sha512"] = "hmac-sha256"

    @model_validator(mode="after")
    def validate_provider_details(self) -> HostingDNSConfig:
        object.__setattr__(self, "zone", normalize_hostname(self.zone))
        if self.provider in {"cloudflare", "rfc2136"} and self.credential_file is None:
            raise ValueError(f"{self.provider} requires a credential file")
        if self.credential_file is not None and not self.credential_file.is_absolute():
            raise ValueError("DNS credential file path must be absolute")
        if self.provider == "manual" and self.credential_file is not None:
            raise ValueError("manual DNS must not configure a credential file")
        if self.provider == "rfc2136" and not (self.rfc2136_server and self.rfc2136_key_name):
            raise ValueError("RFC2136 requires server and key name")
        if self.provider == "rfc2136":
            assert self.rfc2136_server is not None
            assert self.rfc2136_key_name is not None
            parsed = urlsplit(f"//{self.rfc2136_server}")
            try:
                port = parsed.port
            except ValueError as exc:
                raise ValueError("RFC2136 server contains an invalid port") from exc
            if (
                not parsed.hostname
                or port is None
                or parsed.username
                or parsed.password
                or parsed.path
                or parsed.query
                or parsed.fragment
            ):
                raise ValueError("RFC2136 server must be a hostname or IP plus port")
            object.__setattr__(self, "rfc2136_key_name", normalize_hostname(self.rfc2136_key_name))
        return self


class HostingCertificatesConfig(StrictModel):
    issuer: Literal["letsencrypt"] = "letsencrypt"
    email: str = Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    environment: Literal["staging", "production"] = "staging"


class HostingConfig(StrictModel):
    enabled: bool = False
    exposure: Literal["private"] = "private"
    base_domain: str
    services: HostingServicesConfig
    private_addresses: PrivateAddressesConfig
    dns: HostingDNSConfig
    certificates: HostingCertificatesConfig

    @property
    def hostnames(self) -> tuple[str, str, str]:
        return (self.services.nextcloud, self.services.immich, self.services.manager)

    @model_validator(mode="after")
    def validate_domain_boundaries(self) -> HostingConfig:
        base = normalize_hostname(self.base_domain)
        object.__setattr__(self, "base_domain", base)
        if not (base == self.dns.zone or base.endswith(f".{self.dns.zone}")):
            raise ValueError("base domain must be contained by the configured DNS zone")
        hosts = self.hostnames
        if len(set(hosts)) != len(hosts):
            raise ValueError("service hostnames must be unique")
        if any(not host.endswith(f".{base}") for host in hosts):
            raise ValueError("every service hostname must be below the base domain")
        if self.enabled and self.private_addresses.tailscale is None:
            raise ValueError("enabled private hosting requires a Tailscale address")
        try:
            ip_address(base)
        except ValueError:
            return self
        raise ValueError("base domain must not be an IP address")


class PNASConfig(StrictModel):
    system: SystemConfig
    truenas: TrueNASConfig
    storage: StorageConfig
    applications: ApplicationsConfig
    remote_access: RemoteAccessConfig
    backup: BackupConfig
    hosting: HostingConfig | None = None

    @model_validator(mode="after")
    def require_private_tailnet_hosting(self) -> PNASConfig:
        if self.hosting is None or not self.hosting.enabled:
            return self
        if not self.applications.tailscale.enabled:
            raise ValueError("private hosting requires the Tailscale application")
        if self.hosting.private_addresses.tailscale is None:
            raise ValueError("private hosting requires a Tailscale address")
        if self.hosting.base_domain != self.remote_access.tailscale.private_dns_suffix:
            raise ValueError("hosting base domain must match the Tailscale private DNS suffix")
        return self


def load_config(path: Path) -> PNASConfig:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("configuration root must be a mapping")
    return PNASConfig.model_validate(raw)
