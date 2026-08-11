from pathlib import Path

import pytest

from pnas.mock import MockTrueNASAdapter


@pytest.mark.asyncio
async def test_mock_inventory() -> None:
    adapter = MockTrueNASAdapter(Path("tests/fixtures/inventory-four-4tb.json"))
    inventory = await adapter.inventory()
    assert len([drive for drive in inventory.drives if drive.role == "data"]) == 4
    assert inventory.api_version == "25.10.4"
