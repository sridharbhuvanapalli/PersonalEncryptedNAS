# Hardware checklist

## Final platform-specific checklist

The final platform is the i7-12700K, MSI PRO Z790-P WIFI DDR4, 48 GB DDR4-3200,
optional RTX 2060, and Phanteks Enthoo Pro. See the complete
[hardware BOM](hardware-bom.md) and [transplant guide](build-and-transplant-guide.md).

## Required

- Eight 3.5-inch bays with airflow across every drive.
- Eight SATA data and eight safe SATA power connections; no molded adapters.
- Motherboard SATA or supported HBA in IT/JBOD mode; no hardware RAID before ZFS.
- x86_64 CPU with hardware AES, 16 GB RAM minimum, and dedicated 128 GB+ boot SSD.
- Separate 500 GB+ application SSD; never use the TrueNAS boot device for apps.
- Four initial equal-capacity 12 TB or 16 TB CMR NAS/enterprise SATA drives.
- PSU sized for eight-drive startup current and USB-connected NUT-compatible UPS.
- 1 Gb Ethernet, static address or DHCP reservation, compatible switch and cabling.
- TrueNAS installer USB, administrator computer, offsite/USB backup destination,
  offline encryption-key storage, recovery documentation, and replacement SATA cable.

## Recommended

- 32 GB RAM, 2.5 Gb Ethernet, mirrored application SSDs, Intel Quick Sync for
  Immich transcoding, ECC where supported, and drives from varied batches.
- Cabling clear of airflow, a cold spare or rapid replacement plan, and UPS capacity
  sized for the final eight-drive system.

## Optional

- 64 GB RAM for heavier workloads and a cold-spare data drive.
- RTX 2060 for measured Immich CUDA workloads; prefer UHD 770/Quick Sync initially.

## Application SSD contents

PostgreSQL, Redis, container state, Immich thumbnails, encoded video, ML cache,
logs, and temporary processing data. Original documents and media remain on RAIDZ2.

## Drive acceptance

Record bay, model, serial, stable `/dev/disk/by-id/` identity, capacity, sectors,
CMR/SMR status, SMART health and extended-test result, temperature, power-on hours,
and supplied warranty data. Reject USB flash, unhealthy, undersized, unidentified,
boot, and application devices. Do not select a pool disk by `/dev/sdX` alone.
