from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pnas.models import HardwareInventory
from pnas.truenas.base import require_supported_api


class MockTrueNASAdapter:
    def __init__(self, fixture_path: Path):
        self._fixture_path = fixture_path
        self._inventory = HardwareInventory.model_validate_json(
            fixture_path.read_text(encoding="utf-8")
        )

    async def api_version(self) -> str:
        require_supported_api(self._inventory.api_version)
        return self._inventory.api_version

    async def inventory(self) -> HardwareInventory:
        await self.api_version()
        return self._inventory

    async def call(self, method: str, params: list[Any] | None = None) -> Any:
        del params
        if method == "system.version":
            return self._inventory.truenas_version
        if method == "disk.query":
            return [json.loads(drive.model_dump_json()) for drive in self._inventory.drives]
        raise NotImplementedError(f"mock method not implemented: {method}")
