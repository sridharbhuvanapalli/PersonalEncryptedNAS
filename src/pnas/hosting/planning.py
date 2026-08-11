from __future__ import annotations

import hashlib
import json
import os
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Literal

from pydantic import Field

from pnas.config import HostingConfig
from pnas.models import StrictModel


class HostingPlanError(RuntimeError):
    pass


class HostingExecutionPlan(StrictModel):
    schema_version: int = 1
    plan_id: str
    created_at: datetime
    expires_at: datetime
    config_fingerprint: str
    provider: str
    hostnames: tuple[str, ...]
    private_addresses: tuple[str, ...]
    operations: tuple[str, ...]
    persistent_public_records: Literal[False] = False
    approved: bool = False
    applied: bool = False
    metadata: dict[str, str] = Field(default_factory=dict)


def hosting_fingerprint(config: HostingConfig) -> str:
    payload = config.model_dump(mode="json")
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(canonical).hexdigest()


def create_hosting_plan(
    config: HostingConfig, *, lifetime_minutes: int = 30
) -> HostingExecutionPlan:
    if not config.enabled:
        raise HostingPlanError("hosting must be explicitly enabled before planning")
    now = datetime.now(UTC)
    addresses = [str(config.private_addresses.lan)]
    if config.private_addresses.tailscale is not None:
        addresses.append(str(config.private_addresses.tailscale))
    return HostingExecutionPlan(
        plan_id=str(uuid.uuid4()),
        created_at=now,
        expires_at=now + timedelta(minutes=lifetime_minutes),
        config_fingerprint=hosting_fingerprint(config),
        provider=config.dns.provider,
        hostnames=config.hostnames,
        private_addresses=tuple(addresses),
        operations=(
            "render a private-only Caddy configuration",
            "render LAN and Tailscale split-DNS records",
            "configure ACME DNS-01 without public service records",
            "retain the prior hosting revision for rollback",
        ),
        metadata={
            "exposure": config.exposure,
            "certificate_environment": config.certificates.environment,
        },
    )


def hosting_confirmation(plan: HostingExecutionPlan) -> str:
    return f"CONFIGURE PRIVATE HTTPS FOR {', '.join(plan.hostnames)} USING {plan.provider}"


def validate_hosting_plan(
    plan: HostingExecutionPlan, config: HostingConfig, confirmation: str
) -> None:
    if datetime.now(UTC) >= plan.expires_at:
        raise HostingPlanError("hosting plan has expired")
    if hosting_fingerprint(config) != plan.config_fingerprint:
        raise HostingPlanError("hosting configuration changed after planning")
    if confirmation != hosting_confirmation(plan):
        raise HostingPlanError("confirmation must exactly match all hostnames and provider")


def save_hosting_plan(plan: HostingExecutionPlan, state_dir: Path) -> Path:
    plan_dir = state_dir / "hosting" / "plans"
    plan_dir.mkdir(parents=True, exist_ok=True)
    destination = plan_dir / f"{plan.plan_id}.json"
    descriptor = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        handle.write(plan.model_dump_json(indent=2) + "\n")
    return destination


def load_hosting_plan(path: Path) -> HostingExecutionPlan:
    return HostingExecutionPlan.model_validate_json(path.read_text(encoding="utf-8"))
