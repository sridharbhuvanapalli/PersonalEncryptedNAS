from __future__ import annotations

from dataclasses import dataclass

from pnas.config import StorageConfig
from pnas.models import DeviceRole, Drive, HardwareInventory, SmartState


@dataclass(frozen=True)
class SafetyViolation:
    code: str
    serial: str | None
    message: str


class UnsafeDriveSelectionError(ValueError):
    def __init__(self, violations: list[SafetyViolation]):
        self.violations = violations
        super().__init__("; ".join(item.message for item in violations))


def validate_drive_selection(
    inventory: HardwareInventory,
    selected_serials: tuple[str, ...],
    storage: StorageConfig,
    *,
    expected_new_drives: int = 4,
) -> tuple[Drive, ...]:
    violations: list[SafetyViolation] = []
    if len(selected_serials) != expected_new_drives or len(set(selected_serials)) != len(
        selected_serials
    ):
        violations.append(
            SafetyViolation(
                "drive_count", None, f"exactly {expected_new_drives} unique serials required"
            )
        )
    by_serial = {drive.serial: drive for drive in inventory.drives if drive.serial}
    selected: list[Drive] = []
    for serial in selected_serials:
        drive = by_serial.get(serial)
        if drive is None:
            violations.append(SafetyViolation("unknown_serial", serial, f"unknown serial {serial}"))
            continue
        selected.append(drive)
        if drive.role in (DeviceRole.BOOT, DeviceRole.APPLICATION):
            violations.append(
                SafetyViolation(
                    "protected_device", serial, f"{serial} is a protected {drive.role} device"
                )
            )
        if serial in storage.boot_device_serials or serial in storage.application_device_serials:
            violations.append(
                SafetyViolation(
                    "configured_protected_device", serial, f"{serial} is configured as protected"
                )
            )
        if drive.transport.lower() == "usb":
            violations.append(SafetyViolation("usb_device", serial, f"{serial} uses USB transport"))
        if not drive.safe_identity:
            violations.append(
                SafetyViolation("identity", serial, f"{serial} lacks stable identity")
            )
        if drive.smart != SmartState.PASSED:
            violations.append(SafetyViolation("smart", serial, f"{serial} SMART is not passing"))
        if storage.require_smart_extended_test and drive.smart_extended_passed is not True:
            violations.append(
                SafetyViolation(
                    "smart_extended", serial, f"{serial} has no passing extended SMART test"
                )
            )
        if storage.require_cmr and drive.cmr is not True:
            violations.append(SafetyViolation("cmr", serial, f"{serial} is not confirmed CMR"))
    if selected:
        smallest = min(drive.capacity_bytes for drive in selected)
        if any(drive.capacity_bytes != smallest for drive in selected):
            violations.append(
                SafetyViolation("mixed_capacity", None, "selected drives must have equal capacity")
            )
    if violations:
        raise UnsafeDriveSelectionError(violations)
    return tuple(selected)


def validate_archive_preconditions(
    inventory: HardwareInventory, selected_serials: tuple[str, ...]
) -> None:
    failures: list[str] = []
    if not inventory.pool_healthy:
        failures.append("existing pool is not healthy")
    if not inventory.scrub_succeeded:
        failures.append("latest scrub did not succeed")
    if inventory.resilver_active:
        failures.append("a resilver is active")
    if not inventory.ups_connected:
        failures.append("UPS is not connected")
    if not inventory.database_dumps_current:
        failures.append("database dumps are not current")
    if not inventory.snapshots_current:
        failures.append("snapshots are not current")
    if not inventory.offsite_backup_current:
        failures.append("offsite backup is not current")
    if not inventory.restore_test_recent:
        failures.append("recent restore test is missing")
    if not set(selected_serials).issubset(set(inventory.burn_in_passed_serials)):
        failures.append("burn-in has not passed for every selected serial")
    if failures:
        raise ValueError("; ".join(failures))
