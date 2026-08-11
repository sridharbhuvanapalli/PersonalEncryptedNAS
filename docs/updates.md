# Updates

Watchtower and unattended stateful application updates are prohibited.

For each TrueNAS or application update:

1. Detect the candidate and retain its exact version.
2. Read official release notes and identify breaking changes.
3. Create and validate both PostgreSQL dumps.
4. Create named pre-update ZFS snapshots.
5. Confirm offsite-backup freshness and recent restore success.
6. Generate a machine-readable update plan and review rollback limits.
7. Approve exactly one application project.
8. Pull only the pinned target images and apply that project.
9. Run container health, login, upload/download, and application-specific checks.
10. Record success or execute the reviewed rollback.

Rollback can require the previous Compose file, database dump, and pre-update snapshot.
Never start an older application against a database already migrated by a newer
version unless that rollback path is explicitly supported. TrueNAS updates use only
the supported UI/update process after saving configuration and reviewing the Software
Status page.

