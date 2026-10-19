# Beginner's production NAS installation and commissioning runbook

## Read this before doing anything

This guide is written so that an operator who has never built a NAS can follow it one
step at a time. Do not skip a **PASS gate**. If a gate fails, stop at that step and use
the failure instructions. Never keep going because a later step might fix it.

The guide uses the following location labels:

| Label | Where you perform the action |
|---|---|
| **MAC TERMINAL** | Terminal on the trusted Mac containing this repository |
| **TRUENAS UI** | Web browser connected to the private TrueNAS management address |
| **TRUENAS SHELL** | NAS host web Shell or SSH; use `sudo` for administrative work and only write to verified data datasets below `/mnt` |
| **COMMISSIONING CONTAINER** | Apps → pnas-commissioning → Shell → commissioning; select `/bin/bash`, then activate the container-created venv |
| **TAILSCALE CLIENT** | An approved laptop or phone using a network outside the home |
| **PROVIDER UI** | GoDaddy, Cloudflare, Tailscale, Backblaze, or UPS interface |

Commands are shown without a `$` prompt. Copy only the text inside a command block. Run
one block, read its result, and then continue. Text beginning with `Expected:` describes
what success looks like; do not type it.

### Actions this guide never permits

- Never create or extend a pool until the exact model and serial of every selected disk
  have been checked twice.
- Never identify a disk only as `/dev/sdX`; that name can change after a reboot.
- Never put data disks into a motherboard RAID/RST array. TrueNAS must see each disk.
- Never add the future NVMe as a new striped vdev. It becomes the second member of the
  existing `apps` mirror.
- Never create a Firewalla NAT/port-forward mapping for NAS ports 53, 80, or 443.
- Never enable UPnP, Tailscale Funnel, Cloudflare Tunnel, DDNS, or public service A/AAAA
  records.
- Never type a password, API key, encryption key, or Cloudflare token directly in a
  command. This guide uses hidden prompts or mode-0600 files.
- Never install packages into the TrueNAS boot environment. The Python virtual
  environment is created and used inside the commissioning container; its persistent files
  and the repository live on the `apps` data pool.
- Never use `docker compose` from the TrueNAS shell for production configuration. The
  production workflow submits one Custom App through the supported TrueNAS API.

### Final hardware map

| Hardware | Required assignment |
|---|---|
| Samsung PM830 128 GB SATA SSD | TrueNAS `boot-pool` only |
| Inland TN320 512 GB NVMe, serial `IB24AL0512P00879` | Initial single-device `apps` pool; provisional commissioning use after prior read failures |
| Inland 512 GB SATA SSD | Separate `app-recovery` pool |
| Four WD Ultrastar DC HC550 18 TB SAS/512e disks | `tank`, one four-wide RAIDZ2 vdev |
| Four Toshiba DT01ACA300 3 TB SATA/512e disks | `archive`, one four-wide RAIDZ2 vdev |
| Genuine LSI/Broadcom SAS 9300-8i | P16 IT mode; HC550 disks only initially |
| Forward SFF-8643-to-4×SATA breakout | Prefer 75 cm; one populated HBA port |
| Montech Century II 1050W | Installed PSU; use only its original modular cables |
| JONSBO N5 | Three included rear fans plus directed HBA airflow |

Windows 11 is not the base operating system. This deployment installs TrueNAS Community
Edition on the PM830.

## Restart checkpoint — resume commissioning here

The current restart point is **Step 8.3.1**: verify mounted data paths in the host
SSH session, then update the existing container YAML in **8.3.2** and verify CLI help
inside its shell in **8.3.3**.
The CLI entry point exists, but a clean `pnasctl --help` result has not yet been
confirmed: the last error combined `--help` with a second command. Run one command
block at a time at a fresh prompt.

The writable mount migration in **Step 8.3.2** is required before later commands. The earlier
container mounted `/mnt/apps/pnas/repo` read-only at `/workspace`; that was sufficient
for a help check, but cannot create the later configuration, secrets, or state files.
The revised container preserves NAS paths and uses a persistent, container-created
venv. Reopen its shell after saving the updated YAML, then perform Step 8.3.3.
Once help works, continue at **Step 8.4**, then **8.5**, then Phase 9. Do not repeat
pool creation, formatting, secret generation, or completed recovery proofs.

Recorded troubleshooting facts (2026-10-18; verify live state before using):

- Administrator: `truenas_admin`; management: `192.168.1.100/24`; service:
  `192.168.1.110/24`; repository: `/mnt/apps/pnas/repo`.
- The SSH prompt showed hostname `bhuvanapalliNAS`; the planned hostname is
  `family-nas`. Confirm this is the intended NAS and reconcile hostname/Tailscale
  naming before Phase 9. Do not infer a hostname change has already happened.
- Host Python was 3.11.9, below the project's 3.12 requirement. Do not use a host venv.
- The unused `apps` pool on the Inland NVMe reported corruption and repeated kernel
  medium/read errors despite SMART PASSED. A later report showed roughly one full
  device write/read and no recent matching kernel errors. This does not certify the
  SSD or independently confirm the wipe/readback exit status. Keep the disk provisional,
  retain recovery copies elsewhere, and replace it if errors recur.
- The pool was being recreated. Verify `apps` ONLINE, datasets mounted, and Apps Service
  Running; do not assume those gates passed merely because the steps were discussed.

## Phase 0 — prepare the Mac and record all values

### Step 0.1 — open the repository

**Where:** MAC TERMINAL

Run:

```console
cd "/Users/sridharb/Documents/Personal Encrypted NAS"
pwd
```

Expected: the second command prints exactly:

```text
/Users/sridharb/Documents/Personal Encrypted NAS
```

If it says “no such file or directory,” locate the folder containing `pyproject.toml`,
`compose`, `config`, `docs`, and `src`, then run `cd` with that path in quotes.

### Step 0.2 — install the local command-line tools

**Where:** MAC TERMINAL

Run each block separately:

```console
python3 --version
```

Expected: Python 3.12 or newer. If it is older, install a current Python from
<https://www.python.org/downloads/> and reopen Terminal.

```console
python3 -m venv .venv
```

```console
. .venv/bin/activate
```

```console
python -m pip install --upgrade pip
```

```console
python -m pip install -e '.[dev]'
```

```console
make check
```

Expected: lint, type checking, and all tests pass. Any failure is a stop condition.

### Step 0.3 — create the commissioning files with a guided prompt

**Where:** MAC TERMINAL

Have these values in front of you:

- the named TrueNAS administrator username you plan to use;
- two unused private LAN addresses: management and service;
- owner email;
- serial printed on the PM830, both Inland SSDs, all four HC550s, and all four Toshibas.

Run:

```console
pnasctl commissioning-init
```

The command asks one question at a time. For each four-disk group, enter exactly four
serials separated by commas. Do not enter model numbers. The command refuses example,
duplicate, public, or conflicting values and creates:

- `config/pnas.yaml` — production read-only/API configuration;
- `config/pnas-rehearsal.yaml` — mock-only software rehearsal;
- `config/commissioning.yaml` — non-secret build values.

The generated NAS repository path is `/mnt/apps/pnas/repo`. Hosting revision and audit
state is deliberately stored on the separate recovery SSD at
`/mnt/app-recovery/hosting-revisions/pnas-state`.

Export the validated non-secret values for later copy-and-paste commands:

```console
pnasctl commissioning-export-shell
```

```console
. ./.commissioning.env
```

Display only the two addresses to confirm that the correct file was loaded:

```console
printf 'Management: %s\nService: %s/%s\n' \
  "$PNAS_MANAGEMENT_IP" "$PNAS_SERVICE_IP" "$PNAS_LAN_PREFIX"
```

Run the read-only workstation gate:

```console
pnasctl commissioning-check --stage workstation
```

**PASS gate 0:** output contains `"passed": true`. Save the output in the commissioning
log. If it is false, read the failed check's `detail`, correct that item, and rerun.

## Phase 1 — download and verify installation media

### Step 1.1 — download the stable maintenance release

**Where:** MAC plus web browser

This installation uses TrueNAS Community Edition 25.10.7. Do not use a TrueNAS 26 beta,
RC, nightly, or experimental image for this NAS. Immediately before downloading, verify
the recommended production release on
<https://www.truenas.com/docs/softwarestatus/>.

Download from <https://www.truenas.com/download-truenas-community-edition/> into a new
folder named `downloads` inside the repository. Also download or copy the published
SHA-256 checksum for that exact ISO.

Run:

```console
mkdir -p downloads
```

```console
find downloads -maxdepth 1 -type f -name '*.iso' -print
```

Expected: exactly one intended TrueNAS ISO. Remove unrelated ISO files from this folder
before continuing.

Capture its filename and calculate the checksum:

```console
PNAS_ISO_FILE="$(find downloads -maxdepth 1 -type f -name '*.iso' -print -quit)"
```

```console
test -n "$PNAS_ISO_FILE" && shasum -a 256 "$PNAS_ISO_FILE"
```

Compare all 64 checksum characters with the TrueNAS-published checksum. Similar is not
good enough.

### Step 1.2 — create USB media

**Where:** MAC

Use Balena Etcher or another graphical imaging tool to write the verified ISO to a
dedicated USB device. Select the USB by manufacturer and capacity. Do not select an
internal SSD. This guide intentionally does not provide a `dd` command because choosing
the wrong target would overwrite a computer disk.

Create a second USB using MemTest86 or Memtest86+ from its official site. Also download
the current Ubuntu Desktop LTS ISO and use Etcher to create an Ubuntu live USB. Download
the Broadcom 9300-8i/SAS3008 SAS3Flash package before taking the NAS offline. Extract
the Linux `sas3flash` executable and `sas3flash.efi` onto a separate FAT32 utility USB;
these utilities are not built into Ubuntu or the MSI motherboard firmware.

**PASS gate 1:** the checksum matches exactly and all USB devices appear as UEFI boot
choices. Save the ISO filename, source URL, checksum, and date.

## Phase 2 — hardware acceptance

### Step 2.1 — check UEFI settings

**Where:** machine firmware setup

Boot into UEFI setup and verify:

1. UEFI boot is enabled.
2. SATA mode is AHCI, not RAID or Intel RST.
3. CPU is the i7-12700K and memory total is 48 GB.
4. PM830, TN320, Inland 512 GB SSD, and LSI 9300-8i are present.
5. System date/time is correct.
6. The temporary USB is first only for installation; PM830 will be first afterward.

Do not enable overclocking while commissioning storage.

### Step 2.2 — test memory

**Where:** MemTest USB

Run at least four complete passes, preferably overnight. There is no acceptable memory
error count other than zero. Photograph the final screen.

### Step 2.3 — verify the HBA without flashing it

**Where:** the Ubuntu desktop running from the live USB on the NAS itself

The Ubuntu live terminal is a Terminal window inside a temporary Ubuntu session:

1. Connect a monitor and keyboard to the NAS. Use the motherboard video output when the
   i7-12700K integrated graphics is enabled, or the RTX 2060 output if it is active.
