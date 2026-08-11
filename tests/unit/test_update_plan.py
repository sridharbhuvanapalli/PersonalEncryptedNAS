import pytest

from pnas.applications import UpdateReadiness, create_update_plan


def readiness(**changes: bool) -> UpdateReadiness:
    values = {
        "release_notes_reviewed": True,
        "breaking_changes_reviewed": True,
        "database_dump_verified": True,
        "zfs_snapshot_created": True,
        "offsite_backup_fresh": True,
    }
    values.update(changes)
    return UpdateReadiness(**values)


def test_update_plan_is_unapproved_and_has_rollback() -> None:
    plan = create_update_plan(
        application="immich",
        current_version="v3.0.3",
        target_version="v3.1.0",
        readiness=readiness(),
    )
    assert plan.approved is False and plan.executed is False
    assert plan.rollback_steps


def test_update_plan_refuses_missing_backup_gate() -> None:
    with pytest.raises(ValueError, match="offsite_backup_fresh"):
        create_update_plan(
            application="nextcloud",
            current_version="34.0.1",
            target_version="34.0.2",
            readiness=readiness(offsite_backup_fresh=False),
        )
