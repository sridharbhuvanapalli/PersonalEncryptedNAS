# Phase 1 deployment

Physical execution is intentionally unavailable until this entire checklist is
completed on the real machine and the real inventory adapter is enabled.

1. Install TrueNAS on the PM830; create single-device `apps` on the TN320 1 TB NVMe and
   separate single-device `app-recovery` on the Inland 512 GB SATA SSD using the
   installation runbook.
2. Record all eight bays and map the four HC550 SAS disks by serial and stable ID.
3. Run long SMART tests and destructive burn-in on all four HC550 disks.
4. Run `pnas-install preflight`, `inventory`, and `capacity-plan`.
5. Select exactly four drives with `pnas-install main-plan` and repeated `--serial`
   arguments.
6. Review the JSON inventory fingerprint, stable IDs, RAIDZ2 topology, and every
   destructive operation. A generic `yes` is never accepted.
7. Apply only with the exact phrase printed by the plan. Plans expire and any
   inventory change invalidates them.
8. Create the unencrypted `tank` root and independent encrypted dataset roots.
9. Export and verify keys offline before storing family data.
10. Configure ACLs, snapshots, SMART schedules, monthly scrub, UPS, and alerts.

Current software can execute the complete mock dry-run. Real pool creation remains
blocked in code until the hardware validation session is completed.
