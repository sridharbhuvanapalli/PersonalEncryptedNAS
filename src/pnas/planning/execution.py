from __future__ import annotations

import hashlib
import json
import os
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

from pnas.config import StorageConfig
from pnas.models import ExecutionPlan, HardwareInventory
from pnas.preflight import validate_drive_selection, validate_phase2_preconditions


class StalePlanError(RuntimeError):
    pass


class ConfirmationError(ValueError):
    pass


def inventory_fingerprint(inventory: HardwareInventory) -> str:
    payload = inventory.model_dump(mode="json", exclude={"captured_at"})
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(canonical).hexdigest()


def required_confirmation(plan: ExecutionPlan) -> str:
    return f"CREATE {plan.pool_name} USING SERIALS {', '.join(plan.selected_serials)}"


def verify_confirmation(plan: ExecutionPlan, supplied: str) -> None:
    if supplied != required_confirmation(plan):
        raise ConfirmationError("confirmation must exactly match the pool name and ordered serials")


def create_storage_plan(
    *,
    action: str,
    inventory: HardwareInventory,
    storage: StorageConfig,
    selected_serials: tuple[str, ...],
    lifetime_minutes: int = 30,
) -> ExecutionPlan:
    if action not in {"phase1-create", "phase2-expand"}:
        raise ValueError("unsupported storage action")
    if action == "phase2-expand":
        validate_phase2_preconditions(inventory, selected_serials)
    drives = validate_drive_selection(inventory, selected_serials, storage)
    if action == "phase2-expand":
        existing_capacities = {
            drive.capacity_bytes for drive in inventory.drives if drive.role == "data"
        }
        new_capacity = drives[0].capacity_bytes
        if existing_capacities and new_capacity not in existing_capacities:
            if not storage.allow_asymmetric_vdev:
                raise ValueError(
                    "new vdev capacity differs from the existing vdev; separate asymmetric "
                    "capacity approval is required"
                )
    now = datetime.now(UTC)
    operation = (
        f"create pool {storage.pool_name} with one four-drive RAIDZ2 vdev"
        if action == "phase1-create"
        else f"add one four-drive RAIDZ2 data vdev to {storage.pool_name}"
    )
    return ExecutionPlan(
        plan_id=str(uuid.uuid4()),
        created_at=now,
        expires_at=now + timedelta(minutes=lifetime_minutes),
        action=action,
        pool_name=storage.pool_name,
        inventory_fingerprint=inventory_fingerprint(inventory),
        selected_serials=tuple(drive.serial or "" for drive in drives),
        selected_stable_ids=tuple(drive.stable_id or "" for drive in drives),
        destructive_operations=(
            operation,
            "initialize selected disks and destroy existing contents",
        ),
        preconditions=(
            "inventory fingerprint is unchanged",
            "all selected serials and stable identifiers are present",
            "no selected device is boot or application storage",
            "all selected drives pass health policy",
        ),
        metadata={"vdev_type": "RAIDZ2", "vdev_width": 4},
    )


def validate_plan_for_apply(plan: ExecutionPlan, inventory: HardwareInventory) -> None:
    if datetime.now(UTC) >= plan.expires_at:
        raise StalePlanError("plan has expired")
    if inventory_fingerprint(inventory) != plan.inventory_fingerprint:
        raise StalePlanError("inventory changed after planning")


def save_plan(plan: ExecutionPlan, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        handle.write(plan.model_dump_json(indent=2))
        handle.write("\n")


def load_plan(path: Path) -> ExecutionPlan:
    return ExecutionPlan.model_validate_json(path.read_text(encoding="utf-8"))
