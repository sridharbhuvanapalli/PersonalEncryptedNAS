from __future__ import annotations

from typing import Any, Protocol


class TrueNASAppDeploymentError(RuntimeError):
    pass


class TrueNASJobAdapter(Protocol):
    async def api_version(self) -> str: ...

    async def call(self, method: str, params: list[Any] | None = None) -> Any: ...

    async def call_job(
        self,
        method: str,
        params: list[Any],
        *,
        timeout_seconds: int = 900,
        poll_seconds: float = 1.0,
    ) -> Any: ...


async def deploy_custom_app(
    adapter: TrueNASJobAdapter,
    compose_yaml: str,
    *,
    app_name: str = "pnas-services",
) -> dict[str, str]:
    """Create or update one TrueNAS-managed Custom App and verify its final state."""
    api_version = await adapter.api_version()
    existing = await adapter.call("app.query", [[["id", "=", app_name]]])
    if not isinstance(existing, list):
        raise TrueNASAppDeploymentError("TrueNAS app inventory returned an invalid response")
    if len(existing) > 1:
        raise TrueNASAppDeploymentError("TrueNAS returned duplicate application identities")
    if existing and existing[0].get("custom_app") is not True:
        raise TrueNASAppDeploymentError("refusing to replace a catalog-managed application")
    if existing:
        action = "updated"
        await adapter.call_job(
            "app.update",
            [app_name, {"custom_compose_config_string": compose_yaml}],
        )
    else:
        action = "created"
        await adapter.call_job(
            "app.create",
            [
                {
                    "app_name": app_name,
                    "custom_app": True,
                    "custom_compose_config_string": compose_yaml,
                }
            ],
        )
    deployed = await adapter.call("app.query", [[["id", "=", app_name]]])
    if not isinstance(deployed, list) or len(deployed) != 1:
        raise TrueNASAppDeploymentError("deployed application is missing from TrueNAS inventory")
    state = str(deployed[0].get("state", "UNKNOWN"))
    if state != "RUNNING":
        raise TrueNASAppDeploymentError(f"deployed application state is {state}, expected RUNNING")
    return {
        "application": app_name,
        "action": action,
        "state": state,
        "api_version": api_version,
    }
