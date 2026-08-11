from __future__ import annotations

import socket
import ssl
from datetime import UTC, datetime


def certificate_status(hostname: str, address: str, port: int = 443) -> dict[str, object]:
    context = ssl.create_default_context()
    with socket.create_connection((address, port), timeout=10) as connection:
        with context.wrap_socket(connection, server_hostname=hostname) as tls:
            certificate = tls.getpeercert()
    if certificate is None:
        raise RuntimeError("peer did not provide a certificate")
    expires_raw = certificate.get("notAfter")
    if not isinstance(expires_raw, str):
        raise RuntimeError("peer certificate did not include an expiry time")
    expires = datetime.strptime(expires_raw, "%b %d %H:%M:%S %Y %Z").replace(tzinfo=UTC)
    return {
        "hostname": hostname,
        "address": address,
        "port": port,
        "expires_at": expires.isoformat(),
        "days_remaining": (expires - datetime.now(UTC)).days,
    }
