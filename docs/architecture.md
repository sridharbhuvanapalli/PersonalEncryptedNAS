# Architecture

## ADR-001: TrueNAS Community Edition over Ubuntu Server

**Status:** Accepted, 2026-08-06.

Use the latest maintenance release recommended by the official TrueNAS Software
Status page (25.10.4 when revalidated on 2026-08-12). Do not deploy beta releases
for family data.

TrueNAS was chosen because it provides native OpenZFS and RAIDZ2 administration,
encrypted datasets, SMART and scrub scheduling, snapshots and replication, UPS/NUT
integration, storage-focused alerts, and supported Apps and Docker Compose. This
reduces the risk of assembling and maintaining equivalent storage controls by hand
on Ubuntu. The project never installs packages, binaries, or services into the
TrueNAS base OS; management runs on a trusted workstation or supported container.

## Storage topology

Phase 1 creates `tank` from four WD Ultrastar DC HC550 18 TB SAS 512e disks in one
RAIDZ2 vdev. Phase 2 creates `archive` as an independent pool from four Toshiba
DT01ACA300 3 TB SATA 512e disks in one RAIDZ2 vdev. The archive vdev is never added to
`tank`. Each pool tolerates any two member-drive failures; losing an entire vdev loses
only its own pool, not the other pool.

The pool root remains unencrypted. Independent encrypted dataset roots are created
for family files, photos, database dumps, and local backups. The separate `apps`
SSD pool holds databases, caches, thumbnails, encoded video, logs, and container
state. Original files and photos remain on `tank`.

`tank` holds active originals and protected datasets. `archive` holds archival data but
is not a backup merely because it is a separate pool in the same chassis. The older
desktop Toshiba drives require full burn-in, closer monitoring, and independent backup.
The automation models both pool plans but leaves real destructive mutation disabled
until live inventory normalization and hardware validation are complete.

The platform uses the JONSBO N5's 12 hot-swap HDD bays with eight initially populated.
TrueNAS boots from the Samsung PM830 128 GB SATA SSD. The Inland TN320 1 TB NVMe holds
the initial single-device `apps` pool. The Inland 512 GB SATA SSD forms a separate
single-device `app-recovery` pool for local database/configuration recovery copies.
Neither single-device pool is redundant, and `app-recovery` is not an offsite backup.

The four SAS members of `tank` use one port of a genuine LSI SAS 9300-8i in P16 IT/HBA
mode through a forward SFF-8643-to-4 × 7-pin breakout. The four SATA archive members and
two SATA SSDs occupy all six motherboard SATA ports. The HBA's second SFF-8643 port is
reserved for at most four future SAS disks, but that physical headroom does not approve
or define a future ZFS topology.

A future NVMe with at least 1 TB usable capacity is attached to the TN320's existing
data vdev to convert `apps` from a one-device stripe into a two-device mirror. This does
not change the pool name, datasets, host paths, application configuration, or usable
capacity. Adding the future NVMe as a new top-level striped vdev is prohibited because
either SSD failure would then destroy the pool.

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
| `tank`: 4 × 18 TB | 72 | 36 | 32.7 | 26.2 |
| `archive`: 4 × 3 TB | 12 | 6 | 5.46 | 4.37 |

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
- [WD Ultrastar DC HC550 data sheet](https://documents.westerndigital.com/content/dam/doc-library/en_us/assets/public/western-digital/product/data-center-drives/ultrastar-dc-hc500-series/data-sheet-ultrastar-dc-hc550.pdf)
- [Toshiba DT01ACA product overview](https://storage.toshiba.com/docs/desktop-pc-hard-drive-documents/dt01aca-product-overview.pdf)
