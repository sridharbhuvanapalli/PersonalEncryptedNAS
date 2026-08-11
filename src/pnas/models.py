from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class DeviceRole(StrEnum):
    DATA = "data"
    BOOT = "boot"
    APPLICATION = "application"
    UNASSIGNED = "unassigned"


class SmartState(StrEnum):
    PASSED = "passed"
    FAILED = "failed"
    UNKNOWN = "unknown"


class Drive(StrictModel):
    bay: int | None = Field(default=None, ge=1, le=64)
    model: str
    serial: str | None
    stable_id: str | None
    capacity_bytes: int = Field(gt=0)
    logical_sector_bytes: int = Field(default=512, gt=0)
    physical_sector_bytes: int = Field(default=4096, gt=0)
    rotational: bool = True
    transport: str = "sata"
    cmr: bool | None = None
    smart: SmartState = SmartState.UNKNOWN
    smart_extended_passed: bool | None = None
    temperature_c: int | None = Field(default=None, ge=-20, le=100)
    power_on_hours: int | None = Field(default=None, ge=0)
    role: DeviceRole = DeviceRole.UNASSIGNED
    warranty: str | None = None

    @property
    def safe_identity(self) -> bool:
        return bool(self.serial and self.stable_id)


class HardwareInventory(StrictModel):
    inventory_id: str
    captured_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    hostname: str
    truenas_version: str
    api_version: str
    cpu_model: str
    aes_supported: bool
    memory_bytes: int = Field(gt=0)
    nic_model: str
    nic_link_mbps: int = Field(gt=0)
    ups_connected: bool
    drives: tuple[Drive, ...]
    pool_healthy: bool = True
    scrub_succeeded: bool = True
    resilver_active: bool = False
    database_dumps_current: bool = False
    snapshots_current: bool = False
    offsite_backup_current: bool = False
    restore_test_recent: bool = False
    burn_in_passed_serials: tuple[str, ...] = ()

    @model_validator(mode="after")
    def unique_identities(self) -> HardwareInventory:
        serials = [drive.serial for drive in self.drives if drive.serial]
        stable_ids = [drive.stable_id for drive in self.drives if drive.stable_id]
        if len(serials) != len(set(serials)):
            raise ValueError("drive serials must be unique")
        if len(stable_ids) != len(set(stable_ids)):
            raise ValueError("stable drive identifiers must be unique")
        return self


class CapacityPlan(StrictModel):
    drive_count: int
    drive_capacity_decimal_tb: float
    raw_decimal_tb: float
    nominal_raidz2_decimal_tb: float
    nominal_raidz2_tib: float
    overhead_percent: float
    estimated_after_overhead_tib: float
    planning_target_percent: float
    planning_target_tib: float


class ExecutionPlan(StrictModel):
    schema_version: int = 1
    plan_id: str
    created_at: datetime
    expires_at: datetime
    action: str
    pool_name: str
    inventory_fingerprint: str
    selected_serials: tuple[str, ...]
    selected_stable_ids: tuple[str, ...]
    destructive_operations: tuple[str, ...]
    preconditions: tuple[str, ...]
    metadata: dict[str, Any] = Field(default_factory=dict)
