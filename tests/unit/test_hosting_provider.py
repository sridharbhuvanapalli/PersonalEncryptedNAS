from pathlib import Path

import httpx
import pytest

from pnas.config import HostingDNSConfig
from pnas.hosting.providers import CloudflareProvider


@pytest.mark.asyncio
async def test_cloudflare_check_and_temporary_write_are_scoped_and_cleaned_up(
    tmp_path: Path,
) -> None:
    token_file = tmp_path / "token"
    token_file.write_text("scoped-api-token", encoding="utf-8")
    token_file.chmod(0o600)
    calls: list[tuple[str, str]] = []
    content = ""

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal content
        assert request.headers["Authorization"] == "Bearer scoped-api-token"
        calls.append((request.method, request.url.path))
        if request.url.path == "/client/v4/user/tokens/verify":
            return httpx.Response(200, json={"success": True, "result": {"status": "active"}})
        if request.url.path == "/client/v4/zones":
            return httpx.Response(
                200, json={"success": True, "result": [{"id": "zone-1", "name": "example.com"}]}
            )
        if request.method == "POST":
            content = str(request.content)
            return httpx.Response(200, json={"success": True, "result": {"id": "record-1"}})
        if request.method == "GET":
            marker = content.split('"content":"', 1)[1].split('"', 1)[0]
            return httpx.Response(200, json={"success": True, "result": [{"content": marker}]})
        return httpx.Response(200, json={"success": True, "result": {}})

    config = HostingDNSConfig(provider="cloudflare", zone="example.com", credential_file=token_file)
    client = httpx.AsyncClient(
        base_url="https://api.cloudflare.com/client/v4",
        headers={"Authorization": "Bearer scoped-api-token"},
        transport=httpx.MockTransport(handler),
    )
    provider = CloudflareProvider(config, client=client)
    assert (await provider.verify())["zone_visible"] is True
    result = await provider.write_test()
    assert result["deleted"] is True
    assert calls[-1] == (
        "DELETE",
        "/client/v4/zones/zone-1/dns_records/record-1",
    )
    await client.aclose()
