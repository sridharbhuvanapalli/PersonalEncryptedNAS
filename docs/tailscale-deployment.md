# Tailscale deployment and remote-access runbook

## Tailnet preparation

1. Create or select a dedicated personal tailnet using an identity provider protected
   by MFA. Do not share one login among family members.
2. Enable MagicDNS and device approval.
3. Decide the real users for `group:nas-admins` and `group:family`.
4. Replace every `example.invalid` identity in `config/tailscale/grants.hujson`.
5. Review the policy before saving it. Family receives TCP 443 and DNS TCP/UDP 53;
   administrators additionally receive SSH TCP 22. There is no wildcard port grant.
6. Do not enable Funnel, an exit node, or broad subnet routes.

## One-time NAS enrollment

1. In the Tailscale admin console, create a one-off, short-lived, pre-approved auth key
   tagged `tag:nas`. Do not select Ephemeral and do not make the key reusable.
2. In TrueNAS, open **Apps > Discover Apps > Tailscale > Install**.
3. Set:
   - hostname: `family-nas`;
   - auth key: the short-lived key;
   - Host Network: enabled;
   - Userspace: disabled;
   - Accept DNS: disabled;
   - Advertise Exit Node: disabled;
   - routes: empty;
   - persistent state: enabled/default application storage.
4. Install and wait for Running.
5. In Tailscale Machines, verify hostname, `tag:nas`, operating system, created time,
   and stable 100.x/IPv6 addresses.
6. Revoke the enrollment key immediately. If the TrueNAS form permits clearing the key
   without resetting state, clear it. The persisted node identity—not the key—supports
   future restarts.
7. Restart the app once and confirm no duplicate machine appears.

The repository Compose project under `compose/tailscale` is a kernel-mode lab/recovery
fallback, not the production path. It intentionally contains no auth key.

## Split DNS

1. Deploy the generated tailnet CoreDNS listener on the NAS Tailscale address.
2. In Tailscale **DNS > Add nameserver > Custom**, enter that Tailscale address.
3. Enable **Restrict to search domain** and enter `nas.cloudpathz.com`.
4. Keep MagicDNS enabled. Do not override all client DNS merely for the NAS.
5. Ensure clients use Tailscale DNS settings.
6. From an external client verify:

   ```console
   nslookup cloud.nas.cloudpathz.com
   nslookup photos.nas.cloudpathz.com
   nslookup ops.nas.cloudpathz.com
   ```

All results must be the NAS Tailscale address. A public resolver should not return a
publicly reachable NAS origin.

## Connectivity and performance validation

From a device outside the home Wi-Fi:

```console
tailscale ping family-nas
curl --fail --head https://cloud.nas.cloudpathz.com/status.php
curl --fail --head https://photos.nas.cloudpathz.com
```

Capture `tailscale status --json` and run:

```console
pnasctl --config config/pnas.yaml tailscale-doctor --status-file tailscale-status.json
```

The report should show the expected hostname and a direct peer connection. If DERP is
reported, confirm UDP is not blocked and compare performance with `iperf3`; do not open
router TCP 443 as a workaround. All Tailscale connection types remain WireGuard
encrypted, but relays usually reduce throughput.

## Client and user lifecycle

- Enroll each phone or computer under its real user identity.
- Approve only recognized, patched, screen-locked devices.
- Remove access by removing the user from the group, revoking the device, and invalidating
  Nextcloud/Immich sessions.
- Review Machines monthly for stale, duplicate, expired, or unfamiliar entries.
- Leave server key expiry disabled only for the tagged NAS; retain normal expiry for
  user devices.
- Consider Tailnet Lock only after two independent signing devices and disablement-secret
  recovery have been planned. Tailnet Lock and device approval are mutually exclusive,
  so it is not enabled in this baseline.

## Lost or compromised device

1. Revoke the device from the Tailscale Machines page.
2. Remove its Nextcloud app passwords and active sessions.
3. Remove its Immich sessions and reset the user password if compromise is suspected.
4. Review Tailscale configuration audit logs and NAS application logs.
5. Record the incident and affected time window in the offline operations log.
