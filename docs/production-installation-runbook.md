# Beginner's production NAS installation and commissioning runbook

## Read this before doing anything

This guide is written so that an operator who has never built a NAS can follow it one
step at a time. Do not skip a **PASS gate**. If a gate fails, stop at that step and use
the failure instructions. Never keep going because a later step might fix it.

The guide uses five location labels:

| Label | Where you perform the action |
|---|---|
| **MAC TERMINAL** | Terminal on the trusted Mac containing this repository |
| **TRUENAS UI** | Web browser connected to the private TrueNAS management address |
| **TRUENAS SHELL** | TrueNAS web Shell or temporary SSH session; only write below `/mnt` |
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
  environment and repository live under `/mnt/apps`.
- Never use `docker compose` from the TrueNAS shell for production configuration. The
  production workflow submits one Custom App through the supported TrueNAS API.

### Final hardware map

| Hardware | Required assignment |
|---|---|
| Samsung PM830 128 GB SATA SSD | TrueNAS `boot-pool` only |
| Inland TN320 1 TB NVMe | Initial single-device `apps` pool |
| Inland 512 GB SATA SSD | Separate `app-recovery` pool |
| Four WD Ultrastar DC HC550 18 TB SAS/512e disks | `tank`, one four-wide RAIDZ2 vdev |
| Four Toshiba DT01ACA300 3 TB SATA/512e disks | `archive`, one four-wide RAIDZ2 vdev |
| Genuine LSI/Broadcom SAS 9300-8i | P16 IT mode; HC550 disks only initially |
| Forward SFF-8643-to-4×SATA breakout | Prefer 75 cm; one populated HBA port |
| Montech Century II 1050W | Installed PSU; use only its original modular cables |
| JONSBO N5 | Three included rear fans plus directed HBA airflow |

Windows 11 is not the base operating system. This deployment installs TrueNAS Community
Edition on the PM830.

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

As of 2026-08-26, TrueNAS 25.10.6 is the current 25.10 maintenance release. Do not use a
TrueNAS 26 beta, RC, nightly, or experimental image for this NAS. Immediately before
downloading, verify the recommendation on
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

Go to **Network > Interfaces**, edit the physical LAN interface, and add the service IP
as an alias using the recorded prefix length. Do not replace the management address.
In **Firewalla > Network Manager > LAN > Edit**, confirm the service IP is inside the
LAN subnet, outside the dynamic DHCP allocation range, and not used by another device.
Do not create a second reservation for the same NAS NIC.
Apply and test changes from the Mac:

```console
ping -c 4 "$PNAS_SERVICE_IP"
```

Expected: both management and service IPs respond independently. If the UI becomes
unreachable, use the local console to revert the interface change.

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
3. Select only the Inland TN320 1 TB NVMe by model and serial.
4. Accept one single-device data vdev for the initial build.
5. Reject any screen showing another disk or a second top-level vdev.
6. Create these child datasets: `app-config`, `databases`, `immich-generated`, `pnas`,
   and `secrets`.

### Step 5.2 — create `app-recovery`

**Where:** TRUENAS UI

1. Start a new pool named `app-recovery`.
2. Select only the Inland 512 GB SATA SSD.
3. Create `database-dumps`, `app-config-exports`, and `hosting-revisions` datasets.

### Step 5.3 — select the Apps pool

**Where:** TRUENAS UI

Go to **Apps > Configuration/Settings > Choose Pool**, select `apps`, and wait until the
header reports **Apps Service Running**.

### Step 5.4 — test both pools

**Where:** TRUENAS SHELL

These commands create and remove harmless test files below `/mnt`:

```console
printf 'apps test\n' > /mnt/apps/pnas/apps-write-test.txt
```

```console
cat /mnt/apps/pnas/apps-write-test.txt
```

```console
rm /mnt/apps/pnas/apps-write-test.txt
```

```console
printf 'recovery test\n' > /mnt/app-recovery/hosting-revisions/recovery-write-test.txt
```

```console
cat /mnt/app-recovery/hosting-revisions/recovery-write-test.txt
```

