# Project Status

Date: 2026-07-15
Repository: AML-18

## Summary

The project is in an active integration stage for age verification (AV) based on EU OID4VP/OID4VCI flows.
The full local end-to-end flow now works: session start -> wallet DeviceResponse submission -> verifier validation -> compliance-service marks the session `verified=true`.

The previous blocker (verifier rejecting a raw issued mdoc because it expects a wallet DeviceResponse) is resolved
via `scripts/run_ageverify_e2e_device_response.ps1`, which wraps the issuer-signed mdoc into a minimal valid
DeviceResponse CBOR structure before submitting it to the verifier's `direct_post` endpoint.

## What Is Implemented

- Local AV stack orchestration through docker-compose (`docker-compose.ageverify.yaml`) for compliance-service + verifier.
- Compliance API endpoints for AV checks (`/age-verify/check`) and AV session lifecycle (`/age-verify/sessions`).
- Session-start and polling flow integrated in local compliance service.
- Request-value parsing and response-uri/state extraction tested in local runs.
- Live issuer integration automated end-to-end: `scripts/run_ageverify_e2e_device_response.ps1` now issues a
  fresh AV credential from scratch (credential offer -> token -> credential) against the live remote reference
  issuer (`https://backend.issuer.dev.ageverification.dev`), builds a DeviceResponse from it, starts a compliance
  session, submits it to the verifier, and polls until verified — no manual step required.

## Verified Results (re-confirmed 2026-07-15, this session)

- Docker stack (`compliance.local` + `ageverify-verifier`) builds and starts cleanly.
- `/age-verify/check` with `adapter: mock` works as expected (smoke test).
- Full E2E script run against the live local stack succeeded end-to-end, issuing a brand-new credential each run:
  - fresh `credentialOfferReq2` -> `oidc/token` -> `credential` calls against the remote reference issuer
  - session created (`status: pending`)
  - DeviceResponse built from the freshly issued mdoc and submitted to verifier `direct_post`
  - polling reached `final_status: verified`, `verified: true`, with a new `verification_id` persisted in
    compliance-service DB on every run.
- The reference issuer's `/credentialOfferReq2` and `/credential` endpoints do not validate the proof JWT
  signature (by design, for testing) — the script exploits this to skip real key-signing and DPoP wallet software.

## Remaining Gaps / Risks

- The automated issuer leg depends on a live, third-party-hosted reference test deployment
  (`backend.issuer.dev.ageverification.dev`) that we do not control; if it goes down or changes its API shape,
  the E2E script breaks. A `-ReuseExistingMdoc` switch was kept as a fallback to replay a previously captured
  credential from `tmp/ageverify-e2e/issued_mdoc.txt`.
- No automated pytest-level integration test covers this full local positive AV session path against the real
  Docker services (only adapter-level tests with mocked `requests` calls exist in `tests/test_ageverify_route.py`).
- `tmp/ageverify-e2e/` contains working artifacts (tokens, credentials) that should stay out of version control.
- TLS/trust constraints for upstream issuer endpoints still require `verify=False`/`curl -k` in this environment.

## Recommended Next Steps

1. Add a pytest-level integration test that drives the same flow against the live Docker services (or document
   why this stays a PowerShell script only).
2. Decide on and implement the Wallet-Ownership-Verification module flagged in `ANFORDERUNGEN.md` (EBA/BaFin
   requirement for self-hosted wallet transfers above EUR 1000).
3. Close the GlüStV research gap noted in `ANFORDERUNGEN.md` (Teil B.3) if the gambling/casino use case is still in scope.
4. Keep temporary artifacts (tmp/, vendor build output) out of versioned source unless explicitly needed.

## Operational Notes

- Local compliance service port used in this setup: 8300.
- Local verifier service port used in this setup: 8080.
- Upstream AV issuer calls may require curl -k in this environment due certificate trust chain issues.
- Default adapter for `/age-verify/check` in the Docker stack is `eu_oid4vp`; pass `"adapter": "mock"` explicitly
  to exercise the deterministic mock path.

## Status

Overall status: in progress, with a major milestone reached.

The core AV backend integration (compliance-service <-> EU verifier, full session lifecycle) is functionally
complete and verified end-to-end locally. Remaining work is largely automation/testing polish plus the two
regulatory gaps identified in `ANFORDERUNGEN.md` (wallet ownership verification, GlüStV).
