# Hardware bill of materials

## Acquired platform

| Component | Installed hardware | Disposition |
|---|---|---|
| CPU | Intel Core i7-12700K | Keep; use UHD 770/Quick Sync initially |
| Motherboard | MSI PRO Z790-P WIFI DDR4 | Keep; disable motherboard RAID/RST/VMD |
| Memory | 48 GB DDR4-3200 | Keep only after extended memory validation |
| GPU | NVIDIA RTX 2060 | Optional; remove initially to reduce idle power |
| Chassis | JONSBO N5 NAS PC Case | Use; 12 hot-swap 3.5-inch bays and 2–4 dedicated 2.5-inch positions |
| PSU | ASRock Steel Legend SL-1000G | Acquired; retain all original modular cables |
| TrueNAS boot SSD | Samsung SSD PM830 128 GB SATA | Acquired; reuse only after SMART/health validation |
| Application SSD | Inland TN320 NVMe | Acquired; verify label capacity, SMART/NVMe health, endurance, and firmware |
| Main disks | 4 × WD Ultrastar DC HC550 18 TB, SAS 12 Gb/s, 512e | `tank`: one four-wide RAIDZ2 vdev |
| Archive disks | 4 × Toshiba DT01ACA300 3 TB, SATA 6 Gb/s, 512e | `archive`: one four-wide RAIDZ2 vdev |

The board supplies six SATA ports, four M.2 positions, Intel 2.5 Gb Ethernet, a CPU
PCIe 5.0 x16 slot, and a chipset PCIe 4.0 x4 slot. The N5 supports ATX/E-ATX boards,
12 hot-swap 3.5-inch drives, an ATX PSU up to 170–240 mm, a 160 mm CPU cooler, and eight
expansion slots. Its two backplane PCBs expose one SATA-style data port per HDD bay;
they are not SAS expanders. Use the HBA for the four SAS disks and motherboard SATA for
the four Toshiba disks. Four HDD bays remain available for future separately reviewed
expansion.

## Additional required parts

Prices are planning ranges in US dollars, not quotations. Used HBAs must be tested and
counterfeit listings avoided.

| Qty | Component | Recommended specification | Planning range |
|---:|---|---|---:|
| 1 | HBA | Genuine LSI SAS 9207-8i, P20 IT-mode firmware | $40–90 |
| 1 | HBA-to-backplane cable | Forward SFF-8087 host to 4 × 7-pin SATA-style backplane ports, 60–90 cm | $20–40 |
| 4 | SATA data cables | Latching, 60–90 cm, motherboard to archive backplane ports | $20–40 total |
| 1 | UPS | CyberPower CP1500PFCLCD 1500 VA / 1000 W pure sine | $220–275 |
| 0–1 | Second application NVMe | Match capacity/endurance to the TN320 if an Apps mirror is chosen | $40–100 |
| 2–5 | Fans | Quality PWM intake/replacement fans for HDDs and HBA, subject to measured thermals | $25–75 |
| 1 lot | Service parts | Thermal paste, labels, cable ties, spare SATA cable | $15–30 |

Expected remaining incremental total excluding data disks and the already acquired case,
PSU, and SSDs is approximately **$360–650**. Deduct the UPS, HBA, cables, second NVMe, or
fans if already owned or not selected. Do not reduce cost by using a hardware RAID
card, counterfeit HBA, USB boot flash drive, unverified SMR disks, or molded SATA power
splitters. An SFF-8643 cable does not fit the 9207-8i. The N5 backplane requires the
SFF-8087 cable to terminate in four 7-pin data connectors rather than SFF-8482 drive
plugs. SAS support through this pass-through backplane must be proven with all four
HC550s before creating `tank`.

## Controller and slot placement

Preferred low-power configuration:

1. Remove the RTX 2060.
2. Enable the i7-12700K integrated graphics.
3. Put the 9207-8i in the CPU-connected PCIe x16 slot, where it can negotiate its native
   PCIe 3.0 x8 link.

If the RTX 2060 is retained, place it in the CPU x16 slot and place the HBA in the
full-length chipset slot operating at PCIe 4.0 x4. Four PCIe 3.0 lanes still provide
more aggregate bandwidth than eight mechanical HDDs normally sustain, but confirm HBA
enumeration, cooling clearance, and throughput during burn-in.

## Power design

