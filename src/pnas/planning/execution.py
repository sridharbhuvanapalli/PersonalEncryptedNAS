from __future__ import annotations

import hashlib
import json
import os
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

from pnas.config import StorageConfig
from pnas.models import ExecutionPlan, HardwareInventory
from pnas.preflight import validate_archive_preconditions, validate_drive_selection


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
    if action not in {"main-create", "archive-create"}:
        raise ValueError("unsupported storage action")
    if action == "archive-create":
        validate_archive_preconditions(inventory, selected_serials)
    drives = validate_drive_selection(inventory, selected_serials, storage)
    expected_transport: str
    expected_model: str
    accepted_model_identifiers: tuple[str, ...]
    if action == "main-create":
        pool_name = storage.pool_name
        expected_capacity_tb = storage.drive_capacity_tb
        expected_transport = storage.required_transport
        expected_sector_bytes = storage.required_logical_sector_bytes
        expected_model = storage.drive_model
        accepted_model_identifiers = ("hc550", "wuh721818")
    else:
        pool_name = storage.archive_pool.pool_name
        expected_capacity_tb = storage.archive_pool.drive_capacity_tb
        expected_transport = storage.archive_pool.required_transport
        expected_sector_bytes = storage.archive_pool.required_logical_sector_bytes
        expected_model = storage.archive_pool.drive_model
        accepted_model_identifiers = ("dt01aca300",)
    expected_capacity_bytes = int(expected_capacity_tb * 1_000_000_000_000)
    if any(drive.capacity_bytes != expected_capacity_bytes for drive in drives):
        raise ValueError(f"{pool_name} requires four {expected_capacity_tb:g} TB drives")
    if any(drive.transport.lower() != expected_transport for drive in drives):
        raise ValueError(f"{pool_name} requires {expected_transport.upper()} drives")
    if any(drive.logical_sector_bytes != expected_sector_bytes for drive in drives):
        raise ValueError(
            f"{pool_name} requires {expected_sector_bytes}-byte logical sectors on every drive"
        )
    if any(
        not any(identifier in drive.model.casefold() for identifier in accepted_model_identifiers)
        for drive in drives
    ):
        raise ValueError(f"{pool_name} requires the configured {expected_model} drive family")
    now = datetime.now(UTC)
    operation = f"create independent pool {pool_name} with one four-drive RAIDZ2 vdev"
    return ExecutionPlan(
        plan_id=str(uuid.uuid4()),
        created_at=now,
        expires_at=now + timedelta(minutes=lifetime_minutes),
        action=action,
        pool_name=pool_name,
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
        metadata={
            "vdev_type": "RAIDZ2",
            "vdev_width": 4,
            "expected_model": expected_model,
            "required_transport": expected_transport,
            "independent_pool": True,
        },
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
