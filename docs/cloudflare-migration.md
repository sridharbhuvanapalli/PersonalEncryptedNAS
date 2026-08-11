# Move cloudpathz.com from GoDaddy DNS to Cloudflare

DNS hosting and domain registration are separate. Move authoritative DNS first. The
registrar can remain GoDaddy indefinitely; transferring registration to Cloudflare is
optional and does not improve Tailscale performance.

## Phase A: inventory and stage DNS

1. Verify access to the GoDaddy registrant account, registrant email, and MFA recovery.
2. Record the domain expiration date, registrar lock, nameservers, and DNSSEC/DS state.
3. Export or manually inventory every record: A, AAAA, CNAME, MX, TXT, CAA, SRV, DKIM,
   DMARC, SPF, verification, redirects, and subdomain delegations.
4. Record which records are business-critical and test them before migration.
5. Add `cloudpathz.com` to Cloudflare using Full setup.
6. Review Cloudflare's scan against the GoDaddy inventory. Add missing records and remove
   invented or obsolete records.
7. Keep existing web records' proxy status consistent unless a separate reviewed change
   is intended. NAS private names receive no public A/AAAA records.
8. Lower relevant TTLs at GoDaddy at least one prior TTL before the cutover when possible.

## Phase B: change authoritative nameservers

1. If DNSSEC is enabled at GoDaddy, disable it/remove the DS record and wait for the
   documented propagation interval before changing nameservers.
2. Copy the two nameservers assigned by Cloudflare exactly.
3. At GoDaddy, replace the existing nameservers with the Cloudflare nameservers.
4. Do not delete the old GoDaddy zone during the transition.
5. Wait for Cloudflare to show the zone as Active.
6. Query multiple resolvers for NS, SOA, website, MX, TXT, and CAA records.
7. Send and receive test email if the domain handles mail. Verify SPF, DKIM, and DMARC.
8. After the zone is stable, enable DNSSEC in Cloudflare and verify the DS chain.

Rollback before Cloudflare is stable consists of restoring the prior GoDaddy nameservers
and DNSSEC state from the recorded inventory.

## Phase C: create the ACME token

1. Create a Cloudflare API token from a custom template.
2. Grant only **Zone / Zone / Read** and **Zone / DNS / Edit**.
3. Limit resources to `cloudpathz.com` only.
4. Save the token alone in `/mnt/apps/secrets/cloudflare-dns-token` and set mode 0600.
5. Never use the Global API Key.
6. Run the read-only provider check, followed by the explicitly confirmed temporary TXT
   write test.
7. Begin with Let's Encrypt staging. Move to production only after private DNS, Caddy,
   renewal, and client trust tests pass.

Cloudflare is not in the application traffic path. It answers public DNS and ACME TXT
queries only. Do not create a Cloudflare Tunnel or orange-cloud proxy record for the NAS.

## Phase D: optional registrar transfer

1. Confirm the domain has not been registered, transferred, or had protected registrant
   contact changes within the last 60 days.
2. Confirm `cloudpathz.com` is Active on Cloudflare authoritative DNS.
3. Verify payment and registrant email in Cloudflare.
4. Unlock the domain at GoDaddy and request its EPP/authorization code only when ready.
5. Start the transfer at Cloudflare and enter the code.
6. Approve the transfer at GoDaddy if offered.
7. Verify the expiration date, auto-renew, contacts, DNSSEC, and registrar lock after
   completion.

References:
[Cloudflare full DNS setup](https://developers.cloudflare.com/dns/zone-setups/full-setup/setup/),
[DNS import/export](https://developers.cloudflare.com/dns/manage-dns-records/how-to/import-and-export/),
and [registrar transfer](https://developers.cloudflare.com/registrar/get-started/transfer-domain-to-cloudflare/).
