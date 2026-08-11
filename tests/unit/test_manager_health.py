from pathlib import Path
from typing import Any

from pnas.manager.health import LiveHealthProvider, safe_snapshot


async def fake_call(method: str, params: list[Any] | None) -> Any:
    responses: dict[str, Any] = {
        "system.version_short": "25.10.5",
        "pool.query": [
            {
                "name": "tank",
                "status": "ONLINE",
                "healthy": True,
                "size": 1000,
                "allocated": 700,
                "free": 300,
                "scan": {"function": "SCRUB", "state": "FINISHED"},
            }
        ],
        "disk.query": [{"name": "sda", "smart_result": "PASSED"}],
        "app.query": [{"name": "immich", "state": "RUNNING"}],
        "alert.list": [],
    }
    return responses[method]


def test_live_health_normalizes_read_only_api_data(tmp_path: Path) -> None:
    status = tmp_path / "tailscale.json"
    status.write_text(
        '{"BackendState":"Running","Self":{"Online":true,"TailscaleIPs":["100.64.0.2"]}}',
        encoding="utf-8",
    )
    snapshot = LiveHealthProvider(fake_call, tailscale_status_file=status).snapshot()
    assert snapshot["mode"] == "live"
    assert snapshot["storage"]["utilization_percent"] == 70.0
    assert snapshot["services"]["immich"] == "RUNNING"
    assert snapshot["services"]["tailscale"]["status"] == "online"


def test_health_failure_degrades_without_leaking_exception_text() -> None:
    class BrokenProvider:
        def snapshot(self) -> dict[str, Any]:
            raise RuntimeError("secret-value-must-not-appear")

    snapshot = safe_snapshot(BrokenProvider())
    assert snapshot["mode"] == "degraded"
    assert snapshot["stale"] is True
    assert "secret-value" not in str(snapshot)
