# Hardware bill of materials

## Acquired platform

| Component | Installed hardware | Disposition |
|---|---|---|
| CPU | Intel Core i7-12700K | Keep; use UHD 770/Quick Sync initially |
| Motherboard | MSI PRO Z790-P WIFI DDR4 | Keep; disable motherboard RAID/RST/VMD |
| Memory | 48 GB DDR4-3200 | Keep only after extended memory validation |
| GPU | NVIDIA RTX 2060 | Optional; remove initially to reduce idle power |
| Chassis | Phanteks Enthoo Pro | Keep; six native 3.5-inch bays plus three 5.25-inch bays |
| Main disks | Four equal 12 TB or four equal 16 TB enterprise SATA CMR disks | One four-wide RAIDZ2 vdev |
| Archive disks | Three 3 TB SATA disks | Two-disk mirror plus one powered-off cold spare |

The board supplies six SATA ports, four M.2 positions, Intel 2.5 Gb Ethernet, a CPU
PCIe 5.0 x16 slot, and a chipset PCIe 4.0 x4 slot. The Enthoo Pro supplies six native
3.5-inch bays and three external 5.25-inch bays. These facts make an eight-port HBA and
a ventilated 5.25-inch drive cage the cleanest path to seven initial disks and later
expansion.

## Additional required parts

Prices are planning ranges in US dollars, not quotations. Used HBAs must be tested and
counterfeit listings avoided.

| Qty | Component | Recommended specification | Planning range |
|---:|---|---|---:|
| 1 | HBA | Genuine LSI SAS 9207-8i, P20 IT-mode firmware | $40–90 |
| 2 | Forward breakout cable | SFF-8087 to 4 × SATA, explicitly **forward** breakout | $20–35 total |
| 1 | PSU | ASRock Steel Legend SL-1000G | $100–160 |
| 1 | UPS | CyberPower CP1500PFCLCD 1500 VA / 1000 W pure sine | $220–275 |
| 1 | Boot SSD | 128–256 GB SATA SSD dedicated to TrueNAS | $20–35 |
| 1–2 | Application SSD | 500 GB–1 TB NVMe; two-device mirror preferred | $40–160 |
| 1 | Additional drive cage | Ventilated 3×5.25-to-5×3.5 cage or quality trayless equivalent | $70–150 |
| 2–3 | Fans | Quality PWM intake/HDD/HBA cooling fans | $20–45 |
| 1 lot | Service parts | Thermal paste, labels, cable ties, spare SATA cable | $15–30 |

Expected incremental total excluding data disks is approximately **$545–980**. Deduct
the PSU, UPS, SSDs, or cage if already owned. Do not reduce cost by using a hardware RAID
card, counterfeit HBA, USB boot flash drive, unverified SMR disks, or molded SATA power
splitters.

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
needs power for six online HDDs, one boot SSD, and possibly other SATA devices. The third
3 TB cold spare should remain disconnected and labeled.

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
| `tank` option A | 4 × 12 TB | RAIDZ2 | 24 TB / 21.8 TiB nominal |
| `tank` option B | 4 × 16 TB | RAIDZ2 | 32 TB / 29.1 TiB nominal |
| `archive` | 2 × 3 TB | Mirror | 3 TB / 2.7 TiB nominal |
| Cold spare | 1 × 3 TB | Offline, labeled | No active capacity |

Operate `tank` below 80 percent: about 17.5 TiB for 4 × 12 TB or 23.3 TiB for
4 × 16 TB before reservations, metadata, snapshots, and application overhead.
Do not mix 12 TB and 16 TB drives within the first RAIDZ2 vdev. The archive mirror is a
separate pool and is not an offsite backup.

## Reference specifications

- [MSI PRO Z790-P WIFI DDR4 specifications](https://us.msi.com/Motherboard/PRO-Z790-P-WIFI-DDR4/Specification)
- [Phanteks Enthoo Pro manual](https://www.phanteks.com/manuals/Enthoo_Pro_Manual_v1.0.pdf)
- [ASRock SL-1000G specifications](https://asrock.com/Power-Supply/SteelLegend/SL-1000G/)
- [CyberPower CP1500PFCLCD specifications](https://www.cyberpowersystems.com/product/ups/pfc-sinewave/cp1500pfclcd/)
