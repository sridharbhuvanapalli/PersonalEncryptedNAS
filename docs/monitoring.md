# Monitoring and notifications

Collect `tank`, `archive`, `apps`, and `app-recovery` pool/vdev state independently,
SSD/NVMe health and error logs, SMART and temperatures,
scrub/resilver state, encryption
locks, capacity and snapshot growth, databases and caches, application health,
backups and restore age, UPS, certificates, Tailscale, and updates.

Warnings include 70% utilization, a restore test older than 90 days, hot disks, and
certificates expiring within 14 days. Critical alerts include 80% utilization,
degraded pool, failed SMART, backup older than 48 hours, failed backup, unavailable
database, and UPS shutdown conditions.

Schedule monthly scrubs for both pools on different days. Stagger long SMART tests by
disk and do not start them on all eight 7200-RPM drives simultaneously or during a scrub,
resilver, backup, or large media import.

Alert while `apps` remains single-device so operators understand that backups, not a
mirror, are the recovery control. After the future NVMe is attached, alert unless the
`apps` data vdev contains exactly two healthy mirror members. Alert if `app-recovery`
exports are older than 24 hours or their matching encrypted offsite copies are stale.

Configure a private notification target such as an authenticated SMTP relay or a
LAN/Tailscale-only ntfy instance. Notification credentials are secret files. Alerts
must contain system identity, severity, safe context, and runbook link—but no family
filenames, tokens, passwords, or encryption keys.
