# Operations

Use the complete [Operations Manager SOP](operations-manager-sop.md) for deployment,
dashboard interpretation, cadence, change plans, incidents, and user offboarding.

## Daily and weekly checks

Use `pnasctl status` and `doctor` to review pool, disk, encryption, application,
backup, UPS, certificate, and Tailscale health. Read commands are safe by default.
Investigate every critical alert immediately. Never clear an alert without recording
the cause and resolution.

Capacity warns at 70% and becomes critical at 80%. Monthly scrubs, SMART short tests,
and periodic extended tests should be scheduled through TrueNAS. Do not run extended
tests on every disk simultaneously. A degraded pool, active resilver, failed SMART
test, unavailable database, failed backup, or UPS shutdown condition is critical.

## ZFS datasets and encryption

Create an unencrypted pool root and independent encrypted roots:

```text
tank/family-files/nextcloud-data
tank/family-photos/immich-library
tank/database-dumps
tank/local-backups
apps/app-config/{nextcloud,immich,proxy,tailscale,backup}
apps/databases/{nextcloud-postgres,immich-postgres}
apps/immich-generated/{thumbnails,encoded-video,machine-learning-cache}
```

Use AES-256-GCM defaults and `lz4` compression. Disable atime on application and media
datasets. Start with the default record size for general files and databases unless
measurements justify a database-specific record size; changing it affects new blocks,
not existing data. Apply quotas to user-facing datasets and reserve only space that
has a documented recovery purpose. Use separate service accounts and least-privilege
ACLs; applications must not write each other's libraries.

Key-based roots can unlock automatically for unattended services but require verified
offline key exports. Passphrase roots support manual administrative unlock and reduce
unattended exposure after reboot. Record the chosen availability/security tradeoff.
Losing the only key is catastrophic. An unlocked NAS administrator can read ordinary
Nextcloud and Immich content.

## Snapshots and file restoration

Use frequent snapshots for active user data and longer daily/monthly retention based
on change rate and available space. To restore a deleted file, first browse or clone
the relevant snapshot to a temporary read-only location, verify its identity and
contents, then copy only the requested file back with correct ownership and ACLs.
Avoid rolling back an entire active dataset for a single-file recovery.

## UPS test

Configure the USB UPS with TrueNAS NUT support, set a conservative low-battery or
runtime threshold, and test using a maintenance window and noncritical workload.
Verify the alert, orderly application stop, dataset sync, shutdown, and clean recovery.
Never test by abruptly removing utility and battery power together.

Source: [TrueNAS dataset encryption](https://www.truenas.com/docs/scale/datasets/encryption/encryptingdatasets/)
and [TrueNAS UPS service](https://www.truenas.com/docs/scale/scaletutorials/systemsettings/services/upsservicescale/).
