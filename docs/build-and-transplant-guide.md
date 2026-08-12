# NAS build and component-transplant guide

This procedure moves the i7-12700K platform into the JONSBO N5 and prepares
it for TrueNAS. Pool creation remains a separate, serial-confirmed operation.

## 1. Protect the current system

1. Copy every file that exists only on the Samsung PM830, Inland TN320, Inland 512 GB
   SATA SSD, or any other current-system disk to two independently readable destinations.
   Pool/boot preparation can erase these devices.
2. Export browser, license, BitLocker recovery, application, and Windows activation
   information that might be needed later.
3. Photograph the working motherboard, CPU-power, cooler, front-panel, GPU-power, fan,
   and storage connections.
4. Record every installed component model and serial number.
5. Capture Samsung PM830 and Inland 512 GB SATA SMART data plus Inland TN320 NVMe
   health/error logs before dismantling. Record model, serial, capacity, and firmware.
6. Download the MSI motherboard manual, current stable BIOS, TrueNAS ISO and checksum,
   the official Broadcom 9300-8i firmware package/documentation, and NIC firmware before
   taking the system offline.
7. Shut Windows down normally, switch the old PSU off, unplug it, and press the power
   button for ten seconds.

Do not attach any future ZFS data disk during initial firmware or TrueNAS installation.

## 2. Prepare the workspace and chassis

1. Work on a large non-carpeted surface with good lighting.
2. Use an ESD wrist strap connected to the bare chassis or touch grounded metal often.
3. Remove the N5 panels and removable HDD sections in the order shown by the Jonsbo
   installation manual. Photograph both backplane PCBs, their data-port numbering, and
   every SATA/peripheral power input before covering them.
4. Vacuum or blow dust outside; do not spin fans at extreme speed with compressed air.
5. Verify that ATX standoffs correspond exactly to the MSI board holes. Remove every
   unused standoff beneath the board.
6. Confirm the 150 mm-long SL-1000G fits within the N5's 170–240 mm PSU allowance and
   that the existing CPU cooler is no taller than the N5's 160 mm limit.
7. Route and label the eight backplane data cables and all required backplane power
   harnesses before installing the PSU; access becomes restricted after assembly.
8. Plan separate cable paths for data, backplane power, fans, and front-panel wiring.

## 3. Remove the reusable components

1. Label and disconnect the GPU power, motherboard 24-pin, CPU EPS, front-panel, USB,
   audio, SATA, and fan cables.
2. Support the RTX 2060 while releasing the PCIe latch and removing it.
3. Remove the CPU cooler. If its weight or shape allows safe board removal without doing
   so, it may remain temporarily, but reinstalling with fresh paste is preferred.
4. Clean the CPU heat spreader and cooler cold plate with high-purity isopropyl alcohol.
5. Leave the i7-12700K and RAM seated unless inspection reveals a problem.
6. Remove the motherboard while supporting it by the edges.
7. Keep every screw grouped and labeled; do not reuse an incorrect coarse-thread screw
   in a motherboard standoff.

## 4. Install the platform

1. Install the motherboard I/O shield if it is not integrated.
2. Lower the board onto the verified standoffs without dragging it across them.
3. Tighten screws in a loose cross pattern, then make them snug—not over-tight.
4. Apply cooler-manufacturer-specified thermal paste and reinstall the LGA1700 cooler.
5. Connect the 24-pin ATX and both CPU EPS connectors required by the board/cooler load.
6. Install the acquired ASRock SL-1000G using the N5 PSU bracket and chassis-specified
   airflow orientation.
7. Use only the original cables supplied with this exact PSU. Connect every power input
   required by each N5 backplane according to its PCB markings/manual; never substitute
   modular cables from another PSU.
8. Install the Samsung PM830 128 GB and Inland 512 GB SATA SSDs in separate labeled
   2.5-inch positions and the TN320 1 TB in an M.2 slot. Record exact model, capacity,
   serial, firmware, health percentage, error log, and power-on hours. Do not format them.
9. For the preferred low-power build, leave the RTX 2060 out and install the HBA in the
   top CPU-connected x16 slot. Otherwise install the RTX there and the HBA in PCI_E3.
10. Direct an intake or small fan across the HBA heatsink; server HBAs expect forced air.
11. Connect front-panel buttons/LEDs, front USB, chassis intrusion if desired, and fans.

