# Private HTTPS hosting

Private hosting requires Tailscale. Caddy listens on the dedicated service LAN address
and the NAS Tailscale address. CoreDNS provides separate LAN and tailnet views for
`nas.cloudpathz.com`. Cloudflare is used only for authoritative DNS and ACME DNS-01;
the workflow never creates public NAS A/AAAA records, a Cloudflare Tunnel, router
forwarding, UPnP, or Tailscale Funnel.

Follow these runbooks in order:

1. [Tailscale deployment](tailscale-deployment.md)
2. [Cloudflare migration](cloudflare-migration.md)
3. [Technical implementation](technical-implementation.md)
4. [Operations Manager SOP](operations-manager-sop.md)

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

Deploy CoreDNS before Caddy, test Let's Encrypt staging, and then generate a new
production revision. Use `hosting-status`, `hosting-renewal-check`, and the exact
`ROLL BACK PRIVATE HOSTING` confirmation for rollback.
