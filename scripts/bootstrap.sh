#!/usr/bin/env bash
# Linux/macOS equivalent of scripts/bootstrap.ps1 -- see that file's inline
# comments for the reasoning behind each step; kept in lockstep with it.
set -euo pipefail

cd "$(dirname "$0")/.."

RESET=0
if [ "${1:-}" = "--reset" ]; then
    RESET=1
fi

step() {
    echo ""
    echo -e "\033[1;36m==> $1\033[0m"
}

# 1. Root .env: create from example, and fill in GIT_REVISION.
step ".env"
if [ ! -f .env ]; then
    cp .env.example .env
    echo "created .env from .env.example"
fi

git_revision="$(git rev-parse --short HEAD)"
if grep -q "^GIT_REVISION=" .env; then
    sed -i.bak "s/^GIT_REVISION=.*/GIT_REVISION=${git_revision}/" .env
    rm -f .env.bak
else
    echo "GIT_REVISION=${git_revision}" >> .env
fi

# 2. Envoy sandbox TLS certs. Generated once, then bind-mounted/reused --
# only regenerate if missing or --reset was passed. No MSYS_NO_PATHCONV
# dance needed here (that's a Git-for-Windows-only quirk); real Linux/macOS
# bash + openssl run envoy/.secret/generate.sh as-is.
step "TLS sandbox certs"
secrets_exist=1
for f in server.pem.gz counterparty.pem.gz localhost.pem.gz; do
    [ -f "envoy/.secret/$f" ] || secrets_exist=0
done
if [ "$secrets_exist" -eq 0 ] || [ "$RESET" -eq 1 ]; then
    echo "generating..."
    (cd envoy/.secret && bash generate.sh)
else
    echo "already present, skipping (pass --reset to regenerate)"
fi

# 3. Build and start the whole stack.
step "docker compose build"
docker compose build

step "docker compose up -d"
docker compose up -d

echo "waiting for services to settle..."
sleep 10

# 4. Register both TRISA nodes with the local sandbox directory (gds.local).
# go run ./cmd/fsi gds:init opens the GDS leveldb store directly on disk, so
# gds.local must be stopped first to avoid two processes touching the same
# bind-mounted file at once.
step "TRISA directory (gds:init)"
if [ "$RESET" -eq 1 ] || [ ! -d envoy/tmp/gds/db ]; then
    docker compose stop gds.local
    (
        cd envoy
        if [ "$RESET" -eq 1 ]; then
            go run ./cmd/fsi gds:init --reset
        else
            go run ./cmd/fsi gds:init
        fi
    )
    docker compose start gds.local
    sleep 3
    # envoy.local/counterparty.local cache the directory (6h sync interval)
    # -- force an immediate re-sync so the demo scripts see the new records
    # without waiting.
    docker compose restart envoy.local counterparty.local
    sleep 8
else
    echo "already initialized, skipping (pass --reset to reinitialize)"
fi

# 5. API keys for envoy.local / counterparty.local -- used by cmd/fsi and by
# examples/travel-rule-demo/send_transfer.py. Written straight to a
# gitignored file, never printed to the console.
step "API keys"
mkdir -p envoy/tmp/creds

envoy_key_path="envoy/tmp/creds/envoy_local_apikey.txt"
if [ ! -f "$envoy_key_path" ]; then
    docker compose exec -T envoy.local envoy createapikey all > "$envoy_key_path"
    echo "created $envoy_key_path"
else
    echo "$envoy_key_path already exists, skipping"
fi

counterparty_key_path="envoy/tmp/creds/counterparty_local_apikey.txt"
if [ ! -f "$counterparty_key_path" ]; then
    docker compose exec -T counterparty.local envoy createapikey all > "$counterparty_key_path"
    echo "created $counterparty_key_path"
else
    echo "$counterparty_key_path already exists, skipping"
fi

# 6. Webhook HMAC key: envoy.local needs one to sign its webhook calls, and
# compliance.local needs the same one to verify them. Chicken-and-egg --
# doesn't exist until envoy.local has already been running once.
step "Webhook HMAC key"
if ! grep -qE "^WEBHOOK_AUTH_KEY_ID=\S" .env; then
    hmac_output="$(docker compose exec -T envoy.local envoy hmackey)"
    key_id="$(echo "$hmac_output" | sed -n 's/^Key ID: //p' | tr -d '\r')"
    key_secret="$(echo "$hmac_output" | sed -n 's/^Key: //p' | tr -d '\r')"

    sed -i.bak "s/^WEBHOOK_AUTH_KEY_ID=.*/WEBHOOK_AUTH_KEY_ID=${key_id}/" .env
    sed -i.bak "s/^WEBHOOK_AUTH_KEY_SECRET=.*/WEBHOOK_AUTH_KEY_SECRET=${key_secret}/" .env
    rm -f .env.bak

    echo "generated webhook HMAC key, restarting envoy.local + compliance.local to pick it up"
    docker compose up -d envoy.local compliance.local
    sleep 5
else
    echo "already configured in .env, skipping"
fi

step "Done"
echo "Compliance officer UI: http://localhost:8300/review/"
echo "Demo: python examples/travel-rule-demo/send_transfer.py --clean"
echo "      python examples/travel-rule-demo/send_transfer.py --flagged"