Before installing disk cabling, confirm the card is a genuine **LSI SAS 9300-8i**, not a
9300-8e or RAID-only substitute, and has two internal SFF-8643 ports. For the N5, obtain
one forward SFF-8643-to-4×7-pin breakout long enough to reach the selected backplane
ports; the cable terminates at the backplane, not at the drives. Also provide four
latching SATA cables for the archive ports and two for the SATA SSDs. Do not buy an
SFF-8087, reverse-breakout, or SFF-8482 drive-end cable for this connection.

## 5. First boot without data disks

1. Connect a monitor to the motherboard, a keyboard, wired Ethernet, and power through
   the UPS. Leave all HDD data and power cables disconnected.
2. Power on and check the MSI debug LEDs.
3. Load optimized BIOS defaults, then configure:
   - UEFI boot only;
   - AHCI SATA mode;
   - Intel RST, VMD, and motherboard RAID disabled;
   - integrated graphics enabled;
   - VT-d/IOMMU enabled;
   - restore after AC loss set to the documented preference;
   - CPU and RAM overclocking/XMP disabled initially;
   - fan curves that keep HDD intake airflow continuous.
4. Confirm 48 GB of memory, all three SSDs, the HBA, Intel 2.5 GbE, temperatures, and fans.
5. Update BIOS only through MSI's supported process and only while stable UPS power is
   available. Recheck every storage-related setting afterward.

## 6. Validate memory and thermals

1. Run at least four complete MemTest86 passes; a 24-hour run is preferred because the
   48 GB configuration may combine DIMM capacities or kits.
2. Any error is a stop condition. Reseat and test DIMMs individually; do not proceed by
   assuming a single error is harmless.
3. Run a CPU load test from temporary boot media and verify cooler mounting and fan
   response. Do not overclock.
4. Verify that the HBA is a genuine LSI SAS 9300-8i with SAS3008 controller, reports
   Product ID/firmware mode `IT`, and runs the approved P16 firmware. It must expose
   individual disks, not RAID virtual disks. Record `sas3flash -listall` and
   `sas3flash -list` output, including firmware version and a unique nonzero SAS address.
5. In an environment that provides `lspci`, record `lspci -nn` and `lspci -vv` evidence.
   In the preferred CPU-connected slot, `LnkSta` should report PCIe Gen3 (8 GT/s) at x8.
6. Test both SFF-8643 ports independently with a known-good SAS disk during the seller's
   return window, even though only one port is populated at initial deployment.

## 7. Install TrueNAS safely

1. Verify the downloaded TrueNAS ISO SHA-256 checksum against the official publication.
2. Boot the installer in UEFI mode.
3. Select only the Samsung PM830 128 GB boot SSD. Confirm its model, capacity, and serial
   twice. Because it is an older reused device, replace it if SMART/health data,
   self-tests, error logs, or secure erase behavior are questionable.
4. Create a named administrator, enable MFA, and do not expose the UI on the WAN.
5. Give TrueNAS a reserved management address, for example `192.168.1.10`.
6. Reserve a separate service address, for example `192.168.1.20`, for Caddy and LAN DNS.
7. Verify the Inland TN320 reports 1 TB and passes health checks. Create `apps` from only
   this NVMe as the initial single-device Apps pool. Do not combine it with the smaller
   SATA SSD.
8. Verify the Inland 512 GB SATA SSD and create the separate single-device
   `app-recovery` pool. Configure nightly database dumps, configuration exports, and
   selected recovery copies to it, plus encrypted offsite Restic copies.
9. Do not create `tank` yet.

## 8. Install and accept disks

1. Power the system off and disconnect AC before attaching disks.
2. Assign four adjacent N5 hot-swap bays to the HC550 group and four adjacent bays to
   the Toshiba group. Record the visible chassis bay number and matching backplane port;
   leave four bays empty.
3. Insert the four HC550 18 TB SAS 512e disks into the main-pool bays and the four
   DT01ACA300 3 TB SATA 512e disks into the archive bays.
4. Connect the four HC550 backplane ports to one HBA SFF-8643 port with the forward
   four-lane breakout. Connect the four Toshiba backplane ports to motherboard SATA.
5. Before final cable management, verify all eight disks spin and enumerate. Jonsbo's
   page describes hot-swap HDD support but does not explicitly guarantee SAS. Treat
   simultaneous enumeration of all four HC550s, SAS identity, WWNs, SMART access, and
   error-free I/O as a mandatory acceptance gate.
