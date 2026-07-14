# AML+18

Open-source compliance layer for crypto (USDC) payments on EU-facing
subscription/PPV platforms, combining two regulatory requirements that a
small CASP otherwise has to buy separately from vendors like Sumsub or
Notabene:

1. **EU Travel Rule** (Regulation (EU) 2023/1113 / MiCA, effective
   2026-07-01) — sanctions/AML screening on crypto transfers, with a
   fully open, self-hostable architecture (a real advantage with BaFin,
   which wants to see technical architecture, not vendor attestations).
2. **Age verification (18+)** — for adult-content/PPV platforms, ahead of
   payment, kept architecturally separate from Travel Rule identity data
   (DSA Article 28 and TFR are two distinct regulatory regimes).

Strategy: ship something genuinely useful and simple enough that small CASPs
adopt it organically, before worrying about monetization.

## Components

- **`envoy/`** (not committed here — vendored clone, see below) —
  [TRISA Envoy](https://github.com/trisacrypto/envoy), MIT licensed,
  self-hosted Travel Rule protocol node. Transport-only: no sanctions
  screening built in, but exposes exactly one extension point for it — an
  outbound webhook fired on every incoming Travel Rule message.
- **`compliance-service/`** — the actual value-add: a Flask microservice
  that receives Envoy's webhook, screens IVMS101 identity data against real
  sanctions lists (OFAC SDN, EU Consolidated), and replies with an explicit
  decision (accept/review/reject). Age verification is scoped as an
  interface + isolated schema for now (see the plan below) — no real
  provider integration yet.

## Setup

```
git clone https://github.com/trisacrypto/envoy.git
cd envoy
git apply ../patches/0001-fsi-set-routing-protocol.patch
git apply ../patches/0002-fix-webhook-default-response-fallthrough.patch
cd .secret && ./generate.sh && cd ..   # see patches/README.md if this fails on Windows
export GIT_REVISION=$(git rev-parse --short HEAD)
docker compose build
docker compose up -d
go run ./cmd/fsi gds:init
docker compose exec envoy.local envoy createuser -e admin@envoy.local -r admin
docker compose exec counterparty.local envoy createuser -e admin@counterparty.local -r admin
```

Then, from `compliance-service/`:

```
cp .env.example .env
# fill in WEBHOOK_AUTH_KEY_ID / WEBHOOK_AUTH_KEY_SECRET from:
docker compose exec envoy.local envoy hmackey

docker compose -f ../envoy/docker-compose.yaml -f docker-compose.override.yaml \
    --env-file ./.env up -d --build
```

See `docker-compose.override.yaml` for why the `-f` order and `--env-file`
flag matter (Compose resolves relative paths against the first file's
directory).

## Status

- **Phase 0** (webhook + HMAC auth + IVMS101 parsing): done, verified
  end-to-end against a live two-node Envoy stack.
- **Phase 1** (real sanctions screening): done. OFAC SDN + EU Consolidated
  parsers, phonetic-blocked fuzzy matching (rapidfuzz + jellyfish/NYSIIS,
  MIT — not Beider-Morse/`abydos`, which is GPLv3+), Cyrillic
  transliteration, a conservative accept/review/reject decision engine.
  Verified against the real live OFAC SDN list (19,210 entities) — a
  synthetic transaction naming a real sanctioned person was correctly
  flagged for review.
- **Phase 2** (in progress): compliance-officer review/explainability UI.
- **Later**: UN Consolidated source, age-verification adapters (Zyphe /
  EU Age Verification Solution), production hardening.

Run `python -m pytest` inside `compliance-service/` for the test suite.

## Development notes

Local development happened in a series of Claude Code sessions — the full
debugging trail (Windows-specific gotchas, a couple of real upstream Envoy
bugs found and patched, live-data validation findings) is preserved in
project memory rather than duplicated here. `patches/README.md` documents
the two Envoy patches required to run this locally.
