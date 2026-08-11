# Backup artifacts

The runtime workflow creates validated PostgreSQL dumps before Restic captures the
critical datasets. Configure `RESTIC_PASSWORD_FILE` and provider credentials as
mode-0600 files. Never place them in this directory or commit them.

The default policy keeps 30 daily, 12 weekly, and 12 monthly snapshots. Run `check`
and a selected-file restore on a schedule. Object Lock can prevent ransomware and
credential compromise from deleting backup objects, but locked objects cannot be
pruned until their retention expires; align provider retention with Restic policy.

