from __future__ import annotations

from typing import Any, Literal

from pydantic import Field

from pnas.models import StrictModel


class PeerConnection(StrictModel):
    dns_name: str
    online: bool
    connection: Literal["direct", "relayed", "idle", "offline"]
    endpoint: str | None = None
    relay: str | None = None


class TailscaleReport(StrictModel):
    backend_state: str
    self_online: bool
    self_dns_name: str
    tailscale_ips: tuple[str, ...]
    peers: tuple[PeerConnection, ...]
    direct_peers: int = Field(ge=0)
    relayed_peers: int = Field(ge=0)
    warnings: tuple[str, ...]


def _peer_connection(peer: dict[str, Any]) -> PeerConnection:
    online = bool(peer.get("Online", False))
    endpoint = str(peer.get("CurAddr") or "").strip() or None
    relay = str(peer.get("Relay") or "").strip() or None
    if not online:
        connection: Literal["direct", "relayed", "idle", "offline"] = "offline"
    elif endpoint:
        connection = "direct"
    elif relay:
        connection = "relayed"
    else:
        connection = "idle"
    return PeerConnection(
        dns_name=str(peer.get("DNSName") or peer.get("HostName") or "unknown").rstrip("."),
        online=online,
        connection=connection,
        endpoint=endpoint,
        relay=relay,
    )


def analyze_status(payload: dict[str, Any]) -> TailscaleReport:
    """Normalize `tailscale status --json` without retaining keys or user profiles."""
    self_data = payload.get("Self")
    if not isinstance(self_data, dict):
        self_data = {}
    peer_data = payload.get("Peer")
    raw_peers = peer_data.values() if isinstance(peer_data, dict) else ()
    peers = tuple(
        sorted(
            (_peer_connection(peer) for peer in raw_peers if isinstance(peer, dict)),
            key=lambda peer: peer.dns_name,
        )
    )
    direct = sum(peer.connection == "direct" for peer in peers)
    relayed = sum(peer.connection == "relayed" for peer in peers)
    backend_state = str(payload.get("BackendState") or "Unknown")
    self_online = bool(self_data.get("Online", backend_state == "Running"))
    warnings: list[str] = []
    if backend_state != "Running" or not self_online:
        warnings.append("Tailscale node is not online")
    if relayed:
        warnings.append(
            f"{relayed} peer connection(s) are using DERP relay; verify NAT traversal and UDP"
        )
    ips = self_data.get("TailscaleIPs")
    tailscale_ips = tuple(str(value) for value in ips) if isinstance(ips, list) else ()
    if not tailscale_ips:
        warnings.append("Tailscale node has no assigned address")
    return TailscaleReport(
        backend_state=backend_state,
        self_online=self_online,
        self_dns_name=str(
            self_data.get("DNSName") or self_data.get("HostName") or "unknown"
        ).rstrip("."),
        tailscale_ips=tailscale_ips,
        peers=peers,
        direct_peers=direct,
        relayed_peers=relayed,
        warnings=tuple(warnings),
    )
