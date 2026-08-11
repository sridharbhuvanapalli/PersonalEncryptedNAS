"""Read-only Tailscale diagnostics and deployment safety helpers."""

from pnas.tailscale.diagnostics import TailscaleReport, analyze_status

__all__ = ["TailscaleReport", "analyze_status"]