2. Insert both the Ubuntu live USB and the separate FAT32 SAS3Flash utility USB.
3. Power on and repeatedly tap `F11` for the MSI boot menu. If it does not appear, press
   `Delete`, open UEFI setup, and select the Ubuntu USB through Boot Override.
4. Select the entry beginning **UEFI:** for the Ubuntu USB.
5. Choose the language and **Try Ubuntu**. Do not choose **Install Ubuntu** or alter a
   NAS disk partition.
6. When the desktop appears, press `Ctrl+Alt+T`. The new window is the Ubuntu live
   terminal and normally shows a prompt containing `ubuntu@ubuntu`.
7. Open **Files**, click the FAT32 utility USB, and note its mounted folder. In Terminal,
   type `cd ` with a trailing space, drag that folder into Terminal, and press Enter.

Confirm the utility is in the current directory, then make only that copied Linux file
executable. This changes the USB file permission; it does not flash the HBA:

```console
pwd
ls -l
chmod u+x ./sas3flash
```

Run only the two read-only inventory commands:

```console
sudo ./sas3flash -listall
sudo ./sas3flash -c 0 -list
```

Expected: one SAS3008/9300-8i controller, Firmware Product ID or mode indicating `IT`,
firmware version beginning `16.00`, and a unique SAS address that is neither all zeroes
nor all `f` characters.

The UEFI alternative is only for a Linux-utility compatibility failure. It is not a
menu built into the HBA. Use a trusted x64 UEFI Shell USB plus the Broadcom-supplied
`sas3flash.efi`, boot it from the MSI `F11` menu, select the FAT32 filesystem such as
`fs0:`, and run only `sas3flash.efi -listall` and `sas3flash.efi -c 0 -list`.

Never type a SAS3Flash command containing `-f`, `-b`, `-e`, `-o`, `download`, or
`reset`. Do not flash because a different package exists. Stop if the card is IR, has
no valid SAS address, identifies incorrectly, or the utility reports incompatibility.

### Step 2.4 — map and test every HDD

**Where:** Ubuntu live terminal

List stable disk identities:

```console
ls -l /dev/disk/by-id/
```

For each of the eight HDDs, copy its complete stable path and run these commands one disk
at a time. In the first command below, type the real path after the hidden prompt; it is
not a password and will be visible as you type.

```console
read -r -p 'Paste one /dev/disk/by-id path: ' PNAS_TEST_DISK
```

```console
sudo smartctl -x "$PNAS_TEST_DISK"
```

```console
sudo smartctl -t long "$PNAS_TEST_DISK"
```

`smartctl` prints the time at which the long test will finish. Wait until then and run:

```console
sudo smartctl -x "$PNAS_TEST_DISK"
```

Perform a non-destructive full-device read after the SMART test:

```console
sudo dd if="$PNAS_TEST_DISK" of=/dev/null bs=16m status=progress
```

On Linux systems that reject lowercase `16m`, use `bs=16M`.

Repeat for all eight HDDs. Record model, serial/WWN, transport, logical sector size,
SMART result, error counters, temperature, and physical bay. SAS HC550s must be SAS and
512e. Toshiba DT01ACA300 disks must be SATA and 512e.

**PASS gate 2:** zero memory errors; all eight HDD long tests pass; no uncorrectable,
pending, growing defect, link reset, or disconnect appears; HDD temperatures stay below
45 °C where practical; the HBA remains stable with directed airflow. Any failure stops
the build.

## Phase 3 — install and configure TrueNAS

### Step 3.1 — install only to the PM830

**Where:** TrueNAS installer

1. Boot the verified installer in UEFI mode.
2. Select only the Samsung PM830 128 GB by model and serial.
3. Confirm UEFI installation.
4. Do not select TN320, Inland 512 GB, any HC550, or any Toshiba.
5. Remove the USB when installation finishes and boot from PM830.

### Step 3.2 — configure the management address

**Where:** TrueNAS console and UI

Use the console network menu to assign the management address recorded in
`config/commissioning.yaml`. In the Firewalla app, open the NAS under **Devices**, tap
its address under **Information**, choose **Reserved**, and enter that same management
address. The reservation takes effect after lease renewal or reboot. From the Mac,
reload the commissioning variables if necessary:

```console
cd "/Users/sridharb/Documents/Personal Encrypted NAS"
. .venv/bin/activate
. ./.commissioning.env
```

Test four packets only:

```console
ping -c 4 "$PNAS_MANAGEMENT_IP"
```

Open the UI:

```console
open "https://$PNAS_MANAGEMENT_IP"
```

During this initial bootstrap only, the browser can show a self-signed certificate
warning. Confirm the address is your private management IP before proceeding. Create the
named administrator from Phase 0, set a unique password, enable MFA, set hostname
`family-nas`, timezone `America/New_York`, NTP, gateway, and DNS.

### Step 3.3 — assign the separate service address

**Where:** TRUENAS UI

1. In Firewalla open **Network > LAN > Edit** for the NAS LAN. Confirm both addresses
   belong to the LAN, the static service address is outside the dynamic DHCP range,
   and neither address belongs to another device. A Firewalla device/history entry
   alone does not prove an address is currently assigned on TrueNAS. Do not create
   another DHCP reservation for the same NIC.
2. In TrueNAS open **Network > Interfaces** (or **System > Network**), locate the
   interface carrying the current working address, and record its settings.
3. Select **⋮ > Edit**. Under **Aliases / Static IP Addresses**, preserve the existing
   address and click **Add** for the missing address. In this deployment the final
   list is `192.168.1.100/24` and `192.168.1.110/24` on the same interface. If `.110`
   is already configured, add `.100`; do not replace `.110`.
4. If DHCP is enabled and adding static addresses requires disabling it, first record
   and preserve the management address, gateway, and DNS settings. Do not blindly
   switch addressing modes or edit a physical member of an existing bridge/LAGG.
5. Save, click **Test Changes**, and test from the Mac during the displayed countdown:

```console
ping -c 4 "$PNAS_MANAGEMENT_IP"
ping -c 4 "$PNAS_SERVICE_IP"
```

Refresh the management UI. If both addresses respond and management access works,
click **Save Changes** before the countdown expires. Otherwise let the changes revert;
use the local Console Setup network menu if access remains lost. Two addresses on one
NIC are address aliases, not separate VLANs or a security boundary.

