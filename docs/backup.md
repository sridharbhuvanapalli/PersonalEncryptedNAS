# Backup

RAIDZ2 tolerates disk failures and ZFS snapshots provide fast local recovery; neither
is a backup. Restic encrypts critical data client-side before Backblaze B2 or an
external USB target receives it.

Protect family originals, documents, Nextcloud data, Immich originals, validated
PostgreSQL dumps, application/Compose/proxy configuration, and recovery documentation.
Do not back up replaceable caches or generated media unless recovery-time needs justify
the cost. Initial offsite scope is 2–4 TB.

The workflow creates dumps, validates their PostgreSQL headers, takes application-
consistent snapshots, runs Restic, records redacted audit data, and alerts on failure.
Retention is 30 daily, 12 weekly, and 12 monthly. Run `restic check` regularly and a
selected-file restore at least quarterly. Credentials and the Restic password belong
in separate mode-0600 files with least privilege.

For B2, use a bucket-specific application key that can read/write only the backup
bucket. Object Lock improves resistance to deletion but prevents pruning locked
objects until provider retention expires. Ensure the provider policy is compatible
with Restic retention before enabling it.

Sources: [Restic documentation](https://restic.readthedocs.io/en/stable/),
[Restic B2 backend](https://restic.readthedocs.io/en/stable/030_preparing_a_new_repo.html#backblaze-b2),
and [Backblaze Object Lock](https://www.backblaze.com/docs/cloud-storage-object-lock).

