from __future__ import annotations

import uuid
from datetime import UTC, datetime

from pydantic import Field

from pnas.models import StrictModel


class UpdateReadiness(StrictModel):
    release_notes_reviewed: bool
    breaking_changes_reviewed: bool
    database_dump_verified: bool
    zfs_snapshot_created: bool
    offsite_backup_fresh: bool


class ApplicationUpdatePlan(StrictModel):
    plan_id: str
    created_at: datetime
    application: str
    current_version: str
    target_version: str
    steps: tuple[str, ...]
    rollback_steps: tuple[str, ...]
    approved: bool = False
    executed: bool = False
    metadata: dict[str, str] = Field(default_factory=dict)


def create_update_plan(
    *,
    application: str,
    current_version: str,
    target_version: str,
    readiness: UpdateReadiness,
) -> ApplicationUpdatePlan:
    missing = [name for name, ready in readiness.model_dump().items() if not ready]
    if missing:
        raise ValueError(f"update preconditions not met: {', '.join(missing)}")
    if current_version == target_version:
        raise ValueError("target version must differ from current version")
    return ApplicationUpdatePlan(
        plan_id=str(uuid.uuid4()),
        created_at=datetime.now(UTC),
        application=application,
        current_version=current_version,
        target_version=target_version,
        steps=(
            "stop only the selected application project",
            "pull the explicitly pinned target images",
            "start the selected application project",
            "run container health and functional checks",
            "record the result in the audit log",
        ),
        rollback_steps=(
            "stop the failed application project",
            "restore the pre-update database dump if schema migration occurred",
            "roll back the application datasets to the pre-update snapshot where safe",
            "restore the prior pinned image definitions",
            "start and validate the prior version",
        ),
        metadata={"scope": "single-application", "unattended": "false"},
    )