```console
rm /mnt/app-recovery/hosting-revisions/recovery-write-test.txt
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
6. Create encrypted root datasets `family-files`, `family-photos`, `database-dumps`, and
   `local-backups`.
7. Create `family-files/nextcloud-data` and `family-photos/immich-library`.
8. Export dataset keys and store two encrypted offline copies in separate locations.

### Step 6.2 — create `archive`

**Where:** TRUENAS UI

1. Start **Create Pool** again; never extend `tank`.
2. Name the pool `archive`.
3. Select exactly the four recorded Toshiba DT01ACA300 SATA/512e serials.
4. Create one four-wide RAIDZ2 data vdev.
5. Create encrypted archive datasets appropriate for the family archive.

### Step 6.3 — test topology and encryption

**Where:** TRUENAS UI

In the UI, expand each topology and capture screenshots showing serials and vdev layout.
Run a scrub of each pool and wait for both to finish. With applications still absent,
perform one controlled lock/unlock test of each encrypted root using the offline key.

**PASS gate 6:** `tank` and `archive` are separate ONLINE four-wide RAIDZ2 pools; scrubs
finish with zero errors; keys unlock successfully; no serial appears in two pools.

## Phase 7 — configure protection before adding family data

### Step 7.1 — configure and prove every protection layer

**Where:** TRUENAS UI

1. Under **Data Protection**, schedule monthly scrubs for `tank` and `archive` on
   different days.
2. Schedule weekly SMART short tests and staggered monthly long tests. Do not overlap
   long tests, scrubs, or resilvers.
3. Create periodic snapshots for Nextcloud and Immich datasets with frequent active-data
   retention and daily/weekly/monthly recovery points.
4. Configure the connected UPS/NUT service and an early clean-shutdown policy.
5. Configure system email/alert delivery and send a test notification.
6. Add the Backblaze B2 credential in **Credentials > Backup Credentials**.
7. Create a TrueCloud/Cloud Backup task for critical data with snapshot enabled and a
   strong repository password stored offline. TrueNAS uses Restic for this backup path.
8. Run the backup manually, then restore one small test file to a temporary dataset and
   compare its contents before deleting only the temporary restore.

Do not migrate family data until the restore succeeds.

**PASS gate 7:** SMART schedule, staggered scrubs, snapshots, UPS alert, encrypted offsite
backup, and selected-file restore all pass. Record task IDs and screenshots, never the
repository password.

## Phase 8 — copy the repository to the NAS and create secrets

### Step 8.1 — temporarily enable SSH

**Where:** TRUENAS UI

Edit the named administrator and temporarily enable SSH/Shell access using an SSH key.
Start the SSH service, bind it only to the management interface, and do not create a
Firewalla port forward or Internet allow rule. Disable this access after commissioning.

### Step 8.2 — copy the repository

**Where:** MAC TERMINAL

Reload the values:

```console
cd "/Users/sridharb/Documents/Personal Encrypted NAS"
. .venv/bin/activate
. ./.commissioning.env
```

Create the destination below the `apps` dataset:

```console
ssh "$PNAS_ADMIN_USER@$PNAS_MANAGEMENT_IP" \
  "mkdir -p '$PNAS_NAS_REPO_PATH' '$PNAS_NAS_STATE_PATH'"
```

Copy the repository without caches, Git internals, or local virtual environments:

```console
rsync -a --delete \
  --exclude '.git/' --exclude '.venv/' --exclude '__pycache__/' \
  --exclude '.pytest_cache/' --exclude '.mypy_cache/' --exclude '.ruff_cache/' \
  ./ "$PNAS_ADMIN_USER@$PNAS_MANAGEMENT_IP:$PNAS_NAS_REPO_PATH/"
