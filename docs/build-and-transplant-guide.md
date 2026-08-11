# NAS build and component-transplant guide

This procedure moves the i7-12700K platform into the Phanteks Enthoo Pro and prepares
it for TrueNAS. Pool creation remains a separate, serial-confirmed operation.

## 1. Protect the current system

1. Copy every file that exists only on the current 256 GB SSD or 1 TB disk to two
   independently readable destinations.
2. Export browser, license, BitLocker recovery, application, and Windows activation
   information that might be needed later.
3. Photograph the working motherboard, CPU-power, cooler, front-panel, GPU-power, fan,
   and storage connections.
4. Record every installed component model and serial number.
5. Download the MSI motherboard manual, current stable BIOS, TrueNAS ISO and checksum,
   HBA P20 IT firmware evidence, and NIC firmware before taking the system offline.
6. Shut Windows down normally, switch the old PSU off, unplug it, and press the power
   button for ten seconds.

Do not attach any future ZFS data disk during initial firmware or TrueNAS installation.

## 2. Prepare the workspace and chassis

1. Work on a large non-carpeted surface with good lighting.
2. Use an ESD wrist strap connected to the bare chassis or touch grounded metal often.
3. Remove both Enthoo Pro side panels, the front panel, both native HDD cages, and the
   required 5.25-inch bay covers.
4. Vacuum or blow dust outside; do not spin fans at extreme speed with compressed air.
5. Verify that ATX standoffs correspond exactly to the MSI board holes. Remove every
   unused standoff beneath the board.
6. Install the extra 3.5-inch cage and its dedicated intake fan before the motherboard
   obstructs access.
7. Plan two cable paths: data cables on one side and power/fan cables on the other.

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
6. Install the ASRock PSU with its intake facing the ventilated bottom filter.
7. Use only cables supplied or explicitly approved for this exact PSU model.
8. Install the boot SATA SSD and application NVMe SSD. If using mirrored app SSDs,
   install and label both now.
9. For the preferred low-power build, leave the RTX 2060 out and install the HBA in the
   top CPU-connected x16 slot. Otherwise install the RTX there and the HBA in PCI_E3.
10. Direct an intake or small fan across the HBA heatsink; server HBAs expect forced air.
11. Connect front-panel buttons/LEDs, front USB, chassis intrusion if desired, and fans.

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
4. Confirm 48 GB of memory, both SSDs, the HBA, Intel 2.5 GbE, temperatures, and fans.
5. Update BIOS only through MSI's supported process and only while stable UPS power is
   available. Recheck every storage-related setting afterward.

## 6. Validate memory and thermals

1. Run at least four complete MemTest86 passes; a 24-hour run is preferred because the
   48 GB configuration may combine DIMM capacities or kits.
2. Any error is a stop condition. Reseat and test DIMMs individually; do not proceed by
   assuming a single error is harmless.
3. Run a CPU load test from temporary boot media and verify cooler mounting and fan
   response. Do not overclock.
4. Verify that the HBA is genuine, reports IT mode, and runs P20 firmware. It must expose
   individual disks, not RAID virtual disks.

## 7. Install TrueNAS safely

1. Verify the downloaded TrueNAS ISO SHA-256 checksum against the official publication.
2. Boot the installer in UEFI mode.
3. Select only the dedicated 128–256 GB boot SSD. Confirm its model and serial twice.
4. Create a named administrator, enable MFA, and do not expose the UI on the WAN.
5. Give TrueNAS a reserved management address, for example `192.168.1.10`.
6. Reserve a separate service address, for example `192.168.1.20`, for Caddy and LAN DNS.
7. Select the NVMe application SSD or mirror for the Apps pool after TrueNAS installation.
8. Do not create `tank` yet.

## 8. Install and accept disks

1. Power the system off and disconnect AC before attaching disks.
2. Place the four equal 12 TB or four equal 16 TB disks in bays 1–4.
3. Place the two active 3 TB archive disks in bays 5–6.
4. Keep the third 3 TB cold spare in an antistatic container, labeled with model, serial,
   last SMART-test date, and intended pool. Do not leave it powered merely to fill bay 7.
5. Connect HBA port groups using only SFF-8087 **forward** breakout cables.
6. Spread disk power across the PSU's approved harnesses. Avoid sharp cable bends and
   any connector that feels loose or hot.
7. Boot and map physical bay, HBA port, stable `/dev/disk/by-id` name, model, serial,
   capacity, and temperature for every disk.
8. Confirm every large disk is SATA and CMR. A SAS disk requires compatible SAS cabling
   or a SAS backplane; it must not be forced onto a SATA-only connection.
9. Run SMART short and long tests, then a destructive burn-in before storing data.
10. Reject disks with reallocated/pending sectors, interface errors that follow the disk,
    unexplained temperature excursions, capacity mismatch, or failed SMART tests.

## 9. Create storage and protection

1. Create `tank` as one four-disk RAIDZ2 vdev only after recording and confirming all
   four serial numbers.
2. Create the two-disk archive mirror separately through a reviewed TrueNAS workflow.
   The current automation intentionally does not create this non-RAIDZ2 pool.
3. Create encrypted dataset roots, export their keys, and verify the offline copies.
4. Configure snapshots, monthly scrubs, staggered SMART tests, alerts, quotas, and the
   70/80-percent utilization thresholds.
5. Configure encrypted Restic backup before importing the only copy of family data.
6. Configure the UPS USB connection and perform a controlled shutdown test.

## 10. Commission applications and remote access

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
