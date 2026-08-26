# Private HTTPS hosting

Private hosting requires Tailscale. Caddy listens on the dedicated service LAN address
and the NAS Tailscale address. CoreDNS provides separate LAN and tailnet views for
`nas.cloudpathz.com`. Cloudflare is used only for authoritative DNS and ACME DNS-01;
the workflow never creates public NAS A/AAAA records, a Cloudflare Tunnel, router
forwarding, UPnP, or Tailscale Funnel.

For this home, the router is a Firewalla Gold SE. Use **Services > Custom DNS Rules**
for the LAN `nas.cloudpathz.com` mapping, reserve only the TrueNAS management address,
keep the service alias outside the dynamic DHCP range, and verify **Network > NAT
Settings > Port Forwarding** contains no NAS mapping. Preserve the default ingress
firewall; Tailscale needs no inbound rule.

Follow these runbooks in order:

1. [Production installation and commissioning](production-installation-runbook.md)
2. [Tailscale deployment](tailscale-deployment.md)
3. [Cloudflare migration](cloudflare-migration.md)
4. [Technical implementation](technical-implementation.md)
5. [Operations Manager SOP](operations-manager-sop.md)

## Configure and validate

```console
chmod 600 /mnt/apps/secrets/cloudflare-dns-token
pnasctl --config config/pnas.yaml hosting-configure \
  --base-domain nas.cloudpathz.com \
  --nextcloud-url https://cloud.nas.cloudpathz.com \
  --immich-url https://photos.nas.cloudpathz.com \
  --manager-url https://ops.nas.cloudpathz.com \
  --management-lan-address 192.168.1.10 \
  --lan-address 192.168.1.20 \
  --tailscale-address 100.64.0.2 \
  --email OWNER_EMAIL \
  --provider cloudflare \
  --zone cloudpathz.com \
  --credential-file /mnt/apps/secrets/cloudflare-dns-token \
  --certificate-environment staging
pnasctl --config config/pnas.yaml hosting-provider-check
pnasctl --config config/pnas.yaml hosting-dns-write-test \
  --confirmation 'TEST DNS WRITES IN cloudpathz.com USING cloudflare'
```

The provider check performs no write. The confirmed write test creates, verifies, and
deletes one random TXT record. Create and apply a fresh hosting plan after any change.
Apply writes one versioned revision containing Caddy, both CoreDNS views, the private DNS
manifest, deployment environment, and rollback metadata; it does not restart services.

Preview the active revision and print its revision-specific confirmation:

```console
pnasctl --config config/pnas.yaml --state-dir /mnt/app-recovery/hosting-revisions/pnas-state \
  --target truenas-api \
  --project-root /mnt/apps/pnas/repo \
  --api-key-file /mnt/apps/secrets/truenas-deployer-api-token
```

Then rerun with `--execute`, `--api-key-file`, and the exact printed revision-specific
confirmation. The command renders all five service projects into one `pnas-services`
Custom App, submits it through the supported TrueNAS API, waits for the API job, and
requires the final state to be `RUNNING`. It parses only allowlisted environment keys
and never evaluates `deployment.env` as shell code. Test Let's Encrypt staging before
generating and deploying a fresh production revision. Use `hosting-status`,
`hosting-renewal-check`, and the exact
`ROLL BACK PRIVATE HOSTING` confirmation for rollback; after changing the pointer,
preview and deploy the newly active revision with a newly issued short-lived key.
