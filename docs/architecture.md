# Architecture

## ADR-001: TrueNAS Community Edition over Ubuntu Server

**Status:** Accepted, 2026-08-06.

Use the latest maintenance release recommended by the official TrueNAS Software
Status page (25.10.5 when this decision was recorded). Do not deploy beta releases
for family data.

TrueNAS was chosen because it provides native OpenZFS and RAIDZ2 administration,
encrypted datasets, SMART and scrub scheduling, snapshots and replication, UPS/NUT
integration, storage-focused alerts, and supported Apps and Docker Compose. This
reduces the risk of assembling and maintaining equivalent storage controls by hand
on Ubuntu. The project never installs packages, binaries, or services into the
TrueNAS base OS; management runs on a trusted workstation or supported container.

## Storage topology

Phase 1 creates one four-drive RAIDZ2 vdev. Phase 2 adds another four-drive
RAIDZ2 vdev to the same pool. It never adds single-disk stripes. Losing an entire
data vdev loses the pool; each four-drive RAIDZ2 vdev tolerates any two failures
within that vdev. Adding a vdev is treated as a permanent architecture change.

The pool root remains unencrypted. Independent encrypted dataset roots are created
for family files, photos, database dumps, and local backups. The separate `apps`
SSD pool holds databases, caches, thumbnails, encoded video, logs, and container
state. Original files and photos remain on `tank`.

The acquired first-stage layout is one four-disk RAIDZ2 vdev made from four equal
12 TB or four equal 16 TB enterprise SATA CMR disks. Two 3 TB disks form a separate
archive mirror administered through TrueNAS; the third 3 TB disk is an offline cold
spare. The automation does not model or create that mirror.

## ADR-002: Tailnet-only remote access

**Status:** Accepted, 2026-08-11.

Remote access uses the supported TrueNAS Tailscale App with host networking enabled and
userspace networking disabled. The NAS is a tagged, persistent node. Family users receive
private DNS and HTTPS; administrators additionally receive optional non-root SSH.

The Verizon residential WAN address is not an input. There is no DDNS, router forwarding,
UPnP, Funnel, exit-node advertisement, Cloudflare Tunnel, or public service origin.
Cloudflare is authoritative for `cloudpathz.com` and services ACME DNS-01 only. Two
CoreDNS views answer `nas.cloudpathz.com` privately for LAN and tailnet clients.

## ADR-003: Separate manager proxy network

**Status:** Accepted, 2026-08-11.

The Operations Manager publishes no host port and joins only `pnas_management`. Caddy
joins both the application ingress and management networks. The manager accepts forwarded
client identity only from the exact management network; Nextcloud and Immich containers
cannot directly reach or impersonate the trusted proxy.

## Management boundary

TrueNAS remains authoritative for storage state and safety. `pnas-install` creates
inventory-bound plans and applies only explicitly supported API operations.
`pnasctl` and the Operations Manager default to read-only. The manager never stores
service passwords, API tokens, application data, or encryption keys in SQLite.

TrueNAS 25.10 uses a versioned JSON-RPC 2.0 WebSocket API. The adapter authenticates
with `auth.login_ex` using an API key over verified TLS, verifies the API version,
and fails closed on versions outside the explicit compatibility set.

## Capacity model

| Configuration | Raw decimal TB | Nominal RAIDZ2 TB | Approx. TiB | 80% target TiB |
|---|---:|---:|---:|---:|
| 4 × 12TB | 48 | 24 | 21.8 | 17.5 |
| 8 × 12TB | 96 | 48 | 43.7 | 34.9 |
| 4 × 16TB | 64 | 32 | 29.1 | 23.3 |
| 8 × 16TB | 128 | 64 | 58.2 | 46.6 |

Manufacturers advertise decimal TB while TrueNAS commonly presents binary TiB.
Metadata, reservations, snapshots, and application data further reduce free space.
The 80% figure is an operational ceiling, not promised usable capacity. RAIDZ2 and
snapshots are not backups.

## Sources

- [TrueNAS Software Status](https://www.truenas.com/docs/softwarestatus/)
- [TrueNAS API](https://api.truenas.com/)
- [TrueNAS 25.10 API authentication](https://api.truenas.com/v25.10/api_methods_auth.login_ex.html)
- [TrueNAS dataset encryption](https://www.truenas.com/docs/scale/datasets/encryption/encryptingdatasets/)
- [TrueNAS Custom Apps](https://apps.truenas.com/managing-apps/installing-custom-apps/)
- [TrueNAS remote access](https://www.truenas.com/docs/solutions/remoteaccess/)
- [Tailscale grants](https://tailscale.com/docs/features/access-control/grants)
- [Tailscale DNS](https://tailscale.com/docs/reference/dns-in-tailscale)
