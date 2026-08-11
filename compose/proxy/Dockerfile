ARG CADDY_VERSION=2.11.3

FROM caddy:${CADDY_VERSION}-builder-alpine AS builder

ARG CADDY_VERSION
RUN xcaddy build "v${CADDY_VERSION}" \
    --with github.com/caddy-dns/cloudflare@a8737d095ad5a48ca031cea6ab704057dbc2d250 \
    --with github.com/caddy-dns/rfc2136@e50b9f25dd68882c76758446195aca0507be3c05

FROM caddy:${CADDY_VERSION}-alpine

COPY --from=builder /usr/bin/caddy /usr/bin/caddy
COPY dns-secret-entrypoint.sh /usr/local/bin/dns-secret-entrypoint

ENTRYPOINT ["/usr/local/bin/dns-secret-entrypoint"]
CMD ["caddy", "run", "--config", "/etc/caddy/Caddyfile", "--adapter", "caddyfile"]
