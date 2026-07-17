# Project Status

Date: 2026-07-16
Repository: AML-18

## Summary

The project unified into a single deployable stack this session: Envoy
(TRISA transport) is now vendored directly into the repo, and one root
`docker-compose.yml` + `scripts/bootstrap.ps1` bring up the whole thing —
the local TRISA sandbox (`gds.local` + `envoy.local` + `counterparty.local`),
`compliance-service` (all three regulatory modules), and the EU
age-verification reference verifier — from a single command.

All three regulatory pillars (Travel Rule sanctions screening,
wallet-ownership verification, age verification) are implemented and each
has been independently verified end-to-end against live/local
infrastructure. The Travel Rule pillar now has a real entry-point demo
(`examples/travel-rule-demo/`) proving that an external project connecting
over the actual TRISA protocol gets screened automatically.

## 2026-07-17 Update: GitHub Actions CI

Added `.github/workflows/ci.yml`, two independent jobs on push-to-main and
every PR: `test` (Python 3.12, `pip install -r requirements-dev.txt`,
`pytest -v` in `compliance-service/`) and `docker-build` (`docker compose
config --quiet` then `docker compose build` for the whole stack --
`envoy.local`, `compliance.local`, `ageverify-verifier` all have real
`build:` blocks and get validated; `gds.local`/`counterparty.local`/
`postgres` reuse prebuilt or already-built images, no separate build
needed). `GIT_REVISION` is set to `${{ github.sha }}` at the job level so
the compose build args resolve to something meaningful instead of an
empty-string warning.

Deliberately scoped to build validation, not a full bootstrap+e2e run in
CI -- spinning up the whole local TRISA sandbox (cert generation, GDS
init, directory sync) in a CI runner is a separate, meaningfully riskier
piece of work flagged as its own follow-up, not bundled into this pass.
Added a CI status badge to the top of README.md.

First CI run failed immediately (10s, before any real build) on `docker
compose config --quiet`: the `secrets:` block references
`envoy/.secret/*.pem.gz`, deliberately gitignored, so a fresh checkout
(exactly what CI is) doesn't have them. Added a "Generate envoy sandbox
certs" step (`bash envoy/.secret/generate.sh`) before config validation.

Testing that fix locally (in an isolated temp copy, not touching the live
working certs) surfaced a real, previously-unexecuted bug in patch 0003
itself: the `-extfile <(printf "...")` process-substitution form signs
without error-looking output on Linux, but on Git for Windows'
bash/openssl combination it fails intermittently (`Can't open /dev/fd/63
for reading`) while still exiting 0 -- the script "succeeds" but the
signed leaf cert silently ends up with no SAN extension at all (verified
by inspecting the decoded cert: wrong Subject entirely, matching the CA
rather than the leaf). This patch had only ever been reasoned about
syntactically, never actually executed top-to-bottom, because every local
test session so far reused already-generated certs from before the patch
existed. Fixed by writing the SAN to a real temp file instead of process
substitution -- confirmed via decoded-cert inspection that the correct
Subject and SAN now come out on Windows too. patches/0003 and its
description in patches/README.md updated to match.

## 2026-07-17 Update: PostgreSQL + real Alembic migrations

Following an external review (SWOT-style read of the repo), addressed the
top flagged risk: SQLite as the implicit production datastore for an
auditable AML service, with no real schema-migration story (`flask
init-db` was just `db.create_all()` on every container start, no
versioning, no ALTER-TABLE path for future schema changes).

- Added a `postgres` service to `docker-compose.yml` (postgres:16-alpine,
  named volume, healthcheck; `compliance.local` now `depends_on:
  condition: service_healthy` on it) -- Postgres is the new default
  `DATABASE_URL` for the docker-compose stack. SQLite remains fully
  supported for local dev outside Docker (just point `DATABASE_URL` at a
  sqlite file) -- nothing in the ORM layer was Postgres/SQLite-specific
  (audited: no raw SQL, no SQLite PRAGMA usage, no dialect-specific column
  types anywhere in the 12 models).
