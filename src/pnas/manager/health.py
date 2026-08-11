from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

from pnas.tailscale.diagnostics import analyze_status


class HealthProvider(Protocol):
    def snapshot(self) -> dict[str, Any]: ...


class MockHealthProvider:
    def snapshot(self) -> dict[str, Any]:
        return mock_health_snapshot()


class LiveHealthProvider:
    """Read-only, timeout-bounded TrueNAS and Tailscale health collector."""

    def __init__(
        self,
        call: Callable[[str, list[Any] | None], Awaitable[Any]],
        *,
        tailscale_status_file: Path | None = None,
        timeout_seconds: float = 10,
    ):
        self.call = call
        self.tailscale_status_file = tailscale_status_file
        self.timeout_seconds = timeout_seconds

    async def _collect(self) -> list[Any]:
        operations = (
            self.call("system.version_short", None),
            self.call("pool.query", None),
            self.call("disk.query", None),
            self.call("app.query", None),
            self.call("alert.list", None),
        )
        return list(
            await asyncio.wait_for(asyncio.gather(*operations), timeout=self.timeout_seconds)
        )

    def snapshot(self) -> dict[str, Any]:
        version, pools_raw, disks_raw, apps_raw, alerts_raw = asyncio.run(self._collect())
        pools = pools_raw if isinstance(pools_raw, list) else []
        disks = disks_raw if isinstance(disks_raw, list) else []
        apps = apps_raw if isinstance(apps_raw, list) else []
        alerts = alerts_raw if isinstance(alerts_raw, list) else []
        pool = pools[0] if pools and isinstance(pools[0], dict) else {}
        size = pool.get("size")
        allocated = pool.get("allocated")
        utilization = (
            round(float(allocated) / float(size) * 100, 1)
            if isinstance(size, int) and size > 0 and isinstance(allocated, int)
            else None
        )
        scan = pool.get("scan") if isinstance(pool.get("scan"), dict) else {}
        app_states = {
            str(app.get("name", "unknown")): str(app.get("state", "UNKNOWN"))
            for app in apps
            if isinstance(app, dict)
        }
        disk_warnings = [
            str(disk.get("name") or disk.get("serial") or "unknown")
            for disk in disks
            if isinstance(disk, dict)
            and (disk.get("smart_result") not in (None, "PASSED") or disk.get("expiretime"))
        ]
        warnings = [
            str(alert.get("formatted") or alert.get("klass") or "TrueNAS alert")
            for alert in alerts
            if isinstance(alert, dict) and not alert.get("dismissed", False)
        ]
        tailscale: dict[str, Any] = {"status": "not-observed"}
        if self.tailscale_status_file is not None and self.tailscale_status_file.is_file():
            import json

            raw = json.loads(self.tailscale_status_file.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                report = analyze_status(raw)
                tailscale = {
                    "status": "online" if report.self_online else "offline",
                    "addresses": list(report.tailscale_ips),
                    "direct_peers": report.direct_peers,
                    "relayed_peers": report.relayed_peers,
                }
                warnings.extend(report.warnings)
        return {
            "captured_at": datetime.now(UTC).isoformat(),
            "mode": "live",
            "read_only": True,
            "stale": False,
            "storage": {
                "truenas_version": str(version),
                "pool_name": pool.get("name"),
                "pool_health": pool.get("status", "UNKNOWN"),
                "pool_healthy": bool(pool.get("healthy", False)),
                "size_bytes": size,
                "allocated_bytes": allocated,
                "free_bytes": pool.get("free"),
                "utilization_percent": utilization,
                "scan": scan,
            },
            "disks": {
                "assigned": len(disks),
                "warnings": disk_warnings,
            },
            "protection": {
                "latest_snapshot": None,
                "latest_backup": None,
                "latest_restore_test": None,
            },
            "power": {"ups": "verify-in-TrueNAS", "runtime_minutes": None},
            "services": {**app_states, "tailscale": tailscale},
            "updates": {"truenas": None, "applications": None},
            "warnings": warnings + disk_warnings,
        }


def safe_snapshot(provider: HealthProvider) -> dict[str, Any]:
    try:
        return provider.snapshot()
    except Exception as exc:
        return {
            "captured_at": datetime.now(UTC).isoformat(),
            "mode": "degraded",
            "read_only": True,
            "stale": True,
            "storage": {},
            "disks": {},
            "protection": {},
            "power": {},
            "services": {},
            "updates": {},
            "warnings": [f"Live health collection failed ({type(exc).__name__})"],
        }


def mock_health_snapshot() -> dict[str, Any]:
    return {
        "captured_at": datetime.now(UTC).isoformat(),
        "mode": "mock",
        "read_only": True,
        "stale": False,
        "storage": {
            "truenas_version": "25.10.5 (planned target)",
            "pool_health": "MOCK_HEALTHY",
            "vdev_topology": ["4-drive RAIDZ2"],
            "dataset_encryption": "mock-unlocked",
            "raw_tb": 16.0,
            "nominal_tib": 7.28,
            "actual_free_tib": None,
            "snapshot_usage_tib": None,
            "utilization_percent": None,
            "forecast_70_percent": None,
            "forecast_80_percent": None,
            "latest_scrub": "fixture-success",
        },
        "disks": {"assigned": 4, "empty_bays": 4, "unassigned": 0, "warnings": []},
        "protection": {
            "latest_snapshot": None,
            "latest_backup": None,
            "latest_restore_test": None,
        },
        "power": {"ups": "fixture-online", "runtime_minutes": None},
        "services": {
            "nextcloud": "not-deployed",
            "immich": "not-deployed",
            "postgresql": "not-deployed",
            "redis_valkey": "not-deployed",
            "proxy": "not-deployed",
            "tailscale": "not-deployed",
        },
        "updates": {"truenas": None, "applications": None},
        "warnings": ["Mock mode: hardware and services have not been validated"],
    }