```

### Step 8.3 — install the CLI into a dataset-based virtual environment

**Where:** TRUENAS SHELL

Run:

```console
cd /mnt/apps/pnas/repo
```

```console
python3 --version
```

Expected: Python 3.12 or newer. If Python or `venv` is unavailable, stop; do not install
an OS package. Use a supported management container instead.

```console
python3 -m venv /mnt/apps/pnas/venv
```

```console
. /mnt/apps/pnas/venv/bin/activate
```

```console
python -m pip install --no-cache-dir -e .
```

```console
pnasctl --help
```

### Step 8.4 — create application directories and environment files

**Where:** TRUENAS SHELL

```console
umask 077
```

```console
mkdir -p /mnt/apps/secrets/manager \
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
chown -R 10001:10001 /mnt/apps/app-config/manager/state
chmod 700 /mnt/apps/app-config/manager/state
```

```console
cp compose/nextcloud/env.example compose/nextcloud/.env
cp compose/immich/env.example compose/immich/.env
cp compose/manager/env.example compose/manager/.env
cp compose/proxy/env.example compose/proxy/.env
chmod 600 compose/nextcloud/.env compose/immich/.env \
  compose/manager/.env compose/proxy/.env
```

### Step 8.5 — create database and manager secrets

**Where:** TRUENAS SHELL

Generate three alphanumeric database/cache passwords without printing them:

```console
openssl rand -hex 32 > /mnt/apps/secrets/nextcloud-db-password
openssl rand -hex 32 > /mnt/apps/secrets/nextcloud-redis-password
openssl rand -hex 32 > /mnt/apps/secrets/immich-db-password
chmod 600 /mnt/apps/secrets/nextcloud-db-password \
  /mnt/apps/secrets/nextcloud-redis-password \
  /mnt/apps/secrets/immich-db-password
```

Create Operations Manager password, session key, and TOTP material through hidden
prompts:

```console
pnasctl manager-init-secrets --output-dir /mnt/apps/secrets/manager
```

Open the mode-0600 `manager-totp-enrollment-uri` only on a trusted device, enroll it in
an authenticator, and store recovery material offline.

**PASS gate 8:** `pnasctl --help` works from the NAS venv; environment files exist; secret
files are 0600; no secret appeared on screen or in shell history.

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

**Where:** TRUENAS SHELL

Activate the NAS environment and load non-secret values:

```console
cd /mnt/apps/pnas/repo
. /mnt/apps/pnas/venv/bin/activate
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
`/mnt/apps/pnas/observations/tailscale-status.json` through the administrative dataset
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

**Where:** TRUENAS SHELL

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

**Where:** TRUENAS SHELL

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

**Where:** TRUENAS SHELL

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

**Where:** TRUENAS SHELL

```console
read -r -s -p 'Paste temporary deployment API key: ' PNAS_DEPLOY_KEY; printf '\n'
```

```console
printf '%s' "$PNAS_DEPLOY_KEY" > /mnt/apps/secrets/truenas-deployer-api-token
chmod 600 /mnt/apps/secrets/truenas-deployer-api-token
unset PNAS_DEPLOY_KEY
```

### Step 11.3 — deployment file gate

**Where:** TRUENAS SHELL

```console
cd /mnt/apps/pnas/repo
. /mnt/apps/pnas/venv/bin/activate
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

**Where:** TRUENAS SHELL

If this is a new shell, reload values and enter the already recorded Tailscale IP:

```console
cd /mnt/apps/pnas/repo
. /mnt/apps/pnas/venv/bin/activate
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

**Where:** TRUENAS SHELL

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

**Where:** TRUENAS SHELL

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

**Where:** TRUENAS SHELL

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

**Where:** TRUENAS SHELL

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

**Where:** TRUENAS SHELL

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

**Where:** TRUENAS SHELL

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
that do not require it. Confirm no deployment API key remains active.

**PASS gate 16:** the reboot, snapshot restore, offsite restore, encryption-key checks,
final configuration export, and access-removal checks all pass.

### Final release checklist

- [ ] PM830 is the only boot-pool disk.
- [ ] `apps` contains only TN320; `app-recovery` contains only Inland 512 GB.
- [ ] `tank` is four HC550 SAS/512e disks in RAIDZ2.
- [ ] `archive` is four Toshiba SATA/512e disks in RAIDZ2.
- [ ] Both HDD pools scrubbed with zero errors.
- [ ] Encryption lock/unlock and two offline key copies were tested.
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