The SL-1000G is ATX 3.1/PCIe 5.1, fully modular, 80 PLUS Gold, Cybenetics Platinum,
and provides nine SATA power connectors and a ten-year warranty. Never use modular PSU
cables from another PSU model, even when the connector fits. The initial configuration
needs power for both N5 backplane PCBs plus the Samsung SATA boot SSD. The N5 backplanes
aggregate drive power, so do not budget one PSU plug per HDD. Inspect the exact backplane
revision and populate every power input required by the Jonsbo manual/PCB labeling using
only original ASRock harnesses; do not assume one connected input safely powers a full
backplane.

For future operation, use only manufacturer-approved additional PSU cables and keep each
N5 backplane powered within its documented rating. Do not daisy-chain cheap adapters.

The CP1500PFCLCD supplies 1500 VA / 1000 W, sine-wave output, and USB HID communication.
Connect the NAS, network switch, and FiOS ONT/router only after measuring total load and
preserving adequate shutdown runtime. Connect its USB management port directly to the
NAS for NUT-based shutdown.

## Disk layout

| Pool | Disks | Layout | Approximate capacity before operational overhead |
|---|---|---|---:|
| `tank` | 4 × 18 TB HC550 SAS | RAIDZ2 | 36 TB / 32.7 TiB nominal; 26.2 TiB at 80% |
| `archive` | 4 × 3 TB DT01ACA300 SATA | RAIDZ2 | 6 TB / 5.46 TiB nominal; 4.37 TiB at 80% |

Operate each pool below 80 percent. These figures are planning ceilings before ZFS
metadata, reservations, snapshots, and application overhead. Keep the pools independent:
never add the four 3 TB archive disks as another vdev in `tank`. Neither pool is a backup
of the other, and RAIDZ2 does not replace an offsite backup.

## Interface, sector, and cooling requirements

- The photographed HC550 labels state SAS and 512e. Confirm all four full model suffixes
  begin `WUH721818AL52` before installation; other HC550 suffixes can be SATA or 4Kn.
- Connect the four HC550 backplane data ports to one 9207-8i SFF-8087 port using a
  forward 4 × 7-pin breakout. A SAS controller can run the SAS-3 disks at the
  controller's negotiated SAS-2 link rate, which is ample for four HDDs.
- Connect the four Toshiba backplane data ports to four motherboard SATA ports. SATA
  controllers cannot operate SAS drives.
- The N5 backplane is a pass-through connection, not a storage controller. Before pool
  creation, confirm all four HC550s enumerate simultaneously as SAS devices with unique
  WWNs, SMART data, correct capacity, and no link resets. If any fail, stop and replace
  the case/backplane path or use direct SFF-8482 cabling outside the hot-swap backplane.
- Verify Power Disable behavior during bench acceptance. If a drive does not spin, use
  a PWDIS-compatible SAS power/backplane solution; do not tape pins or improvise power
  adapters.
- Provide direct intake airflow across all eight 7200-RPM disks and forced airflow over
  the HBA heatsink. Validate steady-state and simultaneous burn-in temperatures before
  commissioning.

The eight disks draw roughly 44 W idle and 61 W during typical read/write activity from
their published values; startup current is materially higher. The 1000 W PSU has ample
capacity, but power-harness quality, connector count, airflow, and staggered test load
remain operational constraints.

## Reference specifications

- [MSI PRO Z790-P WIFI DDR4 specifications](https://us.msi.com/Motherboard/PRO-Z790-P-WIFI-DDR4/Specification)
- [JONSBO N5 specifications and installation manual](https://www.jonsbo.com/en/products/N5Black.html)
- [JONSBO N5 backplane and cabling review](https://nascompares.com/2024/10/04/jonsbo-n5-review/)
- [ASRock SL-1000G specifications](https://asrock.com/Power-Supply/SteelLegend/SL-1000G/)
- [Samsung 128 GB SSD 830 support](https://www.samsung.com/dk/support/model/MZ-7PC128D/EU/)
- [CyberPower CP1500PFCLCD specifications](https://www.cyberpowersystems.com/product/ups/pfc-sinewave/cp1500pfclcd/)
- [WD Ultrastar DC HC550 data sheet](https://documents.westerndigital.com/content/dam/doc-library/en_us/assets/public/western-digital/product/data-center-drives/ultrastar-dc-hc500-series/data-sheet-ultrastar-dc-hc550.pdf)
- [Toshiba DT01ACA series product overview](https://storage.toshiba.com/docs/desktop-pc-hard-drive-documents/dt01aca-product-overview.pdf)
