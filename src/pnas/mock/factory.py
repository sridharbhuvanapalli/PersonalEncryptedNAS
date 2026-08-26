from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from pnas.models import DeviceRole, Drive, HardwareInventory, SmartState


def _base_drives() -> list[Drive]:
    return [
        Drive(
            model="Samsung SSD PM830 128GB",
            serial="BOOTSSD001",
            stable_id="/dev/disk/by-id/ata-BOOTSSD001",
            capacity_bytes=128_000_000_000,
            rotational=False,
            cmr=None,
            smart=SmartState.PASSED,
            smart_extended_passed=True,
            role=DeviceRole.BOOT,
        ),
        Drive(
            model="Inland TN320 1TB NVMe",
            serial="APPSSD001",
            stable_id="/dev/disk/by-id/nvme-APPSSD001",
            capacity_bytes=1_000_000_000_000,
            rotational=False,
            transport="nvme",
            cmr=None,
            smart=SmartState.PASSED,
            smart_extended_passed=True,
            role=DeviceRole.APPLICATION,
        ),
        Drive(
            model="Inland 512GB SATA III SSD",
            serial="APPRECOVERY001",
            stable_id="/dev/disk/by-id/ata-APPRECOVERY001",
            capacity_bytes=512_000_000_000,
            rotational=False,
            transport="sata",
            cmr=None,
            smart=SmartState.PASSED,
            smart_extended_passed=True,
            role=DeviceRole.APPLICATION,
        ),
    ]


def build_inventory_profile(
    name: str, profiles_path: Path = Path("config/mock-hardware/profiles.yaml")
) -> HardwareInventory:
    raw = yaml.safe_load(profiles_path.read_text(encoding="utf-8"))["profiles"]
    if name not in raw:
        raise KeyError(f"unknown mock hardware profile: {name}")
    profile: dict[str, Any] = raw[name]
    capacities = profile.get("capacities_bytes")
    if capacities is None:
        capacities = [profile["drive_capacity_bytes"]] * profile["data_drive_count"]
    assigned = int(profile.get("assigned_data_drive_count", len(capacities)))
    models = profile.get("models", [])
    transports = profile.get("transports", [])
    drives = _base_drives()
    for index, capacity in enumerate(capacities, start=1):
        serial: str | None = f"DATA{index:03d}"
        if profile.get("missing_serial_bay") == index:
            serial = None
        smart = (
            SmartState.FAILED if profile.get("failed_smart_serial") == serial else SmartState.PASSED
        )
        transport = str(transports[index - 1]) if index <= len(transports) else "sata"
        drives.append(
            Drive(
                bay=index,
                model=(
                    str(models[index - 1])
                    if index <= len(models)
                    else f"NAS CMR {int(capacity) // 1_000_000_000_000}TB"
                ),
                serial=serial,
                stable_id=(
                    f"/dev/disk/by-id/{'wwn' if transport == 'sas' else 'ata'}-{serial}"
                    if serial
                    else None
                ),
                capacity_bytes=int(capacity),
                transport=transport,
                cmr=True,
                smart=smart,
                smart_extended_passed=smart == SmartState.PASSED,
                temperature_c=30 + index % 4,
                power_on_hours=24,
                role=DeviceRole.DATA if index <= assigned else DeviceRole.UNASSIGNED,
            )
        )
    data_serials = tuple(drive.serial for drive in drives[3:] if drive.serial)
    return HardwareInventory(
        inventory_id=f"profile-{name}",
        captured_at=datetime.now(UTC),
        hostname="truenas-mock",
        truenas_version="25.10.6",
        api_version="25.10.6",
        cpu_model="Intel Core i5-12500",
        aes_supported=True,
        memory_bytes=32 * 1024**3,
        nic_model="Intel I225-V",
        nic_link_mbps=2500,
        ups_connected=True,
        drives=tuple(drives),
        pool_healthy=bool(profile.get("pool_healthy", True)),
        scrub_succeeded=True,
        resilver_active=False,
        database_dumps_current=bool(profile.get("database_dumps_current", False)),
        snapshots_current=bool(profile.get("snapshots_current", False)),
        offsite_backup_current=bool(profile.get("offsite_backup_current", False)),
        restore_test_recent=bool(profile.get("restore_test_recent", False)),
        burn_in_passed_serials=data_serials if profile.get("burn_in_passed", False) else (),
    )
