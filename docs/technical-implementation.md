# Technical implementation

## System purpose and limits

This project deploys a private family NAS on TrueNAS Community Edition with encrypted
ZFS datasets, Nextcloud, Immich, private HTTPS, Tailscale remote access, encrypted
Restic backups, and a read-only Operations Manager.

It is not end-to-end encrypted while datasets are unlocked. A TrueNAS administrator
can read ordinary Nextcloud and Immich content. Client-side encryption is required for
content that must remain unreadable to the NAS administrator, but Immich cannot index,
search, thumbnail, or recognize faces in client-side encrypted media.

Immich facial recognition groups and searches photos. It is not a login or identity
control. User security comes from tailnet membership, device approval, application
accounts, MFA, authorization, and audit.

## Network and trust boundaries

```text
Authorized device
  -> Tailscale/WireGuard
  -> family-nas tailnet address
  -> Caddy :443 on the Tailscale address
  -> Nextcloud / Immich / Operations Manager

LAN client
  -> private LAN DNS
  -> dedicated service LAN address
  -> Caddy :443

Let's Encrypt
  -> public Cloudflare authoritative DNS TXT lookup only
  -> no HTTP connection to the NAS
```

The Verizon FiOS WAN address is not in configuration. All peer connections originate
outbound and Tailscale negotiates a direct UDP path where possible. DERP is an encrypted
fallback with lower expected throughput. No DDNS client, router port forwarding, UPnP,
Tailscale Funnel, Cloudflare Tunnel, or public service origin is used.

Network separation:

| Network/address | Members and purpose |
|---|---|
| Management LAN, e.g. `192.168.1.10` | TrueNAS UI and appliance administration |
| Service LAN, e.g. `192.168.1.20` | Caddy 443 and LAN CoreDNS 53 |
| Tailscale `100.64.0.0/10` address | Remote Caddy 443 and tailnet CoreDNS 53 |
| `pnas_private`, e.g. `172.30.0.0/24` | Caddy, Nextcloud, and Immich application traffic |
| `pnas_management`, e.g. `172.31.0.0/28` | Caddy-to-Operations-Manager only |
| Application backend networks | Internal PostgreSQL, Redis/Valkey, ML, and cron traffic |

Only Caddy and CoreDNS publish host ports, always on explicitly validated private
addresses. Databases, caches, and the Operations Manager do not publish ports.

## Private names and certificates

The private service suffix is `nas.cloudpathz.com`:

- `cloud.nas.cloudpathz.com` — Nextcloud
- `photos.nas.cloudpathz.com` — Immich
- `ops.nas.cloudpathz.com` — Operations Manager

Two CoreDNS views are generated in every hosting revision. LAN records return the
service LAN address; tailnet records return the Tailscale address. Tailscale split DNS
for only `nas.cloudpathz.com` points to the tailnet CoreDNS listener. Public Cloudflare
DNS does not receive persistent A/AAAA records for these services.

Caddy uses the scoped Cloudflare API token only to create and remove ACME DNS-01 TXT
records. The token file must be mode 0600 and contains only the token. Global API keys
are rejected.

## Storage layout

```text
tank                         four 18 TB HC550 SAS 512e disks, RAIDZ2
├── family-files             encrypted root
│   └── nextcloud-data
├── family-photos            encrypted root
│   └── immich-library
├── database-dumps           encrypted root
└── local-backups            encrypted root

archive                      four 3 TB DT01ACA300 SATA 512e disks, RAIDZ2

apps                         Inland TN320 1 TB NVMe, single-device initially
├── app-config
├── databases
└── immich-generated

app-recovery                 Inland 512 GB SATA SSD, separate single-device pool
├── database-dumps
├── app-config-exports
└── hosting-revisions
```

Both pools use independently reviewed four-wide RAIDZ2 plans. The archive plan creates
a new pool and never extends `tank`. Real pool mutation remains disabled until live
inventory normalization and hardware validation are completed. Use the TrueNAS UI for
the reviewed initial deployment while preserving the serial-verification checklist.

The JONSBO N5 provides 12 hot-swap 3.5-inch bays; eight are initially populated and
four remain empty. The Samsung PM830 128 GB SATA SSD is dedicated to TrueNAS boot. The
Inland TN320 1 TB NVMe is the initial Apps device. The Inland 512 GB SATA SSD is a
separate `app-recovery` pool; it is not paired with the TN320 or added to a data pool.
Because both start as single-device pools, critical recovery content also goes to
encrypted offsite Restic storage.

When a second ≥1 TB NVMe is purchased, attach it to the existing TN320 vdev as a mirror
member. The `apps` pool/dataset names remain unchanged, so application, Caddy, Tailscale,
DNS, and Compose paths do not migrate. The change is complete only after resilver,
scrub, application checks, and a restore test pass.

Physical connections are deliberately asymmetric: one genuine LSI SAS 9300-8i
SFF-8643 port uses a forward four-lane breakout to four individual N5 backplane data
ports for the HC550s, while four motherboard SATA ports serve four archive backplane
ports. The second HBA port is reserved for up to four future SAS disks; physical
capacity does not authorize a ZFS expansion, which requires its own topology and backup
review. The N5 backplane path must prove SAS enumeration and stable I/O before `tank`
is created.

