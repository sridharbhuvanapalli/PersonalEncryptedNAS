import pytest

from pnas.planning.capacity import BYTES_PER_TB, calculate_raidz2_capacity


@pytest.mark.parametrize(
    ("count", "size_tb", "raw_tb", "usable_tb", "target_tib"),
    [
        (4, 3, 12, 6, 4.3655745685),
        (4, 18, 72, 36, 26.1934474111),
    ],
)
def test_capacity_profiles(
    count: int, size_tb: int, raw_tb: int, usable_tb: int, target_tib: float
) -> None:
    plan = calculate_raidz2_capacity(drive_count=count, drive_capacity_bytes=size_tb * BYTES_PER_TB)
    assert plan.raw_decimal_tb == raw_tb
    assert plan.nominal_raidz2_decimal_tb == usable_tb
    assert plan.planning_target_tib == pytest.approx(target_tib)


def test_rejects_unsupported_width() -> None:
    with pytest.raises(ValueError, match="four-drive"):
        calculate_raidz2_capacity(
            drive_count=4, drive_capacity_bytes=4 * BYTES_PER_TB, vdev_width=5
        )