6. Spread disk power across the PSU's approved harnesses. Avoid sharp cable bends and
   any connector that feels loose or hot.
7. Boot and map physical bay, HBA port, stable `/dev/disk/by-id` name, model, serial,
   capacity, and temperature for every disk.
8. Confirm each HC550 reports SAS, 18 TB, 512-byte logical sectors, and a model identifier
   matching `HC550` or `WUH721818`; confirm each Toshiba reports SATA, 3 TB, 512-byte
   logical sectors, and `DT01ACA300`. Do not mix SATA/SAS or 4Kn/512e variants inside a
   vdev.
9. Run SMART short and long tests, then a destructive burn-in before storing data.
10. Run the full burn-in with direct airflow over all drives and the HBA. Stagger SMART
    long tests during normal operation rather than starting all eight simultaneously.
11. Reject disks with reallocated/pending sectors, interface errors that follow the disk,
    unexplained temperature excursions, capacity mismatch, or failed SMART tests.
12. Reboot and cold-boot twice, then repeat the eight-drive bay/serial map. Any HC550
    intermittently absent through the N5 backplane is a stop condition.

## 9. Create storage and protection

1. Generate `pnas-install main-plan` and create `tank` as one four-HC550 RAIDZ2 vdev
   only after recording and confirming all four serial numbers.
2. Generate `pnas-install archive-plan` and create `archive` as a separate four-Toshiba
   RAIDZ2 pool. Verify the operation says `create independent pool archive`; it must
   never say add/extend `tank`.
3. Create encrypted dataset roots, export their keys, and verify the offline copies.
4. Configure snapshots, separate monthly scrub dates, staggered SMART tests, alerts,
   quotas, and 70/80-percent utilization thresholds for both pools.
5. Configure encrypted Restic backup before importing the only copy of family data.
6. Configure the UPS USB connection and perform a controlled shutdown test.

## 10. Add the future 1 TB NVMe Apps mirror

This is a topology change, not an Apps migration. Perform it only from the TrueNAS UI or
a separately reviewed plan matching the installed TrueNAS release.

1. Acquire an NVMe whose reported usable capacity is at least that of the TN320; similar
   endurance and performance are preferred. Record model, serial, firmware, health, and
   error log, then run the supported extended/device self-test.
2. Confirm `apps` is ONLINE, scrubbed, below 80% utilization, and has no active resilver.
   Refresh database dumps on `app-recovery` and complete an encrypted offsite backup and
   recent restore test.
3. Stop Nextcloud, Immich, PostgreSQL, Redis/Valkey, proxy dependencies, and other
   write-heavy consumers during the topology operation.
4. In the `apps` VDEV/device screen, select the existing TN320 device and use the
   installed release's **Attach** operation to add the new NVMe as its mirror member.
   Confirm the preview changes the one-device data vdev into one two-device mirror.
5. Cancel immediately if the UI proposes a new top-level data vdev, stripe, pool, cache,
   SLOG, or special vdev. Do not choose Add VDEV merely because it is available.
6. Allow resilver to reach 100% without rebooting, detaching either SSD, or performing
   updates. Confirm `zpool status apps` reports one mirror containing exactly the TN320
   and new NVMe, with zero read/write/checksum errors.
7. Run an `apps` scrub, restart services in dependency order, and verify databases,
   Nextcloud, Immich, Operations Manager, backups, and a selected restore.
8. Update the bay/device map, recovery bundle, configuration export, monitoring baseline,
   and audit log. Usable `apps` capacity remains about 1 TB; the added NVMe provides
   redundancy, not capacity. `app-recovery` remains separate.

## 11. Commission applications and remote access

1. Create fixed Docker networks:
   `pnas_private` for applications and `pnas_management` with a documented small subnet
   for Caddy-to-manager traffic.
2. Deploy Nextcloud, Immich, Caddy, CoreDNS, and the manager from reviewed revisions.
3. Install the supported TrueNAS Tailscale App with Host Network enabled and Userspace
   disabled.
4. Apply the tailnet grants only after replacing placeholder identities.
5. Move Cloudflare authoritative DNS, test ACME staging, then issue production
   certificates.
6. Validate LAN access, external direct Tailscale access, ISP-outage behavior, backup
   restoration, disk replacement, and UPS shutdown using the commissioning checklist.

The NAS is not production-ready merely because it boots or a pool reports ONLINE.
Production begins only after the recovery and failure exercises succeed.
