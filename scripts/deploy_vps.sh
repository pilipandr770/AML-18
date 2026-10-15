#!/usr/bin/env bash
# Deploy AML+18 (lean hosted stack) to a VPS that already runs Traefik on 80/443.
#
#   scripts/deploy_vps.sh root@187.124.6.120 aml.example.com [path/to/ssh_key]
#
# What it does (idempotent; safe to re-run to update):
#   1. ships the COMMITTED sources (git archive HEAD) to /opt/aml18 on the server
#   2. creates /opt/aml18/.env.vps once (random POSTGRES_PASSWORD and SECRET_KEY generated on the
#      server; ANTHROPIC_API_KEY copied from your local .env over stdin, never on a command line)
#   3. builds and starts the stack with `nice` so neighbours keep their CPU
# It does NOT touch other containers, Traefik or its configuration.
set -euo pipefail

TARGET="${1:?usage: deploy_vps.sh user@host domain [ssh_key]}"
DOMAIN="${2:?usage: deploy_vps.sh user@host domain [ssh_key]}"
KEY="${3:-}"
REMOTE_DIR=/opt/aml18

cd "$(dirname "$0")/.."
SSH=(ssh -o BatchMode=yes ${KEY:+-i "$KEY" -o IdentitiesOnly=yes})

echo "==> uploading sources (git HEAD: $(git rev-parse --short HEAD))"
git archive HEAD compliance-service docker-compose.vps.yml .env.vps.example \
  | "${SSH[@]}" "$TARGET" "mkdir -p $REMOTE_DIR && tar -x -C $REMOTE_DIR"

echo "==> configuring environment"
SCP=(scp -o BatchMode=yes ${KEY:+-i "$KEY" -o IdentitiesOnly=yes})
KEYFILE="$(mktemp)"
trap 'rm -f "$KEYFILE"' EXIT
chmod 600 "$KEYFILE"
if [ -f .env ]; then
  sed -n 's/^ANTHROPIC_API_KEY=//p' .env | head -1 | tr -d '\r\n' > "$KEYFILE"
fi
# The key travels as a file (mode 600) and is deleted on the server right after use; never on a command line.
"${SCP[@]}" -q "$KEYFILE" "$TARGET:$REMOTE_DIR/.anthropic_key.tmp"
"${SSH[@]}" "$TARGET" bash -s -- "$DOMAIN" "$REMOTE_DIR" <<'REMOTE'
set -euo pipefail
DOMAIN="$1"; DIR="$2"
cd "$DIR"
chmod 600 .anthropic_key.tmp
API_KEY="$(cat .anthropic_key.tmp)"
rm -f .anthropic_key.tmp
if [ ! -f .env.vps ]; then
  cp .env.vps.example .env.vps
  sed -i "s|^AML_DOMAIN=.*|AML_DOMAIN=$DOMAIN|" .env.vps
  sed -i "s|^POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=$(openssl rand -hex 24)|" .env.vps
  sed -i "s|^SECRET_KEY=.*|SECRET_KEY=$(openssl rand -hex 32)|" .env.vps
  chmod 600 .env.vps
  echo "created .env.vps"
else
  sed -i "s|^AML_DOMAIN=.*|AML_DOMAIN=$DOMAIN|" .env.vps
  echo ".env.vps exists, kept secrets (domain updated)"
fi
if [ -n "$API_KEY" ] && ! grep -q '^ANTHROPIC_API_KEY=.\+' .env.vps; then
  sed -i "s|^ANTHROPIC_API_KEY=.*|ANTHROPIC_API_KEY=$API_KEY|" .env.vps
  echo "ANTHROPIC_API_KEY installed"
fi
REMOTE

echo "==> building and starting (low priority)"
"${SSH[@]}" "$TARGET" "cd $REMOTE_DIR && nice -n 15 docker compose -f docker-compose.vps.yml --env-file .env.vps up -d --build"

echo "==> waiting for the app to become healthy"
for _ in $(seq 1 40); do
  status="$("${SSH[@]}" "$TARGET" "docker inspect -f '{{.State.Health.Status}}' aml18-app-1 2>/dev/null" || true)"
  [ "$status" = "healthy" ] && break
  sleep 6
done
echo "app health: ${status:-unknown}"
"${SSH[@]}" "$TARGET" "cd $REMOTE_DIR && docker compose -f docker-compose.vps.yml --env-file .env.vps ps"

cat <<EOF

Next steps
  1. DNS (Cloudflare): A record  ${DOMAIN}  ->  server IP   (DNS-only or proxied, SSL mode Full)
  2. Create your operator account (prompts for nothing sensitive on the command line):
       ssh $TARGET 'cd $REMOTE_DIR && read -rsp "operator password: " P && echo && \\
         AML18_OPERATOR_PASSWORD="\$P" docker compose -f docker-compose.vps.yml --env-file .env.vps \\
         exec -T -e AML18_OPERATOR_PASSWORD app flask platform-create-operator --email you@example.com'
     then open https://${DOMAIN}/admin/login
  3. First sanctions refresh already runs in the background (sanctions-cron); watch it:
       ssh $TARGET 'docker logs -f aml18-sanctions-cron-1'
EOF
