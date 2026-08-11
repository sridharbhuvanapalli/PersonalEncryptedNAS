# Security policy

Do not report vulnerabilities in a public issue. Contact the private maintainer
and include affected versions, reproduction steps, and impact without including
real credentials, family data, encryption keys, or support bundles.

## Invariants

- No public router ports or public tunnels.
- Tailscale hosting uses host/kernel mode; userspace proxy mode is not production ingress.
- No Tailscale Funnel, exit-node advertising, public service A/AAAA record, or DDNS dependency.
- HTTPS is mandatory for a real TrueNAS adapter.
- API credentials are read from restrictive secret files.
- PostgreSQL and Redis ports are never published.
- No Docker socket mount or arbitrary browser-accessible command execution.
- The Operations Manager accepts proxy headers only from its dedicated Caddy network.
- Mutations require a reviewed plan, reauthentication, exact confirmation, and audit.
- Logs and support bundles use field allowlists and redact credentials and tokens.
- Encryption keys must have verified offline copies; the NAS must not hold the only copy.

Dependency and image findings rated high or critical block release until remediated
or explicitly documented with a compensating control and expiry date.
