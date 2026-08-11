from __future__ import annotations

import json
import ssl
import uuid
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import websockets

from pnas.models import HardwareInventory
from pnas.truenas.base import require_supported_api


class TrueNASRPCError(RuntimeError):
    pass


class RealTrueNASAdapter:
    """Minimal JSON-RPC transport; inventory normalization is intentionally explicit."""

    def __init__(
        self,
        *,
        base_url: str,
        username: str,
        credential_file: Path,
        api_version_name: str,
        verify_tls: bool = True,
    ):
        require_supported_api(api_version_name)
        parsed = urlparse(base_url)
        if parsed.scheme != "https" or not parsed.hostname:
            raise ValueError("TrueNAS base URL must be HTTPS with a hostname")
        self.uri = f"wss://{parsed.netloc}/api/current"
        self.username = username
        self.credential_file = credential_file
        self.api_version_name = api_version_name
        self.ssl_context = ssl.create_default_context()
        if not verify_tls:
            self.ssl_context.check_hostname = False
            self.ssl_context.verify_mode = ssl.CERT_NONE

    def _credential(self) -> str:
        mode = self.credential_file.stat().st_mode & 0o777
        if mode & 0o077:
            raise PermissionError(
                "TrueNAS credential file must not be accessible by group or others"
            )
        return self.credential_file.read_text(encoding="utf-8").strip()

    async def _exchange(self, method: str, params: list[Any]) -> Any:
        async with websockets.connect(
            self.uri, ssl=self.ssl_context, max_size=16 * 1024 * 1024
        ) as ws:
            login_id = str(uuid.uuid4())
            await ws.send(
                json.dumps(
                    {
                        "jsonrpc": "2.0",
                        "id": login_id,
                        "method": "auth.login_ex",
                        "params": [
                            {
                                "mechanism": "API_KEY_PLAIN",
                                "username": self.username,
                                "api_key": self._credential(),
                            }
                        ],
                    }
                )
            )
            login = json.loads(await ws.recv())
            if login.get("error") or login.get("result", {}).get("response_type") != "SUCCESS":
                raise TrueNASRPCError("TrueNAS authentication failed")
            request_id = str(uuid.uuid4())
            await ws.send(
                json.dumps({"jsonrpc": "2.0", "id": request_id, "method": method, "params": params})
            )
            while True:
                response = json.loads(await ws.recv())
                if response.get("id") != request_id:
                    continue
                if "error" in response:
                    raise TrueNASRPCError(
                        f"TrueNAS call failed: {response['error'].get('message', 'error')}"
                    )
                return response.get("result")

    async def api_version(self) -> str:
        version = str(await self.call("system.version_short"))
        if not version.startswith("25.10"):
            raise TrueNASRPCError(f"server version {version} does not match configured API 25.10")
        return self.api_version_name

    async def call(self, method: str, params: list[Any] | None = None) -> Any:
        return await self._exchange(method, params or [])

    async def inventory(self) -> HardwareInventory:
        raise NotImplementedError(
            "real inventory normalization requires a hardware validation session; "
            "use preflight API probes"
        )
