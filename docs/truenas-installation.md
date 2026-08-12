# TrueNAS installation

`pnas-install` does not install or modify the TrueNAS base OS. Use the official
TrueNAS Community Edition installer and choose the latest maintenance release
recommended for general users by the Software Status page (25.10.4 when revalidated on
2026-08-12). Check that page again immediately before downloading the installer.

1. Download the ISO only from TrueNAS and verify the published SHA-256 checksum.
2. Write it to dedicated installer media and boot the NAS in UEFI mode.
3. Install only to the Samsung PM830 128 GB boot SSD after confirming model and serial.
4. Create a named administrator; do not enable a shared root login.
5. Configure a static LAN address or DHCP reservation and a trusted TLS certificate.
6. Enable MFA, apply supported maintenance updates, and confirm the UI.
7. Create a least-privilege local automation identity and API key. Put the key in a
   mode-0600 file on the management workstation, never in YAML or shell history.
8. Confirm `/api/docs/`, `system.version_short`, and the configured API compatibility.
9. Create `apps` from only the Inland TN320 1 TB NVMe. Create `app-recovery` separately
   from only the Inland 512 GB SATA SSD. Never combine these unequal devices in one vdev.
10. Configure current database/configuration exports to `app-recovery` and encrypted
    offsite storage. A future ≥1 TB NVMe attaches to the existing TN320 vdev as a mirror
    member; it is not added as a new striped vdev.

Do not install Python packages, services, or arbitrary binaries on the TrueNAS OS.
Run this project from a trusted workstation or a supported management container.

Source: [TrueNAS installation documentation](https://www.truenas.com/docs/scale/gettingstarted/install/)
and [TrueNAS Software Status](https://www.truenas.com/docs/softwarestatus/).