- Set up real Alembic migrations (`compliance-service/migrations/`):
  generated the initial schema migration against a live Postgres
  container (all 12 tables, indexes, and foreign keys came out correct on
  the first autogenerate), removed the `init-db` CLI command entirely
  (nothing referenced it outside its own definition), and changed
  `docker/entrypoint.sh` to run `flask db upgrade` instead.
- Verified a genuinely fresh deployment, not just an idempotent re-run:
  deleted the `aml18_postgres-data` volume, rebuilt `compliance.local`,
  brought the stack up from nothing, and confirmed `flask db upgrade`
  correctly created all 12 tables via migration history alone. Caught a
  real bug in the process: the root `.env` file (not `.env.example`) still
  had the old `DATABASE_URL=sqlite:...` value from before this change, so
  the `${DATABASE_URL:-postgresql+psycopg://...}` default in
  `docker-compose.yml` never kicked in until `.env` itself was updated --
  a reminder that `.env.example` edits don't propagate to an existing
  `.env`.
- Full regression after the switch: 91/91 pytest (still against in-memory
  SQLite, unaffected and intentionally fast), a live developer-portal
  signup + gated wallet-ownership call verified to actually persist in
  Postgres (`SELECT` confirmed the row), the Travel Rule demo
  (`send_transfer.py --clean`) and the AV E2E script both re-run clean
  against the Postgres-backed stack.

## What Is Implemented

- **Unified deployment**: `docker-compose.yml` at repo root (5 services),
  `scripts/bootstrap.ps1` (idempotent: certs, `gds:init`, API keys, webhook
  HMAC key, all skipped if already present; `-Reset` forces a full redo).
  Superseded and removed the old fragmented setup
  (`docker-compose.ageverify.yaml`, `compliance-service/docker-compose.override.yaml`,
  multi-`-f` Compose invocations).
- **Envoy vendored into the repo** (`envoy/`, pinned commit in
  `envoy/VERSIONS.md`), no longer a separately-cloned dependency. Four local
  patches applied directly in the vendored tree, documented in
  `patches/README.md`: two real upstream bugs (routing protocol field,
  webhook default-response fallthrough), one OpenSSL 1.1.1/3.0 compat fix
  for the local sandbox cert script, one local-sandbox VASP-naming fix
  (generic fixture names were fuzzy-matching real OFAC entries, see below).
- **Travel Rule screening** (`compliance-service/app/screening` + `webhook`):
  IVMS101 parsing, OFAC SDN + EU Consolidated fuzzy matching, explainable
  accept/review/reject decisions, compliance-officer review UI.
- **Wallet-Ownership-Verification** (`compliance-service/app/wallet_ownership`):
  signed-challenge-message method (live) and EVM test-transfer method
  (unit-tested only). Endpoints under `/wallet-ownership/`.
- **Age verification** (`compliance-service/app/ageverify`): mock adapter
  plus `eu_oid4vp` against the vendored EU reference issuer/verifier, with
  `scripts/run_ageverify_e2e_device_response.ps1` automating the full flow
  from fresh credential issuance through verified session.
- **Travel Rule entry-point demo** (`examples/travel-rule-demo/`):
  `send_transfer.py --clean` / `--flagged`, sending a real TRISA transfer
  from `counterparty.local` (stand-in for an external project) to
  `envoy.local`, proving the webhook -> screening -> decision path works
  end to end, with both an accepted and a review/rejected outcome
  demonstrated.
