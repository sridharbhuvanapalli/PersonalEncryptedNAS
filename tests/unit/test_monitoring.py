from datetime import UTC, datetime, timedelta

from pnas.mock import build_inventory_profile
from pnas.monitoring import ProtectionStatus, evaluate_health


def test_failed_smart_and_ups_shutdown_are_critical() -> None:
    now = datetime.now(UTC)
    alerts = evaluate_health(
        build_inventory_profile("failed-smart"),
        ProtectionStatus(
            utilization_percent=50,
            latest_backup=now,
            latest_restore_test=now,
            database_healthy=True,
            certificate_days_remaining=90,
            ups_online=True,
            ups_shutdown_condition=True,
        ),
        now=now,
    )
    assert {alert.code for alert in alerts} >= {"smart_failed", "ups_shutdown"}
    assert all(alert.level == "critical" for alert in alerts)


def test_capacity_and_restore_age_thresholds() -> None:
    now = datetime.now(UTC)
    alerts = evaluate_health(
        build_inventory_profile("four-4tb"),
        ProtectionStatus(
            utilization_percent=75,
            latest_backup=now,
            latest_restore_test=now - timedelta(days=91),
            database_healthy=True,
            certificate_days_remaining=90,
            ups_online=True,
        ),
        now=now,
    )
    assert {alert.code for alert in alerts} == {"capacity_70", "restore_stale"}
