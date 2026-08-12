import pytest

from pnas.mock import build_inventory_profile
from pnas.planning.capacity import calculate_raidz2_capacity


@pytest.mark.parametrize(
    ("profile", "count", "capacity"),
    [
        ("four-4tb", 4, 4_000_000_000_000),
        ("eight-4tb", 8, 4_000_000_000_000),
        ("four-8tb", 4, 8_000_000_000_000),
        ("eight-8tb", 8, 8_000_000_000_000),
    ],
)
def test_capacity_profiles_build(profile: str, count: int, capacity: int) -> None:
    inventory = build_inventory_profile(profile)
    drives = inventory.drives[2:]
    assert len(drives) == count
    plan = calculate_raidz2_capacity(drive_count=count, drive_capacity_bytes=capacity)
    assert plan.drive_capacity_decimal_tb in (4.0, 8.0)


def test_fault_profiles_build() -> None:
    assert not build_inventory_profile("degraded-pool").pool_healthy
    assert any(drive.smart == "failed" for drive in build_inventory_profile("failed-smart").drives)
    assert any(drive.serial is None for drive in build_inventory_profile("missing-serial").drives)
    assert (
        len(
            set(
                drive.capacity_bytes
                for drive in build_inventory_profile("mixed-capacities").drives[2:]
            )
        )
        == 2
    )


def test_archive_profile_has_four_new_unassigned_sata_drives() -> None:
    inventory = build_inventory_profile("archive-deployment")
    assert len([drive for drive in inventory.drives if drive.role == "data"]) == 4
    archive = [drive for drive in inventory.drives if drive.role == "unassigned"]
    assert len(archive) == 4
    assert {drive.capacity_bytes for drive in archive} == {3_000_000_000_000}
    assert {drive.transport for drive in archive} == {"sata"}
