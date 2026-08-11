from pathlib import Path

import pytest

from pnas.config import load_config
from pnas.mock import MockTrueNASAdapter, build_inventory_profile
from pnas.planning.execution import (
    ConfirmationError,
    StalePlanError,
    create_storage_plan,
    required_confirmation,
    validate_plan_for_apply,
    verify_confirmation,
)


@pytest.mark.asyncio
async def test_exact_confirmation_and_changed_inventory() -> None:
    inventory = await MockTrueNASAdapter(Path("tests/fixtures/inventory-four-4tb.json")).inventory()
    config = load_config(Path("config/pnas.example.yaml"))
    plan = create_storage_plan(
        action="phase1-create",
        inventory=inventory,
        storage=config.storage,
        selected_serials=("DATA4T001", "DATA4T002", "DATA4T003", "DATA4T004"),
    )
    verify_confirmation(plan, required_confirmation(plan))
    with pytest.raises(ConfirmationError):
        verify_confirmation(plan, "yes")
    changed = inventory.model_copy(update={"nic_link_mbps": 1000})
    with pytest.raises(StalePlanError, match="changed"):
        validate_plan_for_apply(plan, changed)


def test_phase2_plan_requires_and_accepts_complete_safety_gate() -> None:
    inventory = build_inventory_profile("phase2-expansion")
    config = load_config(Path("config/pnas.example.yaml"))
    config = config.model_copy(
        update={
            "storage": config.storage.model_copy(
                update={"deployment_phase": 2, "expected_drive_count": 8}
            )
        }
    )
    plan = create_storage_plan(
        action="phase2-expand",
        inventory=inventory,
        storage=config.storage,
        selected_serials=("DATA005", "DATA006", "DATA007", "DATA008"),
    )
    assert plan.metadata["vdev_type"] == "RAIDZ2"


def test_phase2_refuses_missing_offsite_backup_gate() -> None:
    inventory = build_inventory_profile("phase2-expansion").model_copy(
        update={"offsite_backup_current": False}
    )
    config = load_config(Path("config/pnas.example.yaml"))
    with pytest.raises(ValueError, match="offsite backup"):
        create_storage_plan(
            action="phase2-expand",
            inventory=inventory,
            storage=config.storage,
            selected_serials=("DATA005", "DATA006", "DATA007", "DATA008"),
        )
