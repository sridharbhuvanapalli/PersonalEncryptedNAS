# Hardware bill of materials

## Acquired platform

| Component | Installed hardware | Disposition |
|---|---|---|
| CPU | Intel Core i7-12700K | Keep; use UHD 770/Quick Sync initially |
| Motherboard | MSI PRO Z790-P WIFI DDR4 | Keep; disable motherboard RAID/RST/VMD |
| Memory | 48 GB DDR4-3200 | Keep only after extended memory validation |
| GPU | NVIDIA RTX 2060 | Optional; remove initially to reduce idle power |
| Chassis | Phanteks Enthoo Pro | Keep; six native 3.5-inch bays plus three 5.25-inch bays |
| Main disks | 4 × WD Ultrastar DC HC550 18 TB, SAS 12 Gb/s, 512e | `tank`: one four-wide RAIDZ2 vdev |
| Archive disks | 4 × Toshiba DT01ACA300 3 TB, SATA 6 Gb/s, 512e | `archive`: one four-wide RAIDZ2 vdev |

The board supplies six SATA ports, four M.2 positions, Intel 2.5 Gb Ethernet, a CPU
PCIe 5.0 x16 slot, and a chipset PCIe 4.0 x4 slot. The Enthoo Pro supplies six native
3.5-inch bays and three external 5.25-inch bays. These facts make an eight-port HBA and
a ventilated 5.25-inch drive cage the cleanest path to all eight disks. The four SAS
disks require the HBA; the four SATA archive disks use motherboard SATA ports.

## Additional required parts

Prices are planning ranges in US dollars, not quotations. Used HBAs must be tested and
counterfeit listings avoided.

| Qty | Component | Recommended specification | Planning range |
|---:|---|---|---:|
| 1 | HBA | Genuine LSI SAS 9207-8i, P20 IT-mode firmware | $40–90 |
| 1 | SAS forward breakout harness | SFF-8087 host to 4 × SFF-8482 SAS drive connectors with compatible drive power | $25–50 |
| 4 | SATA data cables | Latching, correct length for motherboard to bays 5–8 | $15–30 total |
| 1 | PSU | ASRock Steel Legend SL-1000G | $100–160 |
| 1 | UPS | CyberPower CP1500PFCLCD 1500 VA / 1000 W pure sine | $220–275 |
| 1 | Boot SSD | 128–256 GB SATA SSD dedicated to TrueNAS | $20–35 |
| 1–2 | Application SSD | 500 GB–1 TB NVMe; two-device mirror preferred | $40–160 |
| 1 | Additional drive cage | Ventilated 3×5.25-to-5×3.5 cage or quality trayless equivalent | $70–150 |
| 2–3 | Fans | Quality PWM intake/HDD/HBA cooling fans | $20–45 |
| 1 lot | Service parts | Thermal paste, labels, cable ties, spare SATA cable | $15–30 |

Expected incremental total excluding data disks is approximately **$565–1,025**. Deduct
the PSU, UPS, SSDs, or cage if already owned. Do not reduce cost by using a hardware RAID
card, counterfeit HBA, USB boot flash drive, unverified SMR disks, or molded SATA power
splitters. An SFF-8643 cable does not fit the 9207-8i, and an SFF-8087-to-SATA-only
breakout cannot attach the HC550 SAS drives. A proper SAS backplane is an alternative
to the SFF-8482 harness.

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
needs power for eight online HDDs plus a SATA boot SSD if the boot device is not NVMe.
Count the actual PSU harness connectors and the SFF-8482 harness power inputs before
assembly; nine connectors leaves no spare when all nine are used.

For future operation above nine SATA-powered devices, use only manufacturer-approved
additional PSU cables or a reputable drive cage/backplane powered within its rating.
Do not daisy-chain multiple cheap SATA adapters.

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
- Connect bays 1–4 to one 9207-8i SFF-8087 port through the four-lane SFF-8482 forward
  harness. A SAS controller can run these SAS-3 disks at the controller's negotiated
  SAS-2 link rate, which is ample for four HDDs.
- Connect bays 5–8 to four motherboard SATA ports. SATA controllers cannot operate SAS
  drives.
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
- [Phanteks Enthoo Pro manual](https://www.phanteks.com/manuals/Enthoo_Pro_Manual_v1.0.pdf)
- [ASRock SL-1000G specifications](https://asrock.com/Power-Supply/SteelLegend/SL-1000G/)
- [CyberPower CP1500PFCLCD specifications](https://www.cyberpowersystems.com/product/ups/pfc-sinewave/cp1500pfclcd/)
- [WD Ultrastar DC HC550 data sheet](https://documents.westerndigital.com/content/dam/doc-library/en_us/assets/public/western-digital/product/data-center-drives/ultrastar-dc-hc500-series/data-sheet-ultrastar-dc-hc550.pdf)
- [Toshiba DT01ACA series product overview](https://storage.toshiba.com/docs/desktop-pc-hard-drive-documents/dt01aca-product-overview.pdf)
