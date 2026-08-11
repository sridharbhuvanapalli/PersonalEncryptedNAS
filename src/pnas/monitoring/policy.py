from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum

from pnas.models import HardwareInventory, SmartState


class AlertLevel(StrEnum):
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass(frozen=True)
class Alert:
    level: AlertLevel
    code: str
    message: str


@dataclass(frozen=True)
class ProtectionStatus:
    utilization_percent: float
    latest_backup: datetime | None
    latest_restore_test: datetime | None
    database_healthy: bool
    certificate_days_remaining: int
    ups_online: bool
    ups_shutdown_condition: bool = False


def evaluate_health(
    inventory: HardwareInventory,
    protection: ProtectionStatus,
    *,
    now: datetime | None = None,
) -> tuple[Alert, ...]:
    current = now or datetime.now(UTC)
    alerts: list[Alert] = []
    if not inventory.pool_healthy:
        alerts.append(Alert(AlertLevel.CRITICAL, "pool_degraded", "ZFS pool is not healthy"))
    for drive in inventory.drives:
        if drive.smart == SmartState.FAILED:
            alerts.append(
                Alert(
                    AlertLevel.CRITICAL, "smart_failed", f"SMART failed for serial {drive.serial}"
                )
            )
        if drive.temperature_c is not None and drive.temperature_c >= 50:
            alerts.append(
                Alert(
                    AlertLevel.WARNING,
                    "disk_hot",
                    f"disk {drive.serial} is {drive.temperature_c} C",
                )
            )
    if protection.utilization_percent >= 80:
        alerts.append(Alert(AlertLevel.CRITICAL, "capacity_80", "pool utilization is at least 80%"))
    elif protection.utilization_percent >= 70:
        alerts.append(Alert(AlertLevel.WARNING, "capacity_70", "pool utilization is at least 70%"))
    if protection.latest_backup is None or (current - protection.latest_backup).days >= 2:
        alerts.append(
            Alert(AlertLevel.CRITICAL, "backup_stale", "no successful backup in 48 hours")
        )
    if (
        protection.latest_restore_test is None
        or (current - protection.latest_restore_test).days >= 90
    ):
        alerts.append(
            Alert(
                AlertLevel.WARNING, "restore_stale", "restore test is missing or over 90 days old"
            )
        )
    if not protection.database_healthy:
        alerts.append(Alert(AlertLevel.CRITICAL, "database_unavailable", "database is unavailable"))
    if protection.certificate_days_remaining <= 14:
        alerts.append(
            Alert(AlertLevel.WARNING, "certificate_expiry", "certificate expires within 14 days")
        )
    if not protection.ups_online or protection.ups_shutdown_condition:
        alerts.append(Alert(AlertLevel.CRITICAL, "ups_shutdown", "UPS requires safe shutdown"))
    return tuple(alerts)
