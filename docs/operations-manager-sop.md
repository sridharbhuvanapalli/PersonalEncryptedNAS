# Operations Manager standard operating procedure

## Purpose

The Operations Manager is the private, read-only daily view of NAS health. It summarizes
TrueNAS pool, disk, application, alert, capacity, and optional Tailscale observations.
It does not replace the TrueNAS UI, backup logs, or recovery documentation, and it does
not directly execute storage, restore, update, or expansion mutations.

It is deterministic safety-gated automation, not an autonomous AI agent: it does not use
an LLM, invent remediation, change its own policy, or execute a plan on its own. Human
review, the relevant runbook, an explicit CLI confirmation, and the implementation's
safety gates remain required for every supported change.

## Initial setup

1. Create a TrueNAS automation user with only the roles required to read system version,
   pools, disks, applications, and alerts. Prefer the built-in read-only administrator
   role, then reduce it if the installed TrueNAS version supports a narrower privilege.
2. Create its API key and save only the key in a mode-0600 file. Do not reuse a full
   administrator key.
3. Set `truenas.adapter: real` in the production `pnas.yaml`, keep HTTPS verification
   enabled, and point `credential_file` to `/run/secrets/truenas_api_token`.
4. Create manager secrets interactively:

   ```console
   pnasctl manager-init-secrets --output-dir /mnt/apps/secrets/manager
   ```

5. Open the mode-0600 `manager-totp-enrollment-uri` file on a trusted local workstation,
   enroll it in an authenticator, and retain the TOTP recovery secret in the offline
   recovery package. After a successful login, securely remove only the enrollment URI
   convenience file. Do not remove the runtime TOTP secret.
6. Copy `compose/manager/env.example` to `.env` and set:
   - manager state and secret paths;
   - production `pnas.yaml` path;
   - read-only TrueNAS API token path;
   - `PNAS_MANAGER_ALLOWED_NETWORKS=172.31.0.0/28`;
   - `PNAS_MANAGER_TRUSTED_PROXY_NETWORKS=172.31.0.0/28`;
   - `PNAS_MANAGER_HEALTH_MODE=live`.
7. Confirm `pnas_management` was created with exactly the documented subnet and contains
   only Caddy and the manager.
8. Validate and start:

   ```console
   docker compose --project-directory compose/manager -f compose/manager/compose.yaml config
   docker compose --project-directory compose/manager -f compose/manager/compose.yaml up -d --build
   ```

9. Open `https://ops.nas.cloudpathz.com` first from LAN and then from an approved remote
   Tailscale client. Direct container access must fail because the manager publishes no
   host port.

## Sign-in procedure

1. Confirm Tailscale is connected when remote.
2. Confirm the browser address is exactly `https://ops.nas.cloudpathz.com` with a valid
   certificate.
3. Enter the manager password and current six-digit authenticator code.
4. Never bypass a certificate warning or enter the credential into an IP-address URL.
5. Sign out when finished. Sessions expire after one hour, but logout invalidates the
   browser cookie immediately.

Five login attempts within five minutes trigger the in-process rate limiter. Repeated
failures are an incident signal, not a reason to weaken the password or TOTP requirement.

## Read the dashboard

Always start with the status line:

| Field | Meaning | Required action |
|---|---|---|
| `Mode: live` | Data came from the read-only TrueNAS API | Continue review |
| `Mode: mock` | Fixture data only | Do not make operational conclusions |
| `Mode: degraded` | Collection failed | Use TrueNAS UI locally and investigate immediately |
| `STALE` | Current collection is unavailable | Treat displayed prior/empty values as untrusted |
| Captured timestamp | Time the snapshot completed | Investigate unexpected age or clock skew |

Review panels in this order:

1. Warnings and active TrueNAS alerts.
2. `tank`, `archive`, `apps`, and `app-recovery` status, health, active scrub/resilver,
   and utilization. All expected pools must be present and healthy; one green pool does
   not mask a missing or degraded pool.
3. Disk count and disk warnings.
4. Nextcloud, Immich, proxy, database, and cache application states.
5. Backup and restore-test freshness.
6. UPS state and available runtime.
7. Tailscale online/direct/relayed observation.
8. Certificate expiry and available updates.

Never clear an alert merely to make the dashboard green. Record its cause, evidence,
action, and resolution time.

## Routine schedule

### Daily

- Confirm live, non-stale collection.
- Check all four pools ONLINE/healthy and no active unexpected resilver.
- Review new critical alerts and service failures.
- Confirm the latest encrypted backup completed.
- Confirm each pool remains below its 70 percent warning and 80 percent ceiling.

### Weekly

- Review disk temperatures and SMART warnings.
- Review HBA/controller and SAS-link alerts; investigate resets, missing WWNs, or rising
  interface-error counts immediately, and physically confirm HBA airflow.
