#!/bin/sh
set -eu

credential_file=${PNAS_DNS_CREDENTIAL_FILE:-/run/secrets/dns_provider_credential}

is_private_ipv4() {
    printf '%s\n' "$1" | awk -F. '
        NF != 4 { exit 1 }
        { for (i = 1; i <= 4; i++) if ($i !~ /^[0-9]+$/ || $i > 255) exit 1 }
        $1 == 10 { exit 0 }
        $1 == 192 && $2 == 168 { exit 0 }
        $1 == 172 && $2 >= 16 && $2 <= 31 { exit 0 }
        $1 == 100 && $2 >= 64 && $2 <= 127 { exit 0 }
        { exit 1 }
    '
}

validate_bind_ip() {
    name=$1
    bind_ip=$2
    case "$bind_ip" in
        fc*:*|fd*:*|FC*:*|FD*:*) ;;
        *)
            if ! is_private_ipv4 "$bind_ip"; then
                echo "$name must be RFC1918, unique-local IPv6, or Tailscale" >&2
                exit 1
            fi
            ;;
    esac
}

validate_bind_ip PNAS_SERVICE_LAN_BIND_IP "${PNAS_SERVICE_LAN_BIND_IP:-}"
validate_bind_ip PNAS_TAILSCALE_BIND_IP "${PNAS_TAILSCALE_BIND_IP:-}"

read_secret() {
    if [ ! -f "$credential_file" ]; then
        echo "DNS credential file is missing: $credential_file" >&2
        exit 1
    fi
    permissions=$(stat -c '%a' "$credential_file")
    if [ "$permissions" != "600" ] && [ "$permissions" != "400" ]; then
        echo "DNS credential file must use mode 0400 or 0600" >&2
        exit 1
    fi
    secret=$(tr -d '\r\n' < "$credential_file")
    if [ -z "$secret" ]; then
        echo "DNS credential file is empty" >&2
        exit 1
    fi
}

case "${PNAS_DNS_PROVIDER:-manual}" in
    cloudflare)
        read_secret
        export CLOUDFLARE_API_TOKEN=$secret
        ;;
    rfc2136)
        read_secret
        export RFC2136_TSIG_KEY=$secret
        ;;
    manual)
        ;;
    *)
        echo "Unsupported DNS provider" >&2
        exit 1
        ;;
esac

exec "$@"
