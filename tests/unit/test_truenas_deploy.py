from typing import Any

import pytest

from pnas.applications.truenas_deploy import (
    TrueNASAppDeploymentError,
    deploy_custom_app,
)


class FakeAdapter:
    def __init__(self, existing: list[dict[str, Any]]):
        self.existing = existing
        self.jobs: list[tuple[str, list[Any]]] = []

    async def api_version(self) -> str:
        return "25.10"

    async def call(self, method: str, params: list[Any] | None = None) -> Any:
        assert method == "app.query"
        return self.existing

    async def call_job(
        self,
        method: str,
        params: list[Any],
        *,
        timeout_seconds: int = 900,
        poll_seconds: float = 1.0,
    ) -> Any:
        self.jobs.append((method, params))
        self.existing = [{"id": "pnas-services", "custom_app": True, "state": "RUNNING"}]
        return None


@pytest.mark.asyncio
async def test_create_custom_app_uses_supported_api_job() -> None:
    adapter = FakeAdapter([])
    result = await deploy_custom_app(adapter, "services: {}\n")
    assert result["action"] == "created"
    assert adapter.jobs[0][0] == "app.create"
    payload = adapter.jobs[0][1][0]
    assert payload["custom_app"] is True
    assert payload["custom_compose_config_string"] == "services: {}\n"


@pytest.mark.asyncio
async def test_update_custom_app_and_refuse_catalog_collision() -> None:
    adapter = FakeAdapter([{"id": "pnas-services", "custom_app": True, "state": "RUNNING"}])
    result = await deploy_custom_app(adapter, "services: {}\n")
    assert result["action"] == "updated"
    assert adapter.jobs[0][0] == "app.update"

    catalog = FakeAdapter(
        [{"id": "pnas-services", "custom_app": False, "state": "RUNNING"}]
    )
    with pytest.raises(TrueNASAppDeploymentError, match="catalog-managed"):
        await deploy_custom_app(catalog, "services: {}\n")
