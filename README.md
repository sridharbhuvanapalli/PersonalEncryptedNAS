# Personal Encrypted NAS

Safety-first tooling and deployment artifacts for a private family NAS built on
TrueNAS Community Edition, two independent four-drive RAIDZ2 pools, encrypted ZFS
datasets, Nextcloud, Immich, Tailscale, snapshots, and encrypted Restic backups.

This project is deliberately conservative:

- commands default to dry-run;
- storage plans are separated from application;
- disks are identified by serial and stable identifier;
- boot and application devices are never valid data-pool targets;
- no service is designed for public exposure;
- secrets and encryption keys are not stored in configuration or manager state.

It is not accurate to call the whole system end-to-end encrypted. ZFS protects
locked datasets at rest, TLS/Tailscale protect network traffic, and Restic
encrypts backups. While datasets are unlocked, the NAS administrator can access
ordinary Nextcloud and Immich content. Use client-side encryption for material
that must remain unreadable to the NAS administrator; doing so prevents Immich
from generating thumbnails and performing search, facial recognition, and ML.

## Development

```console
python3 -m venv .venv
. .venv/bin/activate
python3 -m pip install -e '.[dev]'
make check
```

Hardware is not required for mock development. Real destructive operations are
disabled unless explicitly configured and approved through a current plan.

See [architecture](docs/architecture.md), [hardware checklist](docs/hardware-checklist.md),
[hardware BOM](docs/hardware-bom.md), [build guide](docs/build-and-transplant-guide.md),
[technical implementation](docs/technical-implementation.md),
[private HTTPS hosting](docs/private-hosting.md),
[Operations Manager SOP](docs/operations-manager-sop.md), and [security policy](SECURITY.md).
