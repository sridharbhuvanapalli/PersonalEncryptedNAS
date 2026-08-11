from __future__ import annotations

from typing import Any, Protocol

from pnas.models import HardwareInventory

SUPPORTED_API_VERSIONS = frozenset({"25.10", "25.10.4", "25.10.5"})


class UnsupportedAPIVersionError(RuntimeError):
    pass


class TrueNASAdapter(Protocol):
    async def api_version(self) -> str: ...

    async def inventory(self) -> HardwareInventory: ...

    async def call(self, method: str, params: list[Any] | None = None) -> Any: ...


def require_supported_api(version: str) -> None:
    if version not in SUPPORTED_API_VERSIONS:
        raise UnsupportedAPIVersionError(
            f"unsupported TrueNAS API {version}; supported: {sorted(SUPPORTED_API_VERSIONS)}"
        )
