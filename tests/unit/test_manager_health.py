from pathlib import Path
from typing import Any

from pnas.manager.health import LiveHealthProvider, safe_snapshot


async def fake_call(method: str, params: list[Any] | None) -> Any:
    responses: dict[str, Any] = {
        "system.version_short": "25.10.6",
        "pool.query": [
            {
                "name": "tank",
                "status": "ONLINE",
                "healthy": True,
                "size": 1000,
                "allocated": 700,
                "free": 300,
                "scan": {"function": "SCRUB", "state": "FINISHED"},
            },
            {
                "name": "archive",
                "status": "ONLINE",
                "healthy": True,
                "size": 500,
                "allocated": 100,
                "free": 400,
                "scan": {"function": "SCRUB", "state": "FINISHED"},
            },
            {
                "name": "apps",
                "status": "ONLINE",
                "healthy": True,
                "size": 1000,
                "allocated": 200,
                "free": 800,
            },
            {
                "name": "app-recovery",
                "status": "ONLINE",
                "healthy": True,
                "size": 512,
                "allocated": 100,
                "free": 412,
            },
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
    assert snapshot["storage"]["pools"][0]["utilization_percent"] == 70.0
    assert snapshot["storage"]["all_pools_healthy"] is True
    assert len(snapshot["storage"]["pools"]) == 4
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


def test_live_health_marks_missing_required_pool_unhealthy() -> None:
    async def one_pool_call(method: str, params: list[Any] | None) -> Any:
        response = await fake_call(method, params)
        if method == "pool.query":
            return response[:1]
        return response

    snapshot = LiveHealthProvider(one_pool_call).snapshot()
    assert snapshot["storage"]["all_pools_healthy"] is False
    assert "Expected pool archive is missing" in snapshot["warnings"]
    assert "Expected pool apps is missing" in snapshot["warnings"]
    assert "Expected pool app-recovery is missing" in snapshot["warnings"]
