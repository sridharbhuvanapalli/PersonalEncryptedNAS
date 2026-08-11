# Application deployment

Applications are independent Compose projects installed through supported TrueNAS
Custom Apps/YAML. Create fixed `pnas_private` and `pnas_management` networks, then
deploy Nextcloud, Immich, private DNS, proxy, and manager separately. Tailscale is a
required supported TrueNAS App for remote hosting, not an optional public-access path.

Only Caddy and CoreDNS publish host ports, and only on validated service-LAN and
Tailscale addresses. PostgreSQL, Redis, and Valkey are isolated on internal networks.
The manager is isolated behind Caddy on `pnas_management`. There is no Docker socket.

The default Caddy configuration uses an internal CA. The private-hosting workflow can
instead issue publicly trusted certificates through DNS-01 using a scoped Cloudflare
token or RFC2136 TSIG key. It does not create public service A/AAAA records. Maintain
private LAN DNS entries so local service continues during an ISP outage. Never forward
router ports 80 or 443. See [private HTTPS hosting](private-hosting.md).

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
