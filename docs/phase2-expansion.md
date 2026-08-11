# Phase 2 expansion

The default is a second four-drive RAIDZ2 data vdev. Never add single-disk stripes.
Do not widen the first vdev without a separate resilience and migration decision.

Before planning, require four new identified CMR drives with clean SMART and burn-in,
a healthy pool, successful recent scrub, no resilver, current database dumps and
snapshots, fresh offsite backup, successful restore test, and online UPS. Review the
final topology and the fact that losing either complete data vdev loses the pool.

The exact confirmation must include `tank` and all four new serials. If the second
vdev has a different drive capacity, stop for separate approval: usable capacity and
allocation become asymmetric and the smallest disk in each vdev determines that
vdev's capacity.

After expansion, verify both vdevs and expected capacity, scrub, verify encryption
and applications, run a backup, update inventory and forecasts, export a new recovery
bundle, and record the change in the audit log.

