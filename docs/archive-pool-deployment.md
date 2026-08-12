# Archive-pool deployment

Phase 2 creates `archive` as a separate four-drive RAIDZ2 pool using the four Toshiba
DT01ACA300 3 TB SATA disks. It does not expand `tank`, add a vdev to `tank`, or add a
single-disk stripe. Failure of one pool therefore does not structurally destroy the
other pool.

Before planning, require four identified DT01ACA300 SATA 512e drives with clean SMART
and burn-in,
a healthy pool, successful recent scrub, no resilver, current database dumps and
snapshots, fresh offsite backup, successful restore test, and online UPS. Review the
final topology and verify `tank` remains unchanged.

Generate with `pnas-install archive-plan`; the exact confirmation must include
`archive` and all four Toshiba serials. Reject any SAS, non-3-TB, non-512e, or wrong-model
selection. These older desktop drives require a full destructive burn-in and a current
independent backup before production use.

After creation, verify both pools and expected capacity, scrub `archive`, verify encryption
and applications, run a backup, update inventory and forecasts, export a new recovery
bundle, and record the change in the audit log.
