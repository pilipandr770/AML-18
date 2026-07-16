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

## Operational Notes

- Local ports: compliance-service 8300, Envoy web UI 8000, Envoy TRISA node
  8100, Envoy TRP 8200, counterparty web UI 9000/9100, local GDS
  4433-4435, EU AV verifier 8080.
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
