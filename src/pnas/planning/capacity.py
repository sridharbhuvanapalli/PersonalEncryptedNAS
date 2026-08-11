from __future__ import annotations

from pnas.models import CapacityPlan

BYTES_PER_TB = 1_000_000_000_000
BYTES_PER_TIB = 1_099_511_627_776


def calculate_raidz2_capacity(
    *,
    drive_count: int,
    drive_capacity_bytes: int,
    vdev_width: int = 4,
    overhead_percent: float = 0.0,
    planning_target_percent: float = 80.0,
) -> CapacityPlan:
    if drive_count not in (4, 8):
        raise ValueError("supported layouts contain four or eight data drives")
    if vdev_width != 4 or drive_count % vdev_width:
        raise ValueError("this platform requires four-drive RAIDZ2 vdevs")
    if drive_capacity_bytes <= 0:
        raise ValueError("drive capacity must be positive")
    if not 0 <= overhead_percent < 50:
        raise ValueError("overhead percent must be between 0 and 50")
    if not 1 <= planning_target_percent <= 100:
        raise ValueError("planning target percent must be between 1 and 100")

    vdev_count = drive_count // vdev_width
    raw_bytes = drive_count * drive_capacity_bytes
    usable_bytes = vdev_count * (vdev_width - 2) * drive_capacity_bytes
    usable_tib = usable_bytes / BYTES_PER_TIB
    after_overhead = usable_tib * (1 - overhead_percent / 100)
    target = after_overhead * planning_target_percent / 100
    return CapacityPlan(
        drive_count=drive_count,
        drive_capacity_decimal_tb=drive_capacity_bytes / BYTES_PER_TB,
        raw_decimal_tb=raw_bytes / BYTES_PER_TB,
        nominal_raidz2_decimal_tb=usable_bytes / BYTES_PER_TB,
        nominal_raidz2_tib=usable_tib,
        overhead_percent=overhead_percent,
        estimated_after_overhead_tib=after_overhead,
        planning_target_percent=planning_target_percent,
        planning_target_tib=target,
    )
