# Recovery

Keep this runbook, TrueNAS configuration export, dataset-key manifest, service
configuration, inventory, and backup instructions in an age-encrypted recovery bundle
stored both off the NAS and offline. Keep the age identity separately. Test decryption
and key exports before relying on them.

## Database restore test

1. Provision an isolated PostgreSQL container matching the production major version.
2. Decompress the chosen dump and restore it into a new empty test database.
3. Fail on SQL errors, then run application schema and integrity checks.
4. Start an isolated application instance without access to production paths.
5. Verify login and representative records; destroy the isolated environment afterward.

## Selected-file Restic test

Restore a named file from `latest` into a new empty directory, compare its size and
cryptographic hash with the source record, open it where appropriate, then record the
snapshot ID, file, date, and result. Never restore tests over production paths.

## Complete NAS loss

1. Obtain replacement hardware and verify every component and drive identity.
2. Install the supported TrueNAS maintenance release on a dedicated boot SSD.
3. Restore the TrueNAS configuration only after reviewing network and device mappings.
4. Recreate/import the intended pools without formatting backup media.
5. Unlock encrypted roots using verified offline keys.
6. Recreate application datasets and ACLs; deploy pinned Compose projects stopped.
7. Restore configuration, databases, then family originals from Restic.
8. Validate database integrity, permissions, file counts/hashes, and application health.
9. Re-enroll Tailscale, rotate credentials, issue trusted private certificates, and
   verify there is no public reachability.
10. Run a new backup and restore test, update the recovery bundle, and document loss.

If keys are lost, encrypted datasets are unrecoverable. If Restic credentials or
password are lost, the offsite repository cannot be restored. Never store the only
copy of either on the NAS.

