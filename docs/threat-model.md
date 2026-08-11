# Threat model

## Protected assets

Family originals, documents, photos, videos, application databases, credentials,
encryption keys, backup repositories, recovery material, and audit records.

## Trust boundaries and denied actors

The public internet must never reach NAS services. Ordinary family users must not
reach TrueNAS administration, the Operations Manager, SSH, PostgreSQL, Redis, or
backup administration. One family member must not access another member's private
datasets except through deliberate application sharing. Compromised applications
must not gain Docker control or unrestricted host access. Offsite storage providers
must not see plaintext backup contents.

## Primary threats and controls

| Threat | Principal controls |
|---|---|
| Disk theft | Independently encrypted ZFS dataset roots; offline keys |
| NAS theft or loss | Encrypted Restic offsite backup and tested recovery |
| Public attack | No forwarded ports; LAN/Tailscale-only ingress; ACLs |
| Stolen client | Tailscale device approval/removal, MFA, session revocation |
| Credential theft | Secret files, MFA, least privilege, rotation, redaction |
| Operator error | Dry-run, immutable plan input, exact serial confirmation, audit |
| Ransomware | Snapshots, offsite backup, Object Lock option, restore testing |
| Malicious container | No socket, minimal capabilities, private networks, read-only mounts |
| Unlocked administrator access | Separate accounts; audit; client-side encryption when required |

## Consistency and ownership

Read-only monitoring may be eventually consistent for a short polling interval.
Inventory, plan approval, and destructive storage mutations require a single fresh
authoritative TrueNAS view and fail if it changes. The technical administrator owns
storage mutations, keys, backups, and incident response. No ordinary user or public
actor should ever possess those privileges.

