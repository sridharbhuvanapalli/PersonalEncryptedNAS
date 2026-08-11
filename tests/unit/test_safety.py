from pathlib import Path

import pytest

from pnas.config import load_config
from pnas.mock import MockTrueNASAdapter
from pnas.preflight import UnsafeDriveSelectionError, validate_drive_selection


@pytest.fixture
def context():  # type: ignore[no-untyped-def]
    adapter = MockTrueNASAdapter(Path("tests/fixtures/inventory-four-4tb.json"))
    return adapter, load_config(Path("config/pnas.example.yaml"))


@pytest.mark.asyncio
async def test_valid_data_drives(context) -> None:  # type: ignore[no-untyped-def]
    adapter, config = context
    inventory = await adapter.inventory()
    drives = validate_drive_selection(
        inventory, tuple(f"DATA4T00{number}" for number in range(1, 5)), config.storage
    )
    assert len(drives) == 4


@pytest.mark.asyncio
async def test_boot_device_cannot_be_selected(context) -> None:  # type: ignore[no-untyped-def]
    adapter, config = context
    inventory = await adapter.inventory()
    with pytest.raises(UnsafeDriveSelectionError, match="protected"):
        validate_drive_selection(
            inventory, ("BOOTSSD001", "DATA4T001", "DATA4T002", "DATA4T003"), config.storage
        )


@pytest.mark.asyncio
async def test_application_device_cannot_be_selected(context) -> None:  # type: ignore[no-untyped-def]
    adapter, config = context
    inventory = await adapter.inventory()
    with pytest.raises(UnsafeDriveSelectionError, match="protected"):
        validate_drive_selection(
            inventory, ("APPSSD001", "DATA4T001", "DATA4T002", "DATA4T003"), config.storage
        )