The N5 supplies three rear 120 mm fans. They remain installed for commissioning, but a
separate directed airflow path is required over the passively cooled 9300-8i. A 75 cm
forward breakout is preferred; 60–100 cm is acceptable when routed without sharp bends
or airflow obstruction. Final intake-fan population is determined by simultaneous
eight-drive and HBA burn-in rather than chassis fan-slot count alone.

## Configuration and deployment

1. Create the development environment:

   ```console
   python3 -m venv .venv
   . .venv/bin/activate
   python -m pip install -e '.[dev]'
   make check
   ```

2. Copy `config/pnas.example.yaml` to `config/pnas.yaml`. Replace addresses, serials,
   administrator email, TrueNAS URL, and credential path. Keep every false-valued
   public-exposure invariant unchanged.

   Keep the storage identity constraints intact: `tank` requires four 18 TB SAS 512e
   HC550/WUH721818 drives, and `archive` requires four 3 TB SATA 512e DT01ACA300 drives.

3. Create fixed application networks once:

   ```console
   docker network create --driver bridge --subnet 172.30.0.0/24 pnas_private
   docker network create --driver bridge --subnet 172.31.0.0/28 pnas_management
   ```

4. Install the supported TrueNAS Tailscale App using
   [tailscale deployment](tailscale-deployment.md).

5. Configure private hosting after the NAS has its stable Tailscale address:

   ```console
   pnasctl --config config/pnas.yaml hosting-configure \
     --base-domain nas.cloudpathz.com \
     --nextcloud-url https://cloud.nas.cloudpathz.com \
     --immich-url https://photos.nas.cloudpathz.com \
     --manager-url https://ops.nas.cloudpathz.com \
     --management-lan-address 192.168.1.10 \
     --lan-address 192.168.1.20 \
     --tailscale-address 100.64.0.2 \
     --email OWNER_EMAIL \
     --provider cloudflare \
     --zone cloudpathz.com \
     --credential-file /mnt/apps/secrets/cloudflare-dns-token \
     --certificate-environment staging
   pnasctl --config config/pnas.yaml hosting-provider-check
   ```

6. Perform the explicitly confirmed temporary DNS write test, create the hosting plan,
   review it, and apply it. Use the exact confirmation strings printed by the commands.

7. Load the generated deployment environment and deploy DNS before Caddy:

   ```console
   set -a
   . var/hosting/revisions/PLAN_ID/deployment.env
   . compose/proxy/.env
   set +a
   scripts/compose-with-secrets compose/dns config
   scripts/compose-with-secrets compose/dns up -d
   scripts/compose-with-secrets compose/proxy config
   scripts/compose-with-secrets compose/proxy up -d --build
   ```

8. Verify staging certificates from a LAN and an external tailnet client. Change the
   certificate environment to production, generate a fresh plan/revision, and redeploy.

## Operations Manager design

The manager supports `mock`, `live`, and `degraded` states. Live mode makes only
read-role JSON-RPC calls: TrueNAS version, pools, disks, applications, and active
alerts. Calls are timeout-bounded and a failure produces a timestamped degraded view
without including exception text.

The manager is conventional deterministic automation rather than an AI agent. It has no
LLM, autonomous goal loop, self-modifying policy, or authority to improvise or execute
remediation. Its role is observation, rule-based warnings, and recording reviewed
change intent for a separate human-confirmed workflow.

The manager receives its API key from a read-only secret file. SQLite contains only
observations and audit metadata. Login requires a scrypt password and optional TOTP;
sessions are HMAC-signed, one hour, Secure, HttpOnly, and SameSite Strict. CSRF and
password reauthentication protect action planning.

The web UI does not execute backup restores, updates, pool creation/expansion, or other
mutations. It creates a reviewed intent; the corresponding CLI workflow provides the
separate plan, confirmation, and audit gate.

The existing UniFi Network control plane stays on the laptop through initial NAS
commissioning so a NAS outage cannot simultaneously remove storage and network-control
visibility. A later migration to a supported TrueNAS App or custom container is allowed
only as a separately reviewed optional workload after the storage and recovery gates
pass. This repository does not currently deploy UniFi. Any later deployment must import
a verified configuration backup, pin its revision, expose no WAN port, and limit its
management interface to the trusted LAN and administrator tailnet policy.

## Security failure modes

- Compromised family device: revoke it in Tailscale immediately and rotate its app
  sessions; grants limit it to DNS and HTTPS.
- Cloudflare token loss: revoke and replace the scoped token; the token cannot create a
  public tunnel and should be limited to one zone.
- Tailscale outage: existing LAN service DNS and Caddy remain usable locally.
- FiOS outage: local services continue; remote service is unavailable until WAN returns.
- Manager API failure: dashboard becomes degraded; it never substitutes fabricated live
  values.
- Locked or lost ZFS key: offline recovery key is required. No software can recover a
  lost sole key.
- RAIDZ2 degradation: stop nonessential writes, identify by serial, replace one disk at
  a time, and never remove a second uncertain disk during resilver.