- **Developer portal** (`compliance-service/app/developer_portal`): the
  actual product surface for a third-party project connecting to the two
  REST pillars. Self-service signup (`GET/POST /developer/signup`) issues
  an API key shown once (sha256-hashed at rest, never stored plaintext);
  `POST /developer/api-key/rotate` lets a developer who still has their
  current key issue a new one, no login system needed. Closed a real
  security gap in the same change: `wallet_ownership` and `ageverify`
  (all routes except the wallet-app-facing `/launch` and `/qr.svg` pages,
  which can't carry an Authorization header) had **zero authentication**
  before this -- anyone could call them. Now gated on a valid, active
  `DeveloperProject` API key.

## Verified Results (this session, 2026-07-16)

- Vendored Envoy builds and runs cleanly in the unified compose stack.
- Full 5-service stack (`gds.local`, `envoy.local`, `counterparty.local`,
  `compliance.local`, `ageverify-verifier`) starts and reaches healthy state.
- Real TRISA transfer sent from `counterparty.local` to `envoy.local` via
  `cmd/fsi tests:trisa` proved the vendored TRISA protocol stack itself
  works (mTLS handshake, envelope exchange, directory lookup) — but also
  revealed the webhook only fires for the *receiving* side, which shaped
  the demo script's design (must send counterparty -> envoy, not the
  reverse `cmd/fsi` default).
- `send_transfer.py --clean` -> compliance officer UI shows **accepted**.
- `send_transfer.py --flagged` (real name pulled live from the ingested
  19,210-entry OFAC/EU sanctions data) -> officer UI shows **review**, with
  a 100.0 exact-name-match score and full explainability detail rendered.
- Found and fixed a real false-positive: the stock Envoy dev fixtures
  register both local sandbox VASPs under generic names ("Localhost
  Development", "Localhost Counterparty"), which fuzzy-matched unrelated
  real OFAC entries (85.5 score) purely on common English words, making
  every local demo transfer come back "review" regardless of the actual
  originator/beneficiary. Renamed to distinctive, verified-safe names
  ("Zephyrion Sandbox Node" / "Quillmark Custody Node") — documented as
  patch 0004.
- `scripts/bootstrap.ps1` re-run against already-bootstrapped state
  correctly detected and skipped every already-done step (idempotency
  verified in place; a from-absolute-zero fresh-clone run was not tested
  in this session to avoid wiping local dev state).
- Fixed the Envoy web UI login: `TRISA_WEB_AUTH_COOKIE_DOMAIN` was set to
  `envoy.local`/`counterparty.local`, but the ports are published on
  `localhost` -- the browser silently drops a cookie scoped to a domain
  that doesn't match the address bar, so login looked broken even though
  the backend accepted the credentials (verified via a direct `/v1/login`
  call returning 200 with a `Domain=envoy.local` cookie). Changed
  `TRISA_WEB_ORIGIN`/`_AUDIENCE`/`_ISSUER`/`_AUTH_COOKIE_DOMAIN` to
  `localhost` for both nodes in `docker-compose.yml` -- confirmed the
  re-issued cookies now carry `Domain=localhost` and the demo script still
  works after the restart.
- Developer portal signup verified through a real browser (not just curl):
  filled and submitted the `/developer/signup` form via the Browser tool,
  got a one-time API key rendered on the success page, then confirmed that
  exact key works against `GET /wallet-ownership/requirement`. Found and
  fixed a template-name collision bug in the process: `developer_portal`'s
  `base.html` was being shadowed by `review_ui`'s own `base.html` (Flask's
  blueprint template loader resolves same-named templates by blueprint
  registration order) -- renamed to `developer_base.html`.
- Gating broke 21 previously-open-endpoint tests as expected; updated
  `test_wallet_ownership_route.py` and `test_ageverify_route.py` to use a
  new `auth_headers` fixture (registers a throwaway `DeveloperProject` and
  returns a valid Bearer header), added `test_developer_portal_route.py`
  (8 tests: signup, validation, key rotation, revoked-key rejection). Full
  suite: 91/91 passing.
