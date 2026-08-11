from __future__ import annotations

import re
import secrets
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

import httpx

from pnas.backups.runner import require_secret_file
from pnas.config import HostingDNSConfig


class ProviderError(RuntimeError):
    pass


class DNSProvider(Protocol):
    async def verify(self) -> dict[str, str | bool]: ...

    async def write_test(self) -> dict[str, str | bool]: ...


def read_cloudflare_token(path: Path) -> str:
    token = require_secret_file(path).read_text(encoding="utf-8").strip()
    if not token:
        raise ProviderError("Cloudflare token file is empty")
    if re.fullmatch(r"[a-fA-F0-9]{37}", token):
        raise ProviderError("Cloudflare Global API Keys are prohibited; use a scoped API token")
    if any(character.isspace() for character in token):
        raise ProviderError("Cloudflare API token contains whitespace")
    return token


class CloudflareProvider:
    def __init__(self, config: HostingDNSConfig, *, client: httpx.AsyncClient | None = None):
        if config.provider != "cloudflare" or config.credential_file is None:
            raise ValueError("Cloudflare provider requires Cloudflare DNS configuration")
        self.config = config
        self.token = read_cloudflare_token(config.credential_file)
        self.client = client or httpx.AsyncClient(
            base_url="https://api.cloudflare.com/client/v4",
            timeout=20,
            headers={"Authorization": f"Bearer {self.token}"},
        )
        self._owns_client = client is None

    async def close(self) -> None:
        if self._owns_client:
            await self.client.aclose()

    @staticmethod
    def _result(response: httpx.Response) -> Any:
        try:
            payload = response.json()
        except ValueError as exc:
            raise ProviderError("Cloudflare returned a non-JSON response") from exc
        if response.is_error or payload.get("success") is not True:
            raise ProviderError(f"Cloudflare request failed with HTTP {response.status_code}")
        return payload.get("result")

    async def _zone_id(self) -> str:
        response = await self.client.get("/zones", params={"name": self.config.zone})
        result = self._result(response)
        if not isinstance(result, list) or len(result) != 1:
            raise ProviderError("Cloudflare token must see exactly one matching DNS zone")
        zone = result[0]
        if zone.get("name", "").rstrip(".").lower() != self.config.zone:
            raise ProviderError("Cloudflare returned a zone outside the configured boundary")
        return str(zone["id"])

    async def verify(self) -> dict[str, str | bool]:
        token = self._result(await self.client.get("/user/tokens/verify"))
        if not isinstance(token, dict) or token.get("status") != "active":
            raise ProviderError("Cloudflare API token is not active")
        await self._zone_id()
        return {
            "provider": "cloudflare",
            "token_active": True,
            "zone_visible": True,
            "write_test_performed": False,
        }

    async def write_test(self) -> dict[str, str | bool]:
        zone_id = await self._zone_id()
        name = f"_pnas-validation.{self.config.zone}"
        content = f"pnas-{secrets.token_urlsafe(18)}"
        record_id: str | None = None
        verified = False
        try:
            created = self._result(
                await self.client.post(
                    f"/zones/{zone_id}/dns_records",
                    json={"type": "TXT", "name": name, "content": content, "ttl": 60},
                )
            )
            record_id = str(created["id"])
            queried = self._result(
                await self.client.get(
                    f"/zones/{zone_id}/dns_records",
                    params={"type": "TXT", "name": name},
                )
            )
            verified = any(record.get("content") == content for record in queried)
            if not verified:
                raise ProviderError("temporary Cloudflare TXT record could not be verified")
        finally:
            if record_id is not None:
                self._result(await self.client.delete(f"/zones/{zone_id}/dns_records/{record_id}"))
        return {
            "provider": "cloudflare",
            "temporary_record": name,
            "created": True,
            "verified": verified,
            "deleted": True,
        }


@dataclass(frozen=True)
class ManualProvider:
    zone: str

    async def verify(self) -> dict[str, str | bool]:
        return {
            "provider": "manual",
            "zone": self.zone,
            "token_active": False,
            "write_test_performed": False,
        }

    async def write_test(self) -> dict[str, str | bool]:
        raise ProviderError("manual DNS does not support automated write tests")


@dataclass(frozen=True)
class RFC2136Provider:
    config: HostingDNSConfig

    async def verify(self) -> dict[str, str | bool]:
        if self.config.credential_file is None:
            raise ProviderError("RFC2136 TSIG secret file is required")
        require_secret_file(self.config.credential_file)
        return {
            "provider": "rfc2136",
            "zone": self.config.zone,
            "configuration_valid": True,
            "write_test_performed": False,
        }

    async def write_test(self) -> dict[str, str | bool]:
        raise ProviderError(
            "RFC2136 write tests are performed by Caddy during staging certificate issuance"
        )


def provider_for(config: HostingDNSConfig) -> DNSProvider:
    if config.provider == "cloudflare":
        return CloudflareProvider(config)
    if config.provider == "rfc2136":
        return RFC2136Provider(config)
    return ManualProvider(config.zone)
