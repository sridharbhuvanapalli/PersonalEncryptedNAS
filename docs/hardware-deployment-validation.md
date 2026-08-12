# Hardware deployment validation

Software and mock validation do not make the NAS production-ready. Before storing the
only copy of family data, perform and record:

- component inventory, SAS/SATA and 512e verification, SMART long tests, and destructive
  burn-in for all eight disks;
- genuine LSI SAS 9300-8i acceptance evidence: SAS3008 identity, P16 IT mode, unique
  nonzero SAS address, both SFF-8643 ports tested, directed cooling, PCIe Gen3 x8 link,
  two successful cold boots, and no controller/link resets during sustained I/O;
- all three included N5 rear fans operational, dedicated HBA airflow present, cable
  routing clear of fan blades, and acceptable HDD/HBA thermals during simultaneous load;
- real API method/schema probes against the installed TrueNAS version;
- `tank` and `archive` creation as independent RAIDZ2 pools on explicitly confirmed serials;
- `apps` creation from only the TN320 1 TB NVMe and independent `app-recovery` creation
  from only the Inland 512 GB SATA SSD;
- rehearsal of the future NVMe attach-as-mirror procedure, including rejection of a
  proposed new striped vdev;
- dataset key export, offline storage, lock/unlock, and reboot behavior;
- snapshot single-file recovery and both database restores;
- Restic selected-file and full-loss recovery exercises;
- simulated single- and double-disk failure/replacement/resilver procedures;
- scrub alerts, failed SMART alerts, and capacity thresholds;
- UPS communication, low-battery shutdown, and clean restart;
- private HTTPS trust and renewal on every client type;
- LAN access during ISP outage and remote Tailscale ACL checks;
- proof that router/public scans cannot reach services;
- one application update and supported rollback;
- archive-pool rehearsal with a changed-inventory rejection;
- proof that removing either pool from a mock/recovery exercise does not invalidate the
  topology of the other pool.

Production readiness is granted only after evidence for every applicable item is
stored with the offline recovery documentation.