- Check Nextcloud and Immich background jobs.
- Confirm certificate renewal and private DNS from one LAN and one tailnet client.
- Review failed logins and manager audit events.
- Check `tailscale ping family-nas` from an external network when practical.

### Monthly

- Review both scrub results and the staggered SMART long-test schedule. Never overlap
  all-disk long tests with either pool's scrub or resilver.
- Confirm nightly database/configuration exports reached `app-recovery`, then verify the
  same critical recovery set reached encrypted offsite storage.
- Review Tailscale users, groups, approved devices, duplicates, and inactive machines.
- Perform a selected-file Restic restore to a temporary location and verify its hash.
- Review TrueNAS and application updates without installing them automatically.
- Check UPS self-test/battery information and physical dust/temperature condition.
- Confirm the three included rear fans and any added HBA/HDD fans are operating and that
  cabling has not shifted into a fan path.

### Quarterly

- Restore Nextcloud and Immich database dumps into an isolated test environment.
- Test one lost-file snapshot recovery.
- Review offline ZFS keys, TOTP recovery, Cloudflare recovery, and Tailscale ownership.
- Review the hardware serial/bay map and spare availability.

## Change-plan workflow

The dashboard actions `backup`, `restore-test`, `update`, and `expansion` require the
current CSRF token and password reauthentication. A successful response means only that
the intent was recorded; `executed` remains false.

1. Create the action plan in the manager.
2. Read the corresponding runbook and current system evidence.
3. Use the CLI planning command on a trusted management workstation.
4. Review the plan ID, expiry, inventory fingerprint, serials, preconditions, and exact
   confirmation phrase.
5. Apply only during the approved maintenance window.
6. Verify outcome and record it in the offline operations log.

For the planned phase-2 storage action, use `archive-preflight`, `archive-plan`, and
`archive-apply`. The reviewed plan must create the independent `archive` pool from the
four 3 TB Toshiba serials; cancel any plan that adds them to `tank`.

Real destructive pool application remains blocked by this software until live inventory
normalization and a hardware validation session are complete. Do not bypass that guard.

### Future Apps mirror change

The future second ≥1 TB NVMe is a reviewed storage maintenance action. Follow the
[transplant guide procedure](build-and-transplant-guide.md#10-add-the-future-1-tb-nvme-apps-mirror).
The accepted end state is one two-device mirror vdev in the existing `apps` pool. The
pool name, datasets, paths, and application configuration stay unchanged. A new striped
top-level vdev is a rejection condition. Record pre-change backups, exact SSD serials,
resilver completion, scrub results, application checks, restore evidence, and final
topology in the audit log.

## Incident procedures

### Manager shows degraded

1. Do not restart every service blindly.
2. Open TrueNAS locally through the management address.
3. Check the manager container logs for error type only; never paste secrets into logs.
4. Verify TrueNAS TLS, read-only API role/key, manager configuration mount, DNS, and time.
5. Restore live mode only after the root cause is understood.

### Pool degraded or disk fault

1. Stop large imports and nonessential write-heavy applications.
2. Record which pool is affected, plus pool status, alerts, affected
   GUID, stable ID, serial, bay, interface, and SMART result.
3. Confirm the backup is current without running a competing full backup during a
   fragile resilver unless risk analysis requires it.
4. Identify the physical disk twice. Never act on `/dev/sdX` alone.
5. Follow the TrueNAS replace procedure for one confirmed disk.
6. Monitor temperatures and resilver to completion before considering another disk.

### Backup failure

1. Preserve local snapshots and avoid destructive cleanup.
2. Check destination availability, credential expiry, repository integrity, capacity,
   and network path.
3. Rerun only after the cause is corrected.
4. Perform a restore test; a successful upload alone does not prove recoverability.

### Lost Tailscale client

1. Revoke the device in Tailscale immediately.
2. Revoke Nextcloud app passwords/sessions and Immich sessions.
3. Review audit windows and reset application credentials if compromise is possible.
4. Record the incident and replacement-device approval.

### Certificate failure

1. Continue through a valid LAN fallback name only if it was already provisioned and
   trusted; never click through a browser warning.
2. Verify Cloudflare token status, permissions, clock, authoritative nameservers, CAA,
   and ACME TXT creation.
3. Use Let's Encrypt staging while diagnosing repeated issuance attempts.
4. Roll back to the last complete hosting revision if configuration caused the failure.

### Utility failure

Allow the UPS/TrueNAS NUT policy to stop applications, sync storage, and shut down. Do
not repeatedly power the NAS back on during an unstable outage. After power returns,
confirm UPS state, clean pool import, services, Tailscale, DNS, Caddy, and backup jobs.

## User offboarding

1. Remove the user from the tailnet group.
2. Revoke their devices if they no longer belong in the tailnet.
3. Disable Nextcloud and Immich accounts without immediately deleting recoverable data.
4. Transfer owned shared data according to the family retention decision.
5. Revoke app passwords, sessions, shares, and recovery codes.
6. Record who approved the offboarding and when deletion is due.