- `scripts/run_ageverify_e2e_device_response.ps1` needed updating too --
  it calls the now-gated `/age-verify/sessions` endpoints. Added a
  `Get-OrCreateApiKey` helper that self-registers a throwaway project via
  `/developer/signup` if no `-ApiKey` is passed, so the script still runs
  with zero manual steps. (Hit and fixed a real PowerShell bug along the
  way: `curl.exe`'s multi-line output comes back as a string array, and
  `-notmatch` against an array checks each line individually rather than
  the whole response -- had to `-join "\`n"` first.)

## Remaining Gaps / Risks

- `scripts/bootstrap.ps1`'s fresh-clone path (no existing `envoy/tmp/`,
  `.secret/`, or credentials) has not been tested end to end — only the
  idempotent re-run path has been verified live.
- Wallet-Ownership-Verification's `test_transfer` method still needs
  validation against a real EVM testnet (funded sender key + RPC endpoint).
- No automated pytest-level integration test covers the full Travel Rule
  webhook path against the real Docker services, or the AV E2E flow — both
  are currently PowerShell/Python scripts only.
- Wallet-ownership verification is not wired into the webhook/screening
  decision path automatically — it's a standalone API an integrator must
  call explicitly for self-hosted-wallet transfers above threshold.
- GlüStV (online gambling) regulatory research is still open
  (`ANFORDERUNGEN.md`, Teil B.3).
- The compliance officer review UI still has no authentication.
- The developer portal has no login/recovery beyond the one-time key
  display; a lost key with no way to re-auth means registering a new
  project. `POST /developer/api-key/rotate` covers "I still have my key
  but want a new one," not "I lost it." Deliberate MVP scoping, not an
  oversight -- revisit if this becomes a real adoption blocker.
- No rate limiting or abuse controls on `/developer/signup` -- anyone can
  mint unlimited projects/keys right now.
- `tmp/ageverify-e2e/` and other working artifacts should stay out of
  version control going forward.

## Recommended Next Steps

1. Test `scripts/bootstrap.ps1`'s fresh-clone path (e.g. in a clean
   checkout or CI) to catch anything that only the idempotent-skip path
   papered over.
2. Add authentication to the compliance officer review UI before any real
   deployment.
3. Wire wallet-ownership verification into the webhook/screening decision
   flow for self-hosted-wallet transfers.
4. Validate the `test_transfer` method against a real EVM testnet.
5. Add a pytest-level integration test for the Travel Rule webhook path
   against live Docker services.
6. Close the GlüStV research gap if the gambling use case stays in scope.
7. Decide whether the developer portal needs real signup abuse controls
   (rate limiting, email verification) before any public deployment.

## Operational Notes

- Local ports: compliance-service 8300, Envoy web UI 8000, Envoy TRISA node
  8100, Envoy TRP 8200, counterparty web UI 9000/9100, local GDS
  4433-4435, EU AV verifier 8080, Postgres 5432.
- Schema changes go through Alembic from now on:
  `flask --app wsgi db migrate -m "..."` to generate, `flask --app wsgi db
  upgrade` to apply (the Docker entrypoint already does this on every
  start). Never hand-edit the schema or reach for `db.create_all()` again
  outside test fixtures.
- Default adapter for `/age-verify/check` in the Docker stack is
  `eu_oid4vp`; pass `"adapter": "mock"` explicitly for the deterministic
  mock path.
- Credentials generated by `scripts/bootstrap.ps1` (Envoy API keys, webhook
  HMAC key) are written to `envoy/tmp/creds/*.txt` (gitignored) and `.env`
  (gitignored) — never printed to any transcript or log by the tooling.

## Status

Overall status: major architectural milestone reached.

All three regulatory pillars are implemented and independently verified.
The project is now a genuinely unified, single-command-deployable stack
with a working, protocol-level entry-point demo for the Travel Rule pillar.
Remaining work is real-world validation (fresh-clone bootstrap, EVM
testnet), the two still-open regulatory/ops items (auth on the review UI,
GlüStV), and closing the loop between wallet-ownership verification and the
webhook decision path.
