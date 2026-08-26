# Application deployment

The source remains split into small Compose inputs for focused review. Production
renders those inputs into one `pnas-services` Compose document
and installs it through the supported TrueNAS Custom App API. Keeping the services in
one TrueNAS-managed application lets Nextcloud, Immich, private DNS, Caddy, and the
manager share fixed private networks without using an unsupported Docker CLI workflow
on the appliance. Tailscale remains a separate supported TrueNAS App.

Only Caddy and CoreDNS publish host ports, and only on validated service-LAN and
Tailscale addresses. PostgreSQL, Redis, and Valkey are isolated on internal networks.
The manager is isolated behind Caddy on `pnas_management`. There is no Docker socket.

Use `pnasctl hosting-deploy --target truenas-api` to preview the rendered application.
Execution requires the revision-specific confirmation and a short-lived API key whose
privilege includes `APPS_WRITE`, its read access, and `SYSTEM_GENERAL_READ`. Revoke that
deployment key after commissioning. There is no direct-Docker production or recovery
deployment path in this repository.

The default Caddy configuration uses an internal CA. The private-hosting workflow can
instead issue publicly trusted certificates through DNS-01 using a scoped Cloudflare
token or RFC2136 TSIG key. It does not create public service A/AAAA records. Maintain
private LAN DNS entries so local service continues during an ISP outage. Never forward
router ports 80 or 443. The custom proxy image is pinned to the security-fixed Caddy
2.11.4 release and immutable DNS-plugin commits. See
[private HTTPS hosting](private-hosting.md) and the
[production runbook](production-installation-runbook.md).

Use the supported TrueNAS Tailscale App. Enroll a tagged server,
require device approval and MFA/SSO, configure MagicDNS, remove lost devices, and
apply `config/tailscale/grants.hujson` after replacing placeholder identities. Family
users receive HTTPS only; administrators receive HTTPS and optional SSH.

Nextcloud requires per-user accounts, quotas, MFA, disabled anonymous public sharing,
and brute-force protection. Immich exclusively owns its upload library. An existing
photo collection may be mounted only through Immich's supported external-library
feature and should be read-only.

Sources: [Immich production Compose](https://docs.immich.app/install/docker-compose/),
[Immich v3.1.0 Compose](https://github.com/immich-app/immich/blob/v3.1.0/docker/docker-compose.yml),
[Nextcloud Docker image](https://hub.docker.com/_/nextcloud), and
[Tailscale access controls](https://tailscale.com/kb/1337/acl-syntax).