[TrueNAS interface configuration](https://www.truenas.com/docs/scale/25.10/scaletutorials/network/interfaces/)

### Step 3.4 — update and export configuration

**Where:** TRUENAS UI

Confirm the installed release is the stable 25.10 maintenance release approved by the
Software Status page. Apply only a supported maintenance update, reboot, and verify both
addresses again. Export the TrueNAS configuration with the password secret seed and
store it encrypted and offline.

**PASS gate 3:** UI login plus MFA works; `boot-pool` contains only the PM830; all other
disks are unused; management and service IPs survive a reboot; configuration export is
stored offline.

## Phase 4 — rehearse the software before touching disks

### Step 4.1 — run the complete mock rehearsal

**Where:** MAC TERMINAL

Run:

```console
cd "/Users/sridharb/Documents/Personal Encrypted NAS"
. .venv/bin/activate
. ./.commissioning.env
```

```console
pnas-install --config config/pnas-rehearsal.yaml \
  --fixture tests/fixtures/inventory-four-hc550-18tb.json inventory
```

```console
pnas-install --config config/pnas-rehearsal.yaml \
  --fixture tests/fixtures/inventory-four-hc550-18tb.json preflight
```

```console
pnas-install --config config/pnas-rehearsal.yaml capacity-plan
```

The bundled fixture uses synthetic serials solely to prove the guard behavior. Create
the mock plan with those four fixture serials:

```console
pnas-install --config config/pnas-rehearsal.yaml \
  --fixture tests/fixtures/inventory-four-hc550-18tb.json main-plan \
  --serial DATA4T001 --serial DATA4T002 --serial DATA4T003 --serial DATA4T004 \
  --output /tmp/pnas-main-plan.json
```

```console
python -m json.tool /tmp/pnas-main-plan.json
```

Expected: dry-run/mock output, one four-wide HC550 SAS/512e RAIDZ2 `tank`, and a separate
four-wide 3 TB RAIDZ2 capacity calculation for `archive`. This software does not create
real pools.

**PASS gate 4:** all commands exit successfully and no command claims to mutate TrueNAS.

## Phase 5 — create SSD pools and datasets

All actions in this phase use the TRUENAS UI. Do not use shell `zpool` commands.

### Step 5.1 — create `apps`

**Where:** TRUENAS UI

1. Go to **Storage > Create Pool**.
2. Name it `apps`.
3. Select only the Inland TN320 512 GB NVMe, serial `IB24AL0512P00879`, after checking the physical model and serial.
4. Choose **Stripe** under **Data VDEVs** with that one NVMe only. Leave optional Log, Cache, Spare, Special, and Dedup vdevs empty.
5. Reject any screen showing another disk or a second top-level vdev.
6. Click **Create** and accept the warning that this initial SSD pool has no redundancy.
7. Open **Datasets**, select `apps`, and click **Add Dataset**.
8. Create each of the following as a child of `apps`, one at a time: `app-config`,
   `databases`, `immich-generated`, `pnas`, and `secrets`.
9. For each child, select the **Generic** dataset preset. Do not create a zvol and do
   not select SMB, Multiprotocol, or Apps as the dataset preset.
10. Leave compression, sync, atime, record size, and quotas inherited unless a later
    application step explicitly changes one of them.

Expected layout:

```text
apps
├── app-config
├── databases
├── immich-generated
├── pnas
└── secrets
```

The current TN320 is the only `apps` data vdev. When the future 1 TB NVMe is installed,
attach it as the second member of this existing vdev to convert the single-device vdev
to a mirror. Never add it as another top-level striped vdev.

### Step 5.2 — create `app-recovery`

**Where:** TRUENAS UI

1. Start a new pool named `app-recovery`.
2. Select only the Inland 512 GB SATA SSD.
3. Accept one single-device data vdev and create the pool.
4. In **Datasets**, create `database-dumps`, `app-config-exports`, and
   `hosting-revisions` beneath `app-recovery` using the **Generic** preset.
5. Leave normal dataset properties inherited.

Expected layout:

```text
app-recovery
├── database-dumps
├── app-config-exports
└── hosting-revisions
```

### Step 5.3 — select the Apps pool

**Where:** TRUENAS UI

Go to **Apps > Configuration/Settings > Choose Pool**, select `apps`, and wait until the
header reports **Apps Service Running**. Pool creation alone does not select it for Apps.
If **Install via YAML** is disabled, check this service status before continuing; the
menu is on **Apps > Discover Apps > ⋮ beside Custom App**. If service startup fails,
expand the Alerts/Jobs error and inspect from the host:

```console
sudo midclt call docker.status
sudo midclt call docker.config
sudo zpool status apps
```

An `apps (Exported)` label does not prove it is importable. Use **Storage > Import Pool**
for an existing healthy exported pool. If it is absent or faulted, stop and diagnose;
do not create a new pool over data that needs recovery. For this session only, the user
confirmed the old pool was unused before authorizing its wipe/rebuild. A stale OFFLINE
entry can be disconnected with **Destroy data** unchecked after unsetting the Apps
selection; never disconnect an ONLINE pool merely to clear an old message.

A full-zero wipe followed by a full-device read can test current I/O, but does not erase
this SSD's error history. Do not repeat that destructive test as a normal restart step.

### Step 5.4 — test both pools

**Where:** TRUENAS SHELL

These commands create and remove harmless test files below `/mnt`:

The dataset mount points are initially owned by `root`. Use `sudo tee`; a plain shell
redirection such as `printf ... > /mnt/...` can fail before `sudo` is applied.

```console
printf 'apps test\n' | sudo tee /mnt/apps/pnas/apps-write-test.txt
```

```console
cat /mnt/apps/pnas/apps-write-test.txt
```

```console
sudo rm /mnt/apps/pnas/apps-write-test.txt
```

```console
printf 'recovery test\n' | sudo tee \
  /mnt/app-recovery/hosting-revisions/recovery-write-test.txt
```

```console
cat /mnt/app-recovery/hosting-revisions/recovery-write-test.txt
```

```console
sudo rm /mnt/app-recovery/hosting-revisions/recovery-write-test.txt
```

**PASS gate 5:** both pools show ONLINE, contain only their intended SSD, complete an
initial scrub with zero errors, and pass the file tests.

## Phase 6 — create the two HDD pools

Print the commissioning serials on the Mac before opening the pool wizard:

**Where:** MAC TERMINAL

```console
printf 'MAIN: %s %s %s %s\nARCHIVE: %s %s %s %s\n' \
  "$PNAS_MAIN_SERIAL_1" "$PNAS_MAIN_SERIAL_2" \
  "$PNAS_MAIN_SERIAL_3" "$PNAS_MAIN_SERIAL_4" \
  "$PNAS_ARCHIVE_SERIAL_1" "$PNAS_ARCHIVE_SERIAL_2" \
  "$PNAS_ARCHIVE_SERIAL_3" "$PNAS_ARCHIVE_SERIAL_4"
```

### Step 6.1 — create `tank`

**Where:** TRUENAS UI

1. Go to **Storage > Create Pool**, not Extend.
2. Name the pool `tank`.
3. Select exactly the four recorded 18 TB HC550 SAS/512e serials.
4. Create one four-wide RAIDZ2 data vdev.
5. Reject Stripe, Mirror, RAIDZ1, any SSD, any Toshiba, or the wrong disk count.
6. Review the topology a second time, create the pool, and wait for `tank` to report
   **ONLINE**.

Leave the `tank` pool root itself unencrypted. Create independent encrypted child roots
so a problem with one key does not force all family data to use that same key.

For each name in the following list, perform every numbered action before moving to the
next name:

```text
family-files
family-photos
database-dumps
local-backups
```

1. Go to **Datasets**, select `tank`, and click **Add Dataset**.
2. Enter the exact dataset name and select the **Generic** preset.
3. Expand **Advanced Options** and enable **Encryption**.
4. Select **Key** as the encryption type, not Passphrase.
5. Leave **Generate Key** selected and use `AES-256-GCM`.
6. Leave normal storage properties inherited and click **Save**.
7. Select the new dataset in the tree and inspect its encryption details.
8. Confirm its Encryption Root is itself, for example `tank/family-files`, and its state
   is **Unlocked** or **Key loaded: Yes**. Stop if it inherited encryption from another
   root or encryption is absent.

Create the two application data children after their encrypted parents exist:

1. Select `tank/family-files`, click **Add Dataset**, name it `nextcloud-data`, and use
   the **Generic** preset.
2. Leave **Inherit Encryption** selected. Confirm the resulting encryption root is
   `tank/family-files`.
3. Select `tank/family-photos`, add `immich-library` using **Generic**, and inherit its
   parent's encryption.
4. Confirm its encryption root is `tank/family-photos`.

Expected layout:

```text
tank
├── family-files                 encrypted root, independent key
│   └── nextcloud-data           inherits family-files encryption
├── family-photos                encrypted root, independent key
│   └── immich-library           inherits family-photos encryption
├── database-dumps               encrypted root, independent key
└── local-backups                encrypted root, independent key
```

Do not place the only copy of an encryption key on the NAS. Losing a key makes the
corresponding dataset unrecoverable.

For each of the four encrypted roots:

1. Select the encryption-root dataset in **Datasets**.
2. Open its encryption actions and choose **Export Key**.
3. Download the JSON key to the trusted Mac and give it an unambiguous name, for
   example `tank-family-files-key.json`.
4. If **Export All Keys** is available on the `tank` encryption widget, also download
   the consolidated JSON as `tank-all-dataset-keys.json`; it supplements rather than
   replaces the individually named files.
5. Copy the files to encrypted offline recovery device 1.
6. Copy them to encrypted offline recovery device 2 and store it in a different
   physical location.
7. Open both copies and confirm that they are readable JSON. Record SHA-256 hashes of
   each key file in the commissioning log, but never paste the key contents into the
   log, repository, email, or cloud notes.
8. Remove any unencrypted convenience copies from the Mac only after both encrypted
   offline copies have been verified.

The exported TrueNAS configuration with **Password Secret Seed** is also required for
recovery, but it does not replace these explicit dataset-key exports.

### Step 6.2 — create `archive`

**Where:** TRUENAS UI

1. Start **Create Pool** again; never extend `tank`.
2. Name the pool `archive`.
3. Select exactly the four recorded Toshiba DT01ACA300 SATA/512e serials.
4. Create one four-wide RAIDZ2 data vdev.
5. Review the topology, create the pool, and wait for `archive` to report **ONLINE**.
6. Leave the `archive` pool root unencrypted.
7. Create `archived-files` and `archived-photos` as independent encrypted roots by
   following the same **Generic > Advanced Options > Encryption > Key > Generate Key >
   AES-256-GCM** process used for the four `tank` roots.
8. Confirm each dataset is its own Encryption Root and is unlocked.
9. Export the two individual JSON keys as `archive-archived-files-key.json` and
   `archive-archived-photos-key.json`, then place verified copies on both encrypted
   offline recovery devices.

Expected initial layout:

```text
archive
├── archived-files               encrypted root, independent key
└── archived-photos              encrypted root, independent key
```

Use `archived-files` for old documents, scans, records, and completed projects. Use
`archived-photos` for historical photos and videos that are no longer part of the
active Immich library. Create `long-term-backups` as a third independent encrypted root
only when there is a defined long-retention backup set for it; do not create it merely
as another copy of live data or as the only recovery copy.

If a future archive destination is to be created by a TrueNAS replication task, do not
pre-create that specific destination dataset. Configure the replication encryption and
let the task create its intended destination properties.

### Step 6.3 — test topology and encryption

**Where:** TRUENAS UI

In the UI, expand each topology and capture screenshots showing serials and vdev layout.
Run a scrub of each pool, one at a time, and wait for each to finish. Key-encrypted
datasets do not display the manual **Lock** action in TrueNAS 25.10.7, so do not try to
force a lock through the shell. Instead, confirm all six encryption roots are unlocked,
each root reports itself as its Encryption Root, every individual JSON key exists on
both encrypted offline devices, and the copied files open as valid JSON with matching
recorded SHA-256 hashes. After the later reboot test, confirm all six roots return to the
expected unlocked state.

**PASS gate 6:** `tank` and `archive` are separate ONLINE four-wide RAIDZ2 pools; scrubs
finish with zero errors; all six key exports have two verified offline copies; every
encrypted root is unlocked; and no serial appears in two pools.

## Phase 7 — configure protection before adding family data

### Step 7.1 — configure and prove every protection layer

This procedure is written for TrueNAS Community Edition 25.10.7. In this version, pool
scrub schedules are configured from **Storage**, and the graphical SMART-test scheduler
has been removed. TrueNAS continues automatic drive-health polling, while explicit
short and long self-tests use Cron Jobs under **System > Advanced Settings**.

Record this initial maintenance calendar in the commissioning log:

| Protection task | Initial schedule |
|---|---|
| Weekly SMART short tests | Wednesday, staggered from 20:00 |
| Four `tank` long tests | Days 1, 4, 7, and 10 at 00:30 |
| Four `archive` long tests | Days 13, 15, 17, and 19 at 00:30 |
| `tank` scrub | Day 22 at 00:00 |
| `archive` scrub | Day 28 at 00:00 |
| Hourly snapshots | Minute 5 for Nextcloud; minute 15 for Immich |
| Daily snapshots | 00:35 for Nextcloud; 00:45 for Immich |
| Weekly snapshots | Sunday 01:35 and 01:45 |
| Monthly snapshots | Day 1 at 02:35 and 02:45 |

The dates are starting values. Measure the first scrub and first long test from each
pool. Increase the gaps if the measured duration could overlap another long test or
scrub. Disable all scheduled scrubs and long tests whenever either pool is degraded,
resilvering, replacing a disk, or already scanning.

#### Step 7.1.1 — schedule and prove monthly pool scrubs

**Where:** TRUENAS UI

For `tank`:

1. Open **Storage** and find the `tank` pool.
2. In **Storage Health** or **ZFS Health**, find **Scheduled Scrub** and click
   **Schedule** or **Configure**.
3. Enable the task and select a **Custom** schedule.
4. Set minute `0`, hour `0`, day of month `22`, every month, and every day of week.
5. Set **Threshold Days** to `20` and save.
6. If the Phase 6.3 `tank` scrub just completed and its evidence was recorded, use that
   as the first proof instead of immediately scrubbing the same pool again. Otherwise,
   click **Scrub Now > Start Scrub**.
7. Wait for any newly started scrub to complete and record start time, finish time,
   duration, pool status, and error counts.

After `tank` finishes, repeat for `archive` using day of month `28` and Threshold Days
`20`. Reuse the recorded Phase 6.3 archive scrub as its first proof, or run it manually
if no completed evidence exists. Do not manually scrub both pools simultaneously.

Each scrub passes only when the pool remains **ONLINE/Healthy**, the scan finishes, no
disk becomes degraded or faulted, and no new read, write, or checksum error appears.

#### Step 7.1.2 — verify the eight stable HDD paths again

**Where:** TRUENAS SHELL

Do not use `/dev/sdX` in a recurring job. From the eight paths recorded in Phase 2, use
only whole-disk entries below `/dev/disk/by-id`; never use a path ending in `-part1` or
`-part2`.

Run the following once per path, replacing only the placeholder:

```console
sudo smartctl -i /dev/disk/by-id/REPLACE_WITH_DISK
```

Confirm that the model, serial, capacity, and SAS/SATA transport match the intended
physical HDD. Stop if any path resolves to the PM830, TN320, Inland 512 GB SSD, or a
partition.

#### Step 7.1.3 — prove manual SMART tests before scheduling them

**Where:** TRUENAS SHELL

Start a short test on one HDD:

```console
sudo smartctl -t short /dev/disk/by-id/REPLACE_WITH_DISK
```

Wait until the completion time printed by `smartctl`, then inspect the result:

```console
sudo smartctl -l selftest /dev/disk/by-id/REPLACE_WITH_DISK
```

For the complete SATA or SAS record, run:

```console
sudo smartctl -x /dev/disk/by-id/REPLACE_WITH_DISK
```

Repeat the short test for all eight HDDs. Each must complete without an unrecoverable
read failure. Also inspect reallocated, pending, offline-uncorrectable, reported-
uncorrectable, and SAS grown-defect counts rather than relying only on an overall
`PASSED` line.

Before scheduling long tests, confirm that neither pool is scanning:

```console
sudo zpool status tank
sudo zpool status archive
```

Start one manual long test on a single HC550, wait for the time printed by the command,
and inspect its result:

```console
sudo smartctl -t long /dev/disk/by-id/REPLACE_WITH_ONE_HC550
```

```console
sudo smartctl -l selftest /dev/disk/by-id/REPLACE_WITH_ONE_HC550
```

Later repeat this measurement on one Toshiba. Record actual durations and disk
temperatures. The HC550 test can take many hours; do not assume one day is enough
separation until this measurement proves it.

#### Step 7.1.4 — create weekly SMART short-test Cron Jobs

**Where:** TRUENAS UI

Go to **System > Advanced Settings > Cron Jobs**. Create one job for each HDD:

1. Click **Add**.
2. Enter a description such as `Weekly SMART short - tank disk 1`.
3. Enter the full-path command, substituting that disk's exact stable path:

   ```console
   /usr/sbin/smartctl -t short /dev/disk/by-id/REPLACE_WITH_DISK
   ```

4. Select `root` as **Run As User**.
5. Choose **Custom** schedule, every month and day of month, on Wednesday, using the
   time assigned below.
6. Keep **Hide Standard Error** cleared during commissioning. Standard output can also
   remain visible until the first scheduled test is proven.
7. Select **Enabled** and save.

Use these Wednesday times:

| Disk | Time |
|---|---|
| `tank` disk 1 | 20:00 |
| `tank` disk 2 | 20:05 |
| `tank` disk 3 | 20:10 |
| `tank` disk 4 | 20:15 |
| `archive` disk 1 | 20:30 |
| `archive` disk 2 | 20:35 |
| `archive` disk 3 | 20:40 |
| `archive` disk 4 | 20:45 |

The next morning, run `smartctl -l selftest` against all eight stable paths and confirm
that the newest entry is the scheduled successful short test.

#### Step 7.1.5 — create staggered monthly SMART long-test Cron Jobs

**Where:** TRUENAS UI

Create one more Cron Job for each HDD. Use `root`, enable each job, and use this command
with the correct stable path:

```console
/usr/sbin/smartctl -t long /dev/disk/by-id/REPLACE_WITH_DISK
```

Assign the following custom schedules:

| Disk | Day of month | Time |
|---|---:|---:|
| `tank` disk 1 | 1 | 00:30 |
| `tank` disk 2 | 4 | 00:30 |
| `tank` disk 3 | 7 | 00:30 |
| `tank` disk 4 | 10 | 00:30 |
| `archive` disk 1 | 13 | 00:30 |
| `archive` disk 2 | 15 | 00:30 |
| `archive` disk 3 | 17 | 00:30 |
| `archive` disk 4 | 19 | 00:30 |

At the beginning of each month, compare the calendar with the Wednesday short tests.
Temporarily disable a short-test job if its long test could still be running. If
`zpool status` reports a scrub or resilver, disable upcoming long tests until the scan
finishes and the pool is healthy. Do not schedule manual SMART self-tests for the TN320
NVMe; use its health data and the automatic TrueNAS disk-health alerts.

#### Step 7.1.6 — create Nextcloud periodic snapshots

**Where:** TRUENAS UI

Go to **Data Protection > Periodic Snapshot Tasks** and create four tasks for
`tank/family-files/nextcloud-data`. Leave **Recursive** clear unless child datasets have
deliberately been created under `nextcloud-data`. Enable **Allow Taking Empty
Snapshots** and **Enabled**.

| Tier | Lifetime | Naming schema | Custom schedule |
|---|---|---|---|
| Hourly | 48 hours | `nextcloud-hourly-%Y-%m-%d_%H-%M` | minute 5 of every hour |
| Daily | 30 days | `nextcloud-daily-%Y-%m-%d_%H-%M` | daily at 00:35 |
| Weekly | 12 weeks | `nextcloud-weekly-%Y-%m-%d_%H-%M` | Sunday at 01:35 |
| Monthly | 12 months | `nextcloud-monthly-%Y-%m-%d_%H-%M` | day 1 at 02:35 |

For each row, click **Add**, select the exact dataset, enter the lifetime and naming
schema, configure the custom schedule, confirm it is enabled, and save.

#### Step 7.1.7 — create Immich periodic snapshots

**Where:** TRUENAS UI

Create the same four tasks for `tank/family-photos/immich-library`, using:

| Tier | Lifetime | Naming schema | Custom schedule |
|---|---|---|---|
| Hourly | 48 hours | `immich-hourly-%Y-%m-%d_%H-%M` | minute 15 of every hour |
| Daily | 30 days | `immich-daily-%Y-%m-%d_%H-%M` | daily at 00:45 |
| Weekly | 12 weeks | `immich-weekly-%Y-%m-%d_%H-%M` | Sunday at 01:45 |
| Monthly | 12 months | `immich-monthly-%Y-%m-%d_%H-%M` | day 1 at 02:45 |

These snapshots protect files on the same pool; they are not an independent backup.
They also do not replace application-aware database dumps. Continue writing completed
database dumps to `tank/database-dumps`; do not treat snapshots of live PostgreSQL
database files as the authoritative database backup.

#### Step 7.1.8 — prove selected-file snapshot recovery

**Where:** TRUENAS SHELL and TRUENAS UI

Create a harmless file and record its hash:

```console
printf 'Nextcloud snapshot proof\n' | sudo tee \
  /mnt/tank/family-files/nextcloud-data/pnas-snapshot-proof.txt
```

```console
sudo sha256sum \
  /mnt/tank/family-files/nextcloud-data/pnas-snapshot-proof.txt
```

Run the Nextcloud hourly snapshot task now, or use **Datasets > nextcloud-data > Data
Protection > Create Snapshot**. After the snapshot exists, change the active file:

```console
printf 'This is the changed version\n' | sudo tee \
  /mnt/tank/family-files/nextcloud-data/pnas-snapshot-proof.txt
```

Open **Datasets > nextcloud-data > Manage Snapshots**, find the snapshot just created,
expand its actions, and click **Clone to New Dataset**. Enter or accept an unambiguous
temporary clone name such as `nextcloud-snapshot-proof-clone`, click **Clone**, and then
click **Go to Datasets**. Select the clone and record the complete Mount Point shown by
TrueNAS. Do not click **Rollback**.

Locate and hash the proof file inside the clone, replacing the placeholder with the
mount point just recorded:

```console
sudo find /REPLACE_WITH_CLONE_MOUNT_POINT -type f \
  -name 'pnas-snapshot-proof.txt' -print
```

```console
sudo sha256sum /FULL/PATH/RETURNED/pnas-snapshot-proof.txt
```

The clone's hash must equal the hash recorded before the modification, while the active
dataset must still contain the changed version and remain mounted and writable. After
recording the result, delete exactly the temporary clone from **Datasets**; do not
delete the original dataset or snapshot. Perform a snapshot-creation check for Immich
as well.

#### Step 7.1.9 — configure the connected UPS/NUT service

**Where:** TRUENAS UI and TRUENAS SHELL

The UPS needs both its power connection and its USB or supported network-management
data connection. A power cable alone cannot report UPS state.

1. Go to **System > Services**, find **UPS**, and click Edit.
2. Set Identifier to `ups`.
3. Select **Master** when the UPS USB data cable is connected directly to this NAS.
4. Select the NUT driver that explicitly supports the installed UPS model. Many USB HID
   units use `usbhid-ups`, but do not select it without confirming model support.
5. Set **Port or Hostname** to `auto` for a directly connected USB UPS.
6. Keep the default Monitor User and replace the default Monitor Password with a strong
   unique value. Leave **Remote Monitor** disabled.
7. Set **Shutdown Mode** to **UPS goes on battery** and **Shutdown Timer** to `300`
   seconds. Leave the default shutdown command unchanged unless it is blank.
8. Initially leave **Power off UPS** disabled and set No Communication Warning Time to
   approximately `60` seconds.
9. Save, start the service, and enable **Start Automatically**.

Check communication:

```console
upsc ups@localhost
```

Expected: `ups.status: OL` plus plausible battery charge, runtime, input voltage, and
load. `OL` means on utility line power.

During a quiet maintenance window, keep the USB cable connected and disconnect only the
UPS utility input. Within 30–60 seconds, `upsc ups@localhost` must show `ups.status: OB`
and TrueNAS must create an on-battery alert. Restore utility power before 300 seconds
and verify status returns to `OL` and shutdown is cancelled.

For the full proof, first stop active transfers and applications, verify both pools are
healthy, disconnect UPS utility input, and allow the timer to expire. TrueNAS must shut
down cleanly before the battery is depleted. Restore utility power, boot the NAS, and
confirm both `zpool status tank` and `zpool status archive` are healthy.

No Firewalla change is required for this USB Master-mode configuration. Never expose
NUT port 3493 to the Internet. If a future LAN device must query NUT, keep Remote
Monitor off until a Firewalla rule can restrict access to only that private source IP.

#### Step 7.1.10 — configure system email and immediate alerts

**Where:** TRUENAS UI

1. Go to **System > General Settings**, locate **Email**, and click **Settings**.
2. Select Gmail OAuth, Outlook OAuth, or SMTP. For Gmail/Outlook, complete the provider
   authorization. For SMTP, enter the provider's outgoing server, port, TLS mode,
   username, and app password.
3. Add every intended notification recipient.
4. Click **Send Test Mail**, verify receipt including the spam folder, and save.
5. Click the Alerts bell, then its settings gear, and open **Alert Settings**.
6. Under Alert Services, edit **Email**, enter the recipient, set Level to **Warning**
   and Frequency to **Immediately**.
7. Click **Send Test Alert**, verify receipt, and save.

This step passes only after both the test mail and the separate test alert arrive.

#### Step 7.1.11 — create a restricted Backblaze B2 destination

**Where:** PROVIDER UI

1. In Backblaze, open **B2 Cloud Storage > Buckets > Create a Bucket**.
2. Use a globally unique name such as `cloudpathz-pnas-restic-UNIQUE_SUFFIX`.
3. Make the bucket **Private** and enable provider-side encryption if desired.
4. Do not enable a default Object Lock policy during initial Restic commissioning.
   Object Lock can prevent repository prune/delete operations and cannot simply be
   disabled after it is enabled.
5. Open **Application Keys > Add a New Application Key**.
6. Name it `truenas-cloud-backup` and restrict it to this one bucket.
7. Grant the bucket-level equivalents of list bucket, list files, read files, write
   files, and delete files. Restic retention needs delete permission.
8. Create the key and capture its Key ID and Application Key. The secret is normally
   displayed only once. Never use the Backblaze master key for this task.

#### Step 7.1.12 — add the B2 credential to TrueNAS

**Where:** TRUENAS UI

1. Go to **Credentials > Backup Credentials > Cloud Credentials** and click **Add**.
2. Select **Backblaze B2** and name it `backblaze-b2-pnas`.
3. Enter the Key ID and Application Key in their matching fields.
4. Click **Verify Credentials** and wait for success before saving.

If verification fails, check for reversed fields, spaces copied around either value,
bucket restrictions, DNS, gateway, and outbound HTTPS. Do not add an inbound Firewalla
port-forward; B2 uses an outbound connection.

When exporting the TrueNAS configuration, always include **Password Secret Seed** so
saved cloud credentials can be recovered. Protect that configuration export offline.

#### Step 7.1.13 — create and protect the Restic repository password

**Where:** trusted password manager and encrypted offline recovery media

Generate at least 32 random characters or six to eight random words. Do not reuse a
TrueNAS login, dataset key, Backblaze key, or Cloudflare credential. Record the bucket,
creation date, and purpose with the password in the password manager, then place copies
on both encrypted offline recovery devices in separate physical locations.

TrueNAS stores the password in the task, but it cannot decrypt the Restic repository if
the task/configuration is lost and the offline password is unavailable.

#### Step 7.1.14 — create three Restic Cloud Backup tasks

**Where:** TRUENAS UI

Open **Data Protection** and use **Cloud Backup Tasks** or **TrueCloud Backup Tasks**,
whichever label 25.10.7 displays. Use this Restic-based task, not an ordinary Cloud Sync
copy task. Create one task per source path because each task has one source.

If `backblaze-b2-pnas` is not offered as a credential in this Restic backup screen,
stop and verify the installed 25.10.7 update and Cloud Backup provider support. Do not
silently substitute Cloud Sync, because it does not provide the repository-password and
Restic restore workflow proved by this step.

Create these tasks:

| Name | Source path | B2 folder/prefix | Keep Last | Initial schedule |
|---|---|---|---:|---|
| `b2-database-dumps` | `/mnt/tank/database-dumps` | `/database-dumps` | 30 | daily 03:30 |
| `b2-nextcloud-data` | `/mnt/tank/family-files/nextcloud-data` | `/nextcloud-data` | 30 | daily 05:00 |
| `b2-immich-library` | `/mnt/tank/family-photos/immich-library` | `/immich-library` | 30 | daily 08:00 |

For each task:

1. Click **Add** and select the exact Source Path from the table.
2. Select credential `backblaze-b2-pnas`, the private B2 bucket, and the unique folder
   or prefix from the table.
3. Enter the task Name and Keep Last value.
4. Enter the offline-recorded Restic repository password.
5. Configure the custom schedule and enable the task.
6. Under **Advanced Options**, enable **Use Snapshot**.
7. Leave **Use Absolute Paths** disabled where snapshot mode requires relative paths.
8. Use the default transfer setting and leave pre/post scripts empty.
9. Save.

Use a distinct B2 prefix for every task. Seed the tasks sequentially: temporarily
disable their schedules, run database dumps manually and wait for success, then run
Nextcloud and wait, and finally run Immich. Record duration and uploaded size, move the
recurring start times farther apart if necessary, and then enable the schedules. The
first photo backup can take many hours; later Restic runs should send mostly changes.

#### Step 7.1.15 — create a known cloud-backup proof file

**Where:** TRUENAS SHELL

Use the smaller database-dumps task for the first restore proof:

```console
sudo mkdir -p /mnt/tank/database-dumps/commissioning
```

```console
printf 'cloudpathz TrueNAS B2 restore proof\n' | sudo tee \
  /mnt/tank/database-dumps/commissioning/pnas-b2-proof.txt
```

```console
sudo sha256sum \
  /mnt/tank/database-dumps/commissioning/pnas-b2-proof.txt
```

Record the complete original SHA-256, task name, date, and intended restore destination
in the commissioning log.

#### Step 7.1.16 — run the cloud backup and inspect it

**Where:** TRUENAS UI and PROVIDER UI

1. Under **Data Protection**, open `b2-database-dumps` and click **Run Now/Run Job**.
2. Wait for **SUCCESS**, open its log, and confirm there is no repository,
   authentication, read, upload, or retention error.
3. Confirm a new Restic snapshot appears with the expected timestamp.
4. In Backblaze, confirm repository objects exist only in the intended bucket/prefix.

A successful upload is not restore proof. Continue immediately.

#### Step 7.1.17 — create an encrypted temporary restore target

**Where:** TRUENAS UI

1. In **Datasets**, select the encrypted `tank/local-backups` root.
2. Click **Add Dataset**, name it `cloud-restore-test`, select **Generic**, and inherit
   encryption from `tank/local-backups`.
3. Confirm its mount path is `/mnt/tank/local-backups/cloud-restore-test`, it is
   unlocked, and its encryption root is `tank/local-backups`.

Do not restore over any production dataset.

#### Step 7.1.18 — restore and compare the proof file

**Where:** TRUENAS UI and TRUENAS SHELL

1. Open `b2-database-dumps`, select its newest cloud snapshot, and click **Restore**.
2. Choose **Include from subfolder** and select only
   `commissioning/pnas-b2-proof.txt` when the UI offers path selection.
3. Set Target to `/mnt/tank/local-backups/cloud-restore-test`, check it twice, and start
   the restore.
4. Wait for restore success, then locate the resulting file:

   ```console
   sudo find /mnt/tank/local-backups/cloud-restore-test -type f \
     -name 'pnas-b2-proof.txt' -print
   ```

5. Use the complete path printed by `find`:

   ```console
   sudo cat /FULL/PATH/RETURNED/pnas-b2-proof.txt
   ```

   ```console
   sudo sha256sum /FULL/PATH/RETURNED/pnas-b2-proof.txt
   ```

6. Compare the restored SHA-256 with the original. They must be identical.

After recording the successful proof, use **Datasets** to delete exactly
`tank/local-backups/cloud-restore-test`. Verify that it has no share, application, or
replication dependency. Do not delete its parent, a cloud snapshot, the production B2
task, the bucket, source data, or any encryption key.

Do not migrate family data until every part of this step succeeds.

**PASS gate 7:** both initial scrubs completed without errors; all eight HDD short tests
passed; one timed long test from each pool passed; all short/long schedules are enabled
without planned overlap; all eight snapshot schedules exist and selected-file recovery
matches its original hash; UPS `OL`, `OB`, alert, cancelled-shutdown, and full clean-
shutdown tests pass; both test emails arrive; B2 credentials verify; the Restic password
exists in two encrypted offline locations; all three backups succeed; and the restored
proof-file SHA-256 matches exactly. Record task IDs, dates, durations, hashes, and
screenshots, but never secret values.

## Phase 8 — copy the repository to the NAS and create secrets

### Step 8.1 — temporarily enable SSH

**Where:** TRUENAS UI

1. Edit the actual administrator under **Credentials > Users**. In this deployment,
   the account that successfully logged in was `truenas_admin`, not `bhunasadmin`.
2. Enable **SSH Access**, select an interactive shell such as `bash`, and verify a
   valid home directory. On the Mac display the public key with:

```console
cat ~/.ssh/pnas_commissioning_ed25519.pub
```

3. Paste that complete public-key line into the same user's **Public SSH Key** field.
   Keep password SSH login disabled; do not enable passwordless sudo. Save.
4. In **System > Services > SSH**, confirm port 22 and the intended management
   interface, then start SSH. Do not create Firewalla port forwarding or Internet rules.
   A user SSH key does not start the SSH service. Binding to an interface with both
   aliases may expose SSH on both addresses; do not assume the aliases isolate services.

**Where:** MAC TERMINAL

Reload `.commissioning.env` and check its non-secret values:

```console
cd "/Users/sridharb/Documents/Personal Encrypted NAS"
. ./.commissioning.env
printf 'Admin: %s\nManagement: %s\nService: %s\nRepo: %s\n' \
  "$PNAS_ADMIN_USER" "$PNAS_MANAGEMENT_IP" "$PNAS_SERVICE_IP" "$PNAS_NAS_REPO_PATH"
```

Expected here: `truenas_admin`, `192.168.1.100`, `192.168.1.110`, and
`/mnt/apps/pnas/repo`. If the username is wrong, correct `admin_username` in the canonical
`config/commissioning.yaml` and regenerate the shell export using Phase 0; a temporary shell override alone
is lost on reload. Do not print passwords or tokens.

```console
nc -vz -G 5 "$PNAS_MANAGEMENT_IP" 22
nc -vz -G 5 "$PNAS_SERVICE_IP" 22
```

Management port 22 must succeed. A timeout occurs before key authentication; inspect
IP reachability, SSH service status/binding, and network filtering. `Permission denied
(publickey)` instead means SSH was reached: check the selected username and public key.
The service-address port result depends on the intended SSH listener configuration.

```console
ssh -i ~/.ssh/pnas_commissioning_ed25519 -o IdentitiesOnly=yes \
  "$PNAS_ADMIN_USER@$PNAS_MANAGEMENT_IP"
```

**Where:** TRUENAS SHELL (the new SSH session)

```console
whoami
hostname
id
sudo -v
sudo zfs list -o name,mountpoint,mounted
```

Expected username: `truenas_admin`. Verify the intended hostname and administrative
role; enter the administrator password only at sudo's prompt. Test with a confirmed
mounted data dataset, rather than assuming `/mnt/apps/pnas` already exists:

```console
printf 'temporary SSH test\n' | sudo tee /mnt/app-recovery/ssh-commissioning-test.txt
sudo cat /mnt/app-recovery/ssh-commissioning-test.txt
sudo rm /mnt/app-recovery/ssh-commissioning-test.txt
```

Expected readback: `temporary SSH test`. `No such file or directory` means a parent
path is missing; it is not an SSH failure. Do not create `/mnt/apps` by hand if the
pool is unmounted: that could write into the boot environment. Disable temporary SSH
and remove commissioning access after completion.

### Step 8.2 — copy the repository

**Where:** MAC TERMINAL

Reload the values:

```console
cd "/Users/sridharb/Documents/Personal Encrypted NAS"
. .venv/bin/activate
. ./.commissioning.env
```

Verify that `PNAS_NAS_REPO_PATH` is `/mnt/apps/pnas/repo` and the state path is
`/mnt/app-recovery/hosting-revisions/pnas-state`.

**Where:** TRUENAS SHELL (named administrator SSH session)

```console
findmnt -T /mnt/apps/pnas
findmnt -T /mnt/app-recovery/hosting-revisions
```

Expected: mounted `apps` and `app-recovery` data datasets, not `boot-pool`. If the
`apps/pnas` dataset is missing after rebuilding, create it through **Datasets** using
the Phase 5 layout first. Then create only the repository directory and grant its owner
write access for rsync:

```console
sudo mkdir -p /mnt/apps/pnas/repo
sudo chown "$(id -u):$(id -g)" /mnt/apps/pnas/repo
```

**Where:** MAC TERMINAL

Preview the transfer first; `--delete` removes destination files absent from the source.
Review the destination carefully. The venv, observations, secrets, and state live outside
this repository directory. Exclude local environment files and preserve NAS-specific
app configuration on later transfers:

```console
rsync -an --delete \
  -e 'ssh -i ~/.ssh/pnas_commissioning_ed25519 -o IdentitiesOnly=yes' \
  --exclude '.git/' --exclude '.venv/' --exclude '__pycache__/' \
  --exclude '.pytest_cache/' --exclude '.mypy_cache/' --exclude '.ruff_cache/' \
  --exclude '.env' --exclude '.commissioning.env' \
  ./ "$PNAS_ADMIN_USER@$PNAS_MANAGEMENT_IP:$PNAS_NAS_REPO_PATH/"
```

After reviewing the preview, repeat with `-a` instead of `-an`. This deliberately leaves
`.commissioning.env` out of the transfer; Step 8.3.3 regenerates it on the NAS. Review
any local secret files before transferring; secrets belong outside the repository.
If SSH requests an account password, first test the explicit key command in Step 8.1.
A private-key passphrase prompt is different from an account-password prompt. A file
permission error after authentication requires destination ownership correction, not
password login or passwordless sudo.

### Step 8.3 — install the CLI inside the commissioning container

**Where:** TRUENAS SHELL, then TRUENAS UI, then COMMISSIONING CONTAINER as labelled

Host Python 3.11.9 cannot run this project (requires >=3.12). Do not create a host venv,
install Python/OS packages on the NAS, or activate a container-created venv on the host.
The procedure below replaces the old dataset-based **host** venv section.

#### Step 8.3.1 — prepare the container's data directories

**Where:** TRUENAS SHELL (named administrator SSH session)

Verify the repository root and backing filesystems:

```console
ls -l /mnt/apps/pnas/repo/pyproject.toml
findmnt -T /mnt/apps/pnas/repo
findmnt -T /mnt/apps/secrets
findmnt -T /mnt/apps/app-config
findmnt -T /mnt/app-recovery/hosting-revisions
```

All paths must resolve to the intended mounted data pools. Recreate missing Phase 5
child datasets through the UI before proceeding. Prepare the persistent environment,
secret, and revision directories with elevation, without changing whole-pool ownership:

```console
sudo mkdir -p /mnt/apps/pnas/runtime /mnt/apps/secrets/manager \
  /mnt/app-recovery/hosting-revisions/pnas-state
sudo chmod 700 /mnt/apps/pnas/runtime /mnt/apps/secrets \
  /mnt/apps/secrets/manager /mnt/app-recovery/hosting-revisions/pnas-state
```

#### Step 8.3.2 — create or update the commissioning Custom App

**Where:** TRUENAS UI

Confirm **Apps Service Running** (Step 5.3). Open **Apps > Discover Apps > ⋮ beside
Custom App > Install via YAML**, name it `pnas-commissioning`, and paste the following.
If it already exists, edit its YAML instead of installing a duplicate.

```yaml
services:
  commissioning:
    image: python:3.12-slim
    command: ["sleep", "infinity"]
    restart: unless-stopped
    working_dir: /mnt/apps/pnas/repo
    volumes:
      - type: bind
        source: /mnt/apps/pnas
        target: /mnt/apps/pnas
        bind:
          create_host_path: false
      - type: bind
        source: /mnt/apps/secrets
        target: /mnt/apps/secrets
        bind:
          create_host_path: false
      - type: bind
        source: /mnt/apps/app-config
        target: /mnt/apps/app-config
        bind:
          create_host_path: false
      - type: bind
        source: /mnt/app-recovery/hosting-revisions
        target: /mnt/app-recovery/hosting-revisions
        bind:
          create_host_path: false
```

Save and wait for Running. These writable mounts intentionally allow commissioning
configuration/secrets/state creation; their targets match the NAS paths so later API
payloads still refer to host paths. Do not mount the Docker socket, `/dev`, the boot
filesystem, or all of `/mnt`. No published ports or privileged mode are needed.
The root user in this container can change these mounted datasets; limit its use to
commissioning and stop the app when finished.

This supersedes the earlier read-only `/workspace` mount. The actual repository is
`/mnt/apps/pnas/repo`, not `/mnt/apps/pnas`. The existing `/opt/pnas-venv` environment
is disposable; the replacement below is persistent under the `pnas` dataset.

[TrueNAS YAML Custom Apps](https://apps.truenas.com/managing-apps/installing-custom-apps/)

#### Step 8.3.3 — bootstrap and verify the CLI (restart here)

**Where:** COMMISSIONING CONTAINER

Open **Apps > pnas-commissioning > Shell**, select container `commissioning`, and choose
**`/bin/bash`**. Do not run these commands in Mac Terminal or the host SSH session.
Packages in the first block are installed only into the container, never the NAS OS.
They satisfy the runbook's shell commands and the deployment gate's tool checks.

```console
python --version
ls -l /mnt/apps/pnas/repo/pyproject.toml
apt-get update && apt-get install -y --no-install-recommends \
  bash ca-certificates curl git openssh-client rsync openssl dnsutils
```

Stop if Python is below 3.12 or package installation fails. Then run one block at a time:

```console
python -m venv /mnt/apps/pnas/runtime/venv
. /mnt/apps/pnas/runtime/venv/bin/activate
cd /mnt/apps/pnas/repo
python -m pip install --no-cache-dir .
```

```console
/mnt/apps/pnas/runtime/venv/bin/pnasctl --help
```

Expected: help and a list of commands, without an error. `--help/opt/...` means two
commands were pasted together; press Ctrl+C and enter only the help command on a fresh
line. `pnasctl: not found` usually means the venv is inactive or pip installation failed.
Use the absolute path above to separate PATH issues from installation errors.

Regenerate the non-secret shell values from the copied canonical commissioning file:

```console
umask 077
if [ ! -e .commissioning.env ]; then
  pnasctl commissioning-export-shell \
    --values config/commissioning.yaml --output .commissioning.env
fi
. ./.commissioning.env
```

The export command refuses to overwrite an existing file. If an existing export is
stale, first correct `config/commissioning.yaml`, preserve the old export under a new
backup name, then rerun the export. Do not continue with unknown or stale values. Confirm management/user/repository values
match Step 8.1 before proceeding. Never copy private keys or tokens into this export.

For each new container shell:

```console
. /mnt/apps/pnas/runtime/venv/bin/activate
cd /mnt/apps/pnas/repo
. ./.commissioning.env
```

After container recreation, repeat the container package-install block. The venv and
repository persist; reinstall the project after source changes, because this is a
regular installation rather than an editable installation. Rebuild the venv if the
container Python version/ABI changes. Never execute it using host Python.

**Restart gate:** clean CLI help works, required tools are installed, writable mounts
are present, and commissioning values match the live NAS. Continue at **Step 8.4**.

### Step 8.4 — create application directories and environment files

**Where:** TRUENAS SHELL

```console
sudo mkdir -p /mnt/apps/secrets/manager \
  /mnt/apps/app-config/nextcloud/custom_apps \
  /mnt/apps/app-config/manager/state \
  /mnt/apps/app-config/proxy/data \
  /mnt/apps/app-config/proxy/config \
  /mnt/apps/databases/nextcloud-postgres \
  /mnt/apps/databases/immich-postgres \
  /mnt/apps/immich-generated/machine-learning-cache \
  /mnt/apps/pnas/observations
```

The manager container runs as numeric user `10001`. Give only its state directory to
that account; do not change ownership of the whole `apps` dataset:

```console
sudo chown 10001:10001 /mnt/apps/app-config/manager/state
sudo chmod 700 /mnt/apps/app-config/manager/state
```

**Where:** COMMISSIONING CONTAINER (activate the venv and enter the repository as in 8.3.3)

Create environment files only if absent. On a restart, retain existing edited files;
do not overwrite credentials or production settings with examples.

```console
umask 077
cd /mnt/apps/pnas/repo
for app in nextcloud immich manager proxy; do
  if [ ! -e "compose/$app/.env" ]; then
    cp "compose/$app/env.example" "compose/$app/.env"
  fi
done
chmod 600 compose/nextcloud/.env compose/immich/.env \
  compose/manager/.env compose/proxy/.env
```

### Step 8.5 — create database and manager secrets

**Where:** COMMISSIONING CONTAINER

Generate missing database/cache passwords without printing them. Existing files are
retained on restart. `noclobber` protects against accidental overwrites and `umask`
keeps newly created files private:

```console
umask 077
(
  set -e
  set -o noclobber
  for name in nextcloud-db-password nextcloud-redis-password immich-db-password; do
    if [ ! -e "/mnt/apps/secrets/$name" ]; then
      openssl rand -hex 32 > "/mnt/apps/secrets/$name"
    fi
    test -s "/mnt/apps/secrets/$name"
    chmod 600 "/mnt/apps/secrets/$name"
  done
)
```

Stop if the block fails. Do not display secret file contents.

Create Operations Manager password, session key, and TOTP material through hidden
prompts only on first setup. If these files already exist, retain them and verify the
existing enrollment rather than regenerating secrets:

```console
pnasctl manager-init-secrets --output-dir /mnt/apps/secrets/manager
```

Open the mode-0600 `manager-totp-enrollment-uri` only on a trusted device, enroll it in
an authenticator, and store recovery material offline.

**PASS gate 8:** `pnasctl --help` works inside the commissioning container; environment
files exist; secret files are 0600; no secret appeared on screen or in shell history.

## Phase 9 — install and test Tailscale

### Step 9.1 — prepare the tailnet

**Where:** TAILSCALE PROVIDER UI

1. Enable MFA/SSO, device approval, and MagicDNS.
2. Create a one-use, short-lived, pre-approved key restricted to `tag:nas`.
3. Do not save this enrollment key in a repository file.

### Step 9.2 — install the supported TrueNAS app

**Where:** TRUENAS UI

Go to **Apps > Discover Apps > Tailscale > Install** and set:

- hostname: `family-nas`;
- host network: enabled;
- userspace networking: disabled;
- accept DNS: disabled;
- tag: `tag:nas`;
- exit node, subnet routes, and Funnel: disabled.

Enter the one-use key in the app form. After the app joins, revoke that key in Tailscale
and approve the `family-nas` device. Record its `100.64.0.0/10` address.

### Step 9.3 — update production hosting configuration

**Where:** COMMISSIONING CONTAINER

Activate the container environment and load non-secret values:

```console
cd /mnt/apps/pnas/repo
. /mnt/apps/pnas/runtime/venv/bin/activate
. ./.commissioning.env
```

Record the Tailscale IP in this shell without placing it in history:

```console
read -r -p 'Enter the family-nas Tailscale IP: ' PNAS_TAILSCALE_IP
```

Confirm it begins with `100.`:

```console
printf '%s\n' "$PNAS_TAILSCALE_IP"
```

### Step 9.4 — test from outside the house

**Where:** TAILSCALE CLIENT on cellular/hotspot, not home Wi-Fi

```console
tailscale status
```

```console
tailscale ping family-nas
```

Expected: the NAS is online. `direct` is preferred; a DERP relay is encrypted but slower.

To produce NAS-self diagnostic JSON, open the Tailscale app's workload shell in the
TrueNAS UI and run `tailscale status --json`. Save that output as
`/mnt/apps/pnas/observations/tailscale-status.json` through the commissioning container
shell. Do not use JSON captured from the remote laptop because its `Self` identity is
the laptop, not the NAS.

**PASS gate 9:** NAS is approved/tagged/online, remote ping works, enrollment key is
revoked, and an unauthorized tailnet identity cannot reach the NAS.

## Phase 10 — move authoritative DNS to Cloudflare

### Step 10.1 — preserve GoDaddy DNS

**Where:** GODADDY UI

Export or screenshot every record, TTL, mail entry, verification record, current
nameserver, and DNSSEC setting. Confirm unrelated email/web services currently work.

### Step 10.2 — activate Cloudflare authoritative DNS

**Where:** CLOUDFLARE and GODADDY UI

1. Add `cloudpathz.com` to Cloudflare using Full setup.
2. Compare Cloudflare's imported records line by line with the GoDaddy record.
3. Copy the two Cloudflare-assigned nameservers.
4. At GoDaddy, replace only the authoritative nameservers.
5. Wait until Cloudflare reports **Active**.
6. After stable operation, enable DNSSEC and verify the DS chain.

**Where:** MAC TERMINAL

Verify using two independent resolvers:

```console
dig NS cloudpathz.com @1.1.1.1
```

```console
dig NS cloudpathz.com @8.8.8.8
```

Both must return Cloudflare nameservers.

### Step 10.3 — create and store the scoped Cloudflare token

**Where:** CLOUDFLARE UI

Create a custom token limited to `cloudpathz.com` with only:

- Zone: DNS: Edit;
- Zone: Zone: Read.

Do not use a Global API Key. Copy the token once.

**Where:** COMMISSIONING CONTAINER

Use a hidden prompt so the token never appears in history or on screen:

```console
read -r -s -p 'Paste Cloudflare token, then press Enter: ' PNAS_CF_TOKEN; printf '\n'
```

```console
printf '%s' "$PNAS_CF_TOKEN" > /mnt/apps/secrets/cloudflare-dns-token
chmod 600 /mnt/apps/secrets/cloudflare-dns-token
unset PNAS_CF_TOKEN
```

Confirm that the public internet has no NAS service addresses:

```console
dig A cloud.nas.cloudpathz.com @1.1.1.1
dig AAAA cloud.nas.cloudpathz.com @1.1.1.1
```

Expected: no routable NAS A or AAAA answer.

**PASS gate 10:** Cloudflare is authoritative; unrelated DNS still works; scoped token is
0600; public NAS A/AAAA records do not exist.

## Phase 11 — create the two TrueNAS API identities

### Step 11.1 — read-only Operations Manager identity

**Where:** TRUENAS UI

1. Go to **Credentials > Users > Add**.
2. Create `pnas-observer` with **Readonly Admin** access and no SSH access.
3. Create an API key named `operations-manager-readonly`.
4. Set an expiration/rotation date appropriate for household operations.
5. Copy the key before closing the one-time dialog.

**Where:** COMMISSIONING CONTAINER

Store it through a hidden prompt:

```console
read -r -s -p 'Paste read-only TrueNAS API key: ' PNAS_READ_KEY; printf '\n'
```

```console
printf '%s' "$PNAS_READ_KEY" > /mnt/apps/secrets/truenas-readonly-api-token
chmod 600 /mnt/apps/secrets/truenas-readonly-api-token
unset PNAS_READ_KEY
```

### Step 11.2 — temporary Custom App deployment identity

**Where:** TRUENAS UI

Create a local `pnas-deployer` user/group and a custom privilege containing `APPS_WRITE`,
its read access, and `SYSTEM_GENERAL_READ`. The last role permits the deployment guard
to verify the TrueNAS release before changing an app. Link the privilege to that local
group. Do not grant shell access.
Create a short-expiry API key named `initial-pnas-custom-app-deployment`.

If the installed maintenance release does not expose an APPS_WRITE custom privilege in
the UI, stop and review the installed API/RBAC documentation. Do not silently substitute
a permanent Full Admin key.

**Where:** COMMISSIONING CONTAINER

```console
read -r -s -p 'Paste temporary deployment API key: ' PNAS_DEPLOY_KEY; printf '\n'
```

```console
printf '%s' "$PNAS_DEPLOY_KEY" > /mnt/apps/secrets/truenas-deployer-api-token
chmod 600 /mnt/apps/secrets/truenas-deployer-api-token
unset PNAS_DEPLOY_KEY
```

### Step 11.3 — deployment file gate

**Where:** COMMISSIONING CONTAINER

```console
cd /mnt/apps/pnas/repo
. /mnt/apps/pnas/runtime/venv/bin/activate
pnasctl commissioning-check --stage deployment \
  --project-root /mnt/apps/pnas/repo \
  --config config/pnas.yaml \
  --values config/commissioning.yaml
```

**PASS gate 11:** output contains `"passed": true`. Fix every listed path or permission
before proceeding.

## Phase 12 — configure, plan, and deploy staging services

This phase deploys Nextcloud, Immich, Operations Manager, CoreDNS, and Caddy as one
TrueNAS-managed Custom App named `pnas-services`. It does not run Docker directly.

### Step 12.1 — configure private hosting

**Where:** COMMISSIONING CONTAINER

If this is a new shell, reload values and enter the already recorded Tailscale IP:

```console
cd /mnt/apps/pnas/repo
. /mnt/apps/pnas/runtime/venv/bin/activate
. ./.commissioning.env
read -r -p 'Enter the family-nas Tailscale IP: ' PNAS_TAILSCALE_IP
```

Run:

```console
pnasctl --config config/pnas.yaml --state-dir "$PNAS_NAS_STATE_PATH" \
  hosting-configure \
  --base-domain nas.cloudpathz.com \
  --nextcloud-url https://cloud.nas.cloudpathz.com \
  --immich-url https://photos.nas.cloudpathz.com \
  --manager-url https://ops.nas.cloudpathz.com \
  --management-lan-address "$PNAS_MANAGEMENT_IP" \
  --lan-address "$PNAS_SERVICE_IP" \
  --tailscale-address "$PNAS_TAILSCALE_IP" \
  --email "$PNAS_OWNER_EMAIL" \
  --provider cloudflare \
  --zone cloudpathz.com \
  --credential-file /mnt/apps/secrets/cloudflare-dns-token \
  --certificate-environment staging
```

### Step 12.2 — test Cloudflare access

**Where:** COMMISSIONING CONTAINER

The first command is read-only:

```console
pnasctl --config config/pnas.yaml --state-dir "$PNAS_NAS_STATE_PATH" \
  hosting-provider-check
```

The next command creates, verifies, and deletes one random test TXT record:

```console
pnasctl --config config/pnas.yaml --state-dir "$PNAS_NAS_STATE_PATH" \
  hosting-dns-write-test \
  --confirmation 'TEST DNS WRITES IN cloudpathz.com USING cloudflare'
```

Expected: token active, zone visible, temporary record created/verified/deleted.

### Step 12.3 — create and approve the revision

**Where:** COMMISSIONING CONTAINER

```console
pnasctl --config config/pnas.yaml --state-dir "$PNAS_NAS_STATE_PATH" hosting-plan
```

The output prints a plan path and an exact confirmation. Copy both. Review the plan with:

```console
read -r -p 'Paste the printed plan path: ' PNAS_PLAN_PATH
python -m json.tool "$PNAS_PLAN_PATH"
```

Confirm it lists only the three private hostnames, private addresses, Cloudflare DNS-01,
and `persistent_public_records: false`. Then apply using the exact printed phrase:

```console
read -r -p 'Paste the exact CONFIGURE PRIVATE HTTPS confirmation: ' PNAS_PLAN_CONFIRMATION
pnasctl --config config/pnas.yaml --state-dir "$PNAS_NAS_STATE_PATH" \
  hosting-apply --plan "$PNAS_PLAN_PATH" \
  --confirmation "$PNAS_PLAN_CONFIRMATION"
```

### Step 12.4 — preview the TrueNAS API deployment

**Where:** COMMISSIONING CONTAINER

```console
pnasctl --config config/pnas.yaml --state-dir "$PNAS_NAS_STATE_PATH" \
  hosting-deploy --target truenas-api \
  --project-root /mnt/apps/pnas/repo
```

Expected: `executed: false`, target `truenas-api`, Custom App `pnas-services`, rendered
YAML path, revision ID, and exact deployment confirmation.

Review the generated YAML without displaying secret values—it contains secret file paths
only:

```console
read -r -p 'Paste the rendered_compose path: ' PNAS_RENDERED_COMPOSE
python -c 'import sys,yaml; d=yaml.safe_load(open(sys.argv[1])); print(sorted(d["services"])); print(sorted(d["networks"]))' "$PNAS_RENDERED_COMPOSE"
```

Expected services include Nextcloud, Immich, their databases/caches, manager, two DNS
listeners, and Caddy. Expected networks include separate Nextcloud/Immich backends plus
`pnas_private` and `pnas_management`.

### Step 12.5 — execute through the supported API

**Where:** COMMISSIONING CONTAINER

```console
read -r -p 'Paste the exact DEPLOY PRIVATE HOSTING confirmation: ' PNAS_DEPLOY_CONFIRMATION
```

```console
pnasctl --config config/pnas.yaml --state-dir "$PNAS_NAS_STATE_PATH" \
  hosting-deploy --target truenas-api --execute \
  --confirmation "$PNAS_DEPLOY_CONFIRMATION" \
  --project-root /mnt/apps/pnas/repo \
  --api-username pnas-deployer \
  --api-key-file /mnt/apps/secrets/truenas-deployer-api-token
```

Expected: action `created` or `updated`, state `RUNNING`, API version `25.10`, and no
public service records. In **TRUENAS UI > Apps**, verify `pnas-services` is RUNNING.

If it fails, do not rerun repeatedly. Open the app job/log in TrueNAS, record the first
error, correct it, generate a fresh plan if configuration changed, and retry once.

**PASS gate 12:** provider test cleaned up; plan and revision are approved; API deployment
reports RUNNING; TrueNAS owns the Custom App.

## Phase 13 — configure split DNS and test staging

### Step 13.1 — configure DNS views

**Where:** FIREWALLA MOBILE APP

1. From the Firewalla box screen tap **Services > Custom DNS Rules > Add Custom DNS
   Rule**.
2. Enter `nas.cloudpathz.com` as the domain and the NAS service IP as the address, then
   save. Firewalla normally applies a parent-domain rule to its subdomains.
3. Confirm LAN clients receive Firewalla as their DNS server through LAN DHCP. Do not
   configure a public resolver directly on the test client.
4. Test all three names. If the installed Firewalla release does not apply the parent
   rule, add explicit Custom DNS Rules for `cloud.nas.cloudpathz.com`,
   `photos.nas.cloudpathz.com`, and `ops.nas.cloudpathz.com`, each pointing to the
   service IP.

Do not use Firewalla SSH or an unsupported `dnsmasq_local` customization. The supported
Custom DNS Rules UI replaces the generic conditional-forward instruction. Tailnet
clients still use the Tailscale restricted nameserver and NAS tailnet CoreDNS listener.

**Where:** TAILSCALE DNS UI

Add the NAS Tailscale IP as a restricted nameserver for only `nas.cloudpathz.com`.

### Step 13.2 — test LAN answers

**Where:** MAC on home LAN

```console
dig +short cloud.nas.cloudpathz.com
dig +short photos.nas.cloudpathz.com
dig +short ops.nas.cloudpathz.com
```

Every answer must be the service LAN IP.

Let's Encrypt staging certificates are intentionally untrusted. Use `--insecure` only in
these three staging tests:

```console
curl --insecure --fail --show-error https://cloud.nas.cloudpathz.com/status.php
```

```console
curl --insecure --fail --show-error https://photos.nas.cloudpathz.com/api/server/ping
```

```console
curl --insecure --fail --show-error https://ops.nas.cloudpathz.com/healthz
```

### Step 13.3 — test remote answers

**Where:** TAILSCALE CLIENT outside the home

Run the same three `dig +short` commands. Every answer must be the NAS Tailscale IP. Run
the same three staging curl tests.

### Step 13.4 — prove the services are not public

**Where:** any non-tailnet external device or public resolver

```console
dig A cloud.nas.cloudpathz.com @1.1.1.1
dig AAAA cloud.nas.cloudpathz.com @1.1.1.1
```

Expected: no routable address. In Firewalla open **Network > NAT Settings > Port
Forwarding**. Confirm no manual or UPnP-created mapping points to either NAS address on
ports 53, 80, or 443. Disable UPnP for the NAS LAN unless another documented device
requires it; if it must remain enabled, restrict it to only the required network and
continue verifying that the NAS has no mapping. Preserve Firewalla's default ingress
firewall rule—never pause or delete it. Tailscale needs outbound connectivity only and
requires no Firewalla port forward or inbound allow rule.

**PASS gate 13:** LAN and tailnet return their respective private addresses; all three
staging endpoints respond; public DNS and WAN expose nothing.

## Phase 14 — issue production certificates

### Step 14.1 — create a fresh production revision

**Where:** COMMISSIONING CONTAINER

Repeat hosting configuration with production ACME:

```console
pnasctl --config config/pnas.yaml --state-dir "$PNAS_NAS_STATE_PATH" \
  hosting-configure \
  --base-domain nas.cloudpathz.com \
  --nextcloud-url https://cloud.nas.cloudpathz.com \
  --immich-url https://photos.nas.cloudpathz.com \
  --manager-url https://ops.nas.cloudpathz.com \
  --management-lan-address "$PNAS_MANAGEMENT_IP" \
  --lan-address "$PNAS_SERVICE_IP" \
  --tailscale-address "$PNAS_TAILSCALE_IP" \
  --email "$PNAS_OWNER_EMAIL" \
  --provider cloudflare \
  --zone cloudpathz.com \
  --credential-file /mnt/apps/secrets/cloudflare-dns-token \
  --certificate-environment production
```

Create a new plan:

```console
pnasctl --config config/pnas.yaml --state-dir "$PNAS_NAS_STATE_PATH" hosting-plan
```

Repeat Steps 12.3 through 12.5 with the newly printed plan path, plan confirmation,
revision, and deployment confirmation. Never reuse the staging plan or confirmation.

### Step 14.2 — test production TLS without bypasses

**Where:** MAC on LAN and then external TAILSCALE CLIENT

Do not use `--insecure`:

```console
curl --fail --show-error https://cloud.nas.cloudpathz.com/status.php
```

```console
curl --fail --show-error https://photos.nas.cloudpathz.com/api/server/ping
```

```console
curl --fail --show-error https://ops.nas.cloudpathz.com/healthz
```

Inspect the certificate:

```console
openssl s_client -connect "$PNAS_SERVICE_IP:443" \
  -servername cloud.nas.cloudpathz.com </dev/null
```

**Where:** COMMISSIONING CONTAINER

Run the built-in check:

```console
pnasctl --config config/pnas.yaml --state-dir "$PNAS_NAS_STATE_PATH" \
  hosting-renewal-check --service nextcloud
```

Expected: correct hostname/SAN, publicly trusted chain, valid dates, and no browser
warning.

### Step 14.3 — revoke the temporary deployment key

**Where:** TRUENAS UI

Delete or revoke `initial-pnas-custom-app-deployment` after the accepted deployment.

**Where:** COMMISSIONING CONTAINER

Remove only the now-revoked local copy:

```console
rm /mnt/apps/secrets/truenas-deployer-api-token
```

It can be recreated with a new short-expiry key for a reviewed future deployment.

**PASS gate 14:** production TLS passes without bypasses on LAN and tailnet; public
exposure remains absent; temporary deployment key is revoked and removed.

## Phase 15 — initialize applications and Operations Manager

### Step 15.1 — Nextcloud

**Where:** WEB BROWSER on the home LAN

Open `https://cloud.nas.cloudpathz.com` from the LAN. Complete the first-run administrator
setup, create individual family accounts, enable MFA, set quotas, select cron/background
jobs, disable anonymous public sharing, and test one upload/download with a known hash.

### Step 15.2 — Immich

**Where:** WEB BROWSER on the home LAN

Open `https://photos.nas.cloudpathz.com`, create the owner account, then individual family
accounts. Upload a small test photo/video, wait for thumbnail and metadata processing,
and confirm download/playback. Immich facial recognition organizes photos; it does not
authenticate NAS users.

### Step 15.3 — Operations Manager

**Where:** WEB BROWSER on the home LAN

Open `https://ops.nas.cloudpathz.com`, sign in with the manager password and TOTP, and
confirm:

- Mode is `live`, never `mock`;
- timestamp is current;
- `tank`, `archive`, `apps`, and `app-recovery` are present and healthy;
- application `pnas-services` is running;
- alerts match TrueNAS.

The manager is deterministic read-only automation, not an autonomous AI agent. A planned
dashboard action must report `executed: false`.

**PASS gate 15:** Nextcloud and Immich functional tests pass; manager is live/MFA
protected; no database, cache, or manager direct host port is reachable.

## Phase 16 — reboot, recovery, and final handoff

### Step 16.1 — reboot test

**Where:** TRUENAS UI

Perform a controlled reboot. Wait for TrueNAS to return, then from the Mac run:

```console
ping -c 4 "$PNAS_MANAGEMENT_IP"
```

```console
curl --fail --show-error https://cloud.nas.cloudpathz.com/status.php
curl --fail --show-error https://photos.nas.cloudpathz.com/api/server/ping
curl --fail --show-error https://ops.nas.cloudpathz.com/healthz
```

In TrueNAS, verify all four pools ONLINE, Tailscale running, `pnas-services` RUNNING, no
unexpected resilver, and no critical alert.

### Step 16.2 — repeat recovery proofs

**Where:** TRUENAS UI and TRUENAS SHELL

1. Restore one snapshot file to a temporary path and compare it.
2. Restore one offsite Restic/TrueCloud file to a temporary dataset and compare it.
3. Confirm both offline dataset-key copies are readable.
4. Export the final TrueNAS configuration with password secret seed.
5. Copy database/config exports and hosting revision state to `app-recovery` and offsite.

### Step 16.3 — disable temporary access

**Where:** TRUENAS UI

Stop temporary SSH if it is no longer needed and remove SSH/shell access from accounts
that do not require it. Confirm no deployment API key remains active. Stop the
`pnas-commissioning` app after commissioning; it has writable access to secrets and
configuration. Retain its dataset files for a reviewed future maintenance session.

**PASS gate 16:** the reboot, snapshot restore, offsite restore, encryption-key checks,
final configuration export, and access-removal checks all pass.

### Final release checklist

- [ ] PM830 is the only boot-pool disk.
- [ ] `apps` contains only TN320; `app-recovery` contains only Inland 512 GB.
- [ ] `tank` is four HC550 SAS/512e disks in RAIDZ2.
- [ ] `archive` is four Toshiba SATA/512e disks in RAIDZ2.
- [ ] Both HDD pools scrubbed with zero errors.
- [ ] All six encryption roots are unlocked and have two verified offline key copies.
- [ ] Snapshot and encrypted offsite restore tests passed.
- [ ] UPS event, alert, and shutdown policy were tested.
- [ ] LAN split DNS returns service IP; tailnet split DNS returns Tailscale IP.
- [ ] Public DNS returns no NAS address; Firewalla has no NAS port mapping, DMZ, or UPnP exposure.
- [ ] Production TLS passes for all three hostnames without bypasses.
- [ ] Nextcloud, Immich, and Operations Manager passed functional/MFA tests.
- [ ] Reboot test passed and all services returned automatically.
- [ ] Temporary SSH and deployment API key were removed.
- [ ] UniFi Network control remains on the laptop during initial NAS operation.
- [ ] Final configuration export, source commit, checksums, database dumps, hosting
      revisions, and commissioning log are present in the recovery set.

Only after every item passes should family data be migrated. Move a small sample first,
verify permissions and backups, then migrate in controlled batches.

## Failure and rollback quick reference

Stop immediately for a wrong serial, memory error, SMART failure, HBA reset, unexpected
public DNS answer, WAN-reachable service, failed TLS hostname, missing encryption-key
copy, failed restore, degraded pool, or Operations Manager mock/degraded state.

To point hosting back to the prior generated revision:

```console
pnasctl --config config/pnas.yaml --state-dir "$PNAS_NAS_STATE_PATH" \
  hosting-rollback --confirmation 'ROLL BACK PRIVATE HOSTING'
```

Then preview and deploy the newly active revision through the TrueNAS API using a newly
created short-expiry deployment key. Rollback changes configuration; it does not excuse
skipping DNS, TLS, exposure, application, and restore tests.

Focused references:

- [Hardware deployment validation](hardware-deployment-validation.md)
- [TrueNAS installation](truenas-installation.md)
- [Tailscale deployment](tailscale-deployment.md)
- [Cloudflare migration](cloudflare-migration.md)
- [Private hosting](private-hosting.md)
- [Backup](backup.md) and [recovery](recovery.md)
- [Operations Manager SOP](operations-manager-sop.md)
