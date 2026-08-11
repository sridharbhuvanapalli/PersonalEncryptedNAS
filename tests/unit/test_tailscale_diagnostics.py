from pnas.tailscale.diagnostics import analyze_status


def test_status_distinguishes_direct_relayed_and_offline_peers() -> None:
    report = analyze_status(
        {
            "BackendState": "Running",
            "Self": {
                "Online": True,
                "DNSName": "family-nas.example.ts.net.",
                "TailscaleIPs": ["100.100.1.2"],
            },
            "Peer": {
                "a": {"DNSName": "direct", "Online": True, "CurAddr": "203.0.113.1:41641"},
                "b": {"DNSName": "relay", "Online": True, "Relay": "nyc"},
                "c": {"DNSName": "away", "Online": False},
            },
        }
    )
    assert report.direct_peers == 1
    assert report.relayed_peers == 1
    assert "DERP" in report.warnings[0]
    assert [peer.connection for peer in report.peers] == ["offline", "direct", "relayed"]


def test_status_fails_closed_when_self_identity_is_missing() -> None:
    report = analyze_status({"BackendState": "Stopped"})
    assert report.self_online is False
    assert len(report.warnings) == 2
