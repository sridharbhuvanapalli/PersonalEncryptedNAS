# Hardware bill of materials

## Acquired platform

| Component | Installed hardware | Disposition |
|---|---|---|
| CPU | Intel Core i7-12700K | Keep; use UHD 770/Quick Sync initially |
| Motherboard | MSI PRO Z790-P WIFI DDR4 | Keep; disable motherboard RAID/RST/VMD |
| Memory | 48 GB DDR4-3200 | Keep only after extended memory validation |
| GPU | NVIDIA RTX 2060 | Optional; remove initially to reduce idle power |
| Chassis | JONSBO N5 NAS PC Case | Use; 12 hot-swap 3.5-inch bays, 2–4 dedicated 2.5-inch positions, and three included rear 120 mm fans |
| PSU | Montech Century II 1050W | Acquired; retain every original Montech modular cable |
| TrueNAS boot SSD | Samsung SSD PM830 128 GB SATA | Acquired; reuse only after SMART/health validation |
| Application SSD | Inland TN320 1 TB NVMe | Acquired; initial single-device `apps`, future mirror member 1 |
| Recovery SSD | Inland 512 GB 2.5-inch SATA III 6 Gb/s | Acquired; separate single-device `app-recovery` pool |
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
| 1 | HBA | Genuine LSI SAS 9300-8i (SAS3008), P16 IT/HBA-mode firmware; two internal SFF-8643 ports and full-height bracket | $45–100 |
| 1 | HBA-to-backplane cable | Forward SFF-8643 host to 4 × 7-pin SATA-style backplane ports; 75 cm preferred, 60–100 cm acceptable | $9–25 |
| 1 future | Second HBA-to-backplane cable | Same forward SFF-8643-to-4 × 7-pin cable, reserved for a separately approved four-disk `tank` expansion | $9–25 |
| 6 | SATA data cables | Latching cables: four for archive backplane ports and two for the SATA SSDs | $25–55 total |
| 1 | UPS | CyberPower CP1500PFCLCD 1500 VA / 1000 W pure sine | $220–275 |
| 0–1 future | Second application NVMe | At least 1 TB usable capacity; matched endurance preferred; attach as a TN320 mirror member | $50–100 |
| 1–3 | Additional fans | At minimum, directed HBA airflow; add quality PWM HDD intake fans only when measured thermals require them | $10–60 |
| 1 lot | Service parts | Thermal paste, labels, cable ties, spare SATA cable | $15–30 |

Expected initial incremental total excluding data disks and the already acquired case,
PSU, and SSDs is approximately **$340–545**. The future cable and second NVMe add about
**$60–125** when approved. Deduct the UPS, HBA, cables, or fans if already owned. Do not
reduce cost by using a hardware RAID card, counterfeit HBA, USB boot flash drive,
unverified SMR disks, or molded SATA power splitters. The 9300-8i requires a **forward**
SFF-8643-to-4 × 7-pin breakout; SFF-8087,
reverse-breakout, and SFF-8482 drive-end cables are not substitutes for this N5
backplane path. SAS support through the pass-through backplane must be proven with all
four HC550s before creating `tank`.

The N5 includes three rear 120 mm fans. Do not count those as proof of adequate HBA or
drive cooling: retain them initially, add a small directed fan or duct over the 9300-8i
heatsink, and add intake fans only after inspecting clearances and measuring the full
eight-drive burn-in. A 75 cm breakout is the preferred routing length; a 1 m forward
breakout is electrically suitable when its excess is secured in a broad loop outside
fan blades and without tight bends.

## Solid-state pool layout

| Pool | Initial device/layout | Purpose | Future state |
|---|---|---|---|
| `boot-pool` | Samsung PM830 128 GB SATA, single | TrueNAS OS and boot environments only | Replace if health degrades; retain config exports |
| `apps` | Inland TN320 1 TB NVMe, single | Databases, containers, thumbnails, generated media, logs | Attach a second ≥1 TB NVMe to the existing vdev as a mirror member |
| `app-recovery` | Inland 512 GB SATA, single | Nightly DB/config exports and selected app recovery material | Remains separate; never add to `apps`, `tank`, or `archive` |

The 512 GB SATA SSD does not mirror the 1 TB TN320: that would limit `apps` to the
smaller device and SATA write speed. `app-recovery` is a convenient local recovery copy,
not protection from theft, fire, PSU/backplane failure, or destructive administration;
the same critical recovery set must also reach encrypted offsite Restic storage.

## Controller and slot placement

Preferred low-power configuration:

1. Remove the RTX 2060.
2. Enable the i7-12700K integrated graphics.
3. Put the 9300-8i in the CPU-connected PCIe x16 slot, where it can negotiate its native
   PCIe 3.0 x8 link.

If the RTX 2060 is retained, place it in the CPU x16 slot and place the HBA in the
full-length chipset slot operating at PCIe 4.0 x4. Four PCIe 3.0 lanes still provide
more aggregate bandwidth than eight mechanical HDDs normally sustain, but confirm HBA
enumeration, cooling clearance, and throughput during burn-in.

## Power design

The Montech Century II 1050W is a fully modular 140 × 150 × 86 mm ATX supply. Its
single 12 V rail is rated for 87.5 A/1050 W, it has a 135 mm FDB fan, six listed
electrical protections, three SATA harnesses with four connectors each, and a ten-year
warranty. Never use a modular cable from any other PSU:
modular pinouts are not interchangeable even when the connector fits. The initial
configuration needs power for both N5 backplane PCBs plus the Samsung SATA boot SSD.
The N5 backplanes aggregate drive power, so do not budget one PSU connector per HDD.
Populate every input required by the Jonsbo manual or PCB labeling using only the
original Montech harnesses; do not assume one input safely powers a full backplane.

For future operation, use only manufacturer-approved additional PSU cables and keep each
N5 backplane powered within its documented rating. Do not daisy-chain cheap adapters.

The CP1500PFCLCD supplies 1500 VA / 1000 W, sine-wave output, and USB HID communication.
Connect the NAS, network switch, Verizon FiOS ONT, and Firewalla Gold SE only after
measuring total load and preserving adequate shutdown runtime. Connect the UPS USB
management port directly to the NAS for NUT-based shutdown.

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
- Connect the four HC550 backplane data ports to one 9300-8i SFF-8643 port using a
  forward 4 × 7-pin breakout. This provides native SAS-3 connectivity. Reserve the
  second SFF-8643 port for as many as four future SAS disks, but do not connect or add
  them until their ZFS topology and backup impact receive a separate review.
- Connect the four Toshiba backplane data ports to four motherboard SATA ports. SATA
  controllers cannot operate SAS drives. The two SATA SSDs use the remaining two
  motherboard ports, so all six motherboard SATA ports are occupied initially.
- The N5 backplane is a pass-through connection, not a storage controller. Before pool
  creation, confirm all four HC550s enumerate simultaneously as SAS devices with unique
  WWNs, SMART data, correct capacity, and no link resets. If any fail, stop and replace
  the case/backplane path or use direct SFF-8482 cabling outside the hot-swap backplane.
- Verify Power Disable behavior during bench acceptance. If a drive does not spin, use
  a PWDIS-compatible SAS power/backplane solution; do not tape pins or improvise power
  adapters.
- Provide direct intake airflow across all eight 7200-RPM disks and forced airflow over
  the HBA heatsink. The passively cooled server HBA requires directed airflow in a tower
  chassis. Validate steady-state and simultaneous burn-in temperatures, and reject any
  configuration that produces controller resets, link errors, or thermal instability.

The eight disks draw roughly 44 W idle and 61 W during typical read/write activity from
their published values; startup current is materially higher. The 1050 W PSU has ample
capacity, but power-harness quality, connector count, airflow, and staggered test load
remain operational constraints.

## Reference specifications

- [MSI PRO Z790-P WIFI DDR4 specifications](https://us.msi.com/Motherboard/PRO-Z790-P-WIFI-DDR4/Specification)
- [JONSBO N5 specifications and installation manual](https://www.jonsbo.com/en/products/N5Black.html)
- [JONSBO N5 backplane and cabling review](https://nascompares.com/2024/10/04/jonsbo-n5-review/)
- [Broadcom LSI SAS 9300-8i installation guide](https://docs.broadcom.com/doc/12354877)
- [Montech Century II 1050W specifications](https://www.montechpc.com/century-ii-1050w)
- [Samsung 128 GB SSD 830 support](https://www.samsung.com/dk/support/model/MZ-7PC128D/EU/)
- [CyberPower CP1500PFCLCD specifications](https://www.cyberpowersystems.com/product/ups/pfc-sinewave/cp1500pfclcd/)
- [WD Ultrastar DC HC550 data sheet](https://documents.westerndigital.com/content/dam/doc-library/en_us/assets/public/western-digital/product/data-center-drives/ultrastar-dc-hc500-series/data-sheet-ultrastar-dc-hc550.pdf)
- [Toshiba DT01ACA series product overview](https://storage.toshiba.com/docs/desktop-pc-hard-drive-documents/dt01aca-product-overview.pdf)
