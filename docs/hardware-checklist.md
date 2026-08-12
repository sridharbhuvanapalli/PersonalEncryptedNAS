# Hardware checklist

## Final platform-specific checklist

The final platform is the i7-12700K, MSI PRO Z790-P WIFI DDR4, 48 GB DDR4-3200,
optional RTX 2060, JONSBO N5, acquired ASRock SL-1000G, Samsung PM830 128 GB SATA
boot SSD, and Inland TN320 NVMe application SSD. See the complete
[hardware BOM](hardware-bom.md) and [transplant guide](build-and-transplant-guide.md).

## Required

- JONSBO N5 with 12 hot-swap 3.5-inch bays; eight initially populated.
- Four SAS and four SATA data connections plus eight safe drive-power connections;
  no molded adapters.
- Genuine LSI SAS 9207-8i in P20 IT mode for the SAS disks; motherboard SATA for the
  Toshiba disks; no hardware RAID before ZFS.
- Samsung PM830 128 GB dedicated TrueNAS boot SSD, accepted only after health testing.
- Inland TN320 NVMe for Apps; verify its actual capacity and health before use and never
  place Apps on the TrueNAS boot device.
- Four WD Ultrastar DC HC550 18 TB 512e SAS drives for `tank`.
- Four Toshiba DT01ACA300 3 TB 512e SATA drives for `archive`.
- PSU sized for eight-drive startup current and USB-connected NUT-compatible UPS.
- All original SL-1000G modular harnesses and all required N5 backplane power inputs.
- 1 Gb Ethernet, static address or DHCP reservation, compatible switch and cabling.
- TrueNAS installer USB, administrator computer, offsite/USB backup destination,
  offline encryption-key storage, recovery documentation, and replacement SATA cable.

## Recommended

- 32 GB RAM, 2.5 Gb Ethernet, mirrored application SSDs, Intel Quick Sync for
  Immich transcoding, ECC where supported, and drives from varied batches.
- Cabling clear of airflow, a rapid replacement plan, and UPS capacity
  sized for the final eight-drive system.

## Optional

- 64 GB RAM for heavier workloads and a cold-spare data drive.
- RTX 2060 for measured Immich CUDA workloads; prefer UHD 770/Quick Sync initially.

## Application SSD contents

PostgreSQL, Redis, container state, Immich thumbnails, encoded video, ML cache,
logs, and temporary processing data. Original documents and media remain on RAIDZ2.

## Drive acceptance

Record bay, model, serial, stable `/dev/disk/by-id/` identity, capacity, interface,
logical/physical sectors, recording method, SMART health and extended-test result,
temperature, power-on hours,
and supplied warranty data. Reject USB flash, unhealthy, undersized, unidentified,
boot, and application devices. Do not select a pool disk by `/dev/sdX` alone.
Confirm every HC550 label is a SAS 512e `WUH721818AL52xx` variant before cabling; do
not mix it with a SATA or 4Kn variant in the same vdev.
