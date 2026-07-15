# Age Verification Upstream Integration Plan

Goal: integrate the regulator-aligned open-source age verification flow
as the primary adapter, returning only over-age outcome while keeping raw
identity data outside this service.

## Product and privacy contract

1. This service consumes only an opaque proof token from the external age
   verification system and returns a boolean decision (`verified=true/false`)
   for a configured threshold (`AGEVERIFY_MIN_AGE`, default 18).
2. Raw identity payloads, document scans, and full claims are never stored.
3. Persistence is limited to:
   - opaque `subject_reference`
   - adapter name
   - boolean result
   - method metadata
   - proof token hash
   - timestamps

## Why vendor the upstream project locally

Using long-lived local patches on a moving external target increases merge
risk and slows delivery. For the age-verification integration path, prefer
a fully vendored local snapshot with explicit update windows.

## Recommended repository strategy

1. Keep current repository as the product root.
2. Add upstream age-verification project as a vendored subtree at
   `vendor/ageverify/`.
3. Keep local integration logic in `compliance-service/app/ageverify/`.
4. Never edit vendored code in-place without recording the change in
   `vendor/ageverify/LOCAL_PATCHES.md`.

## Current status (2026-07-15)

1. Source import completed into `vendor/ageverify/`.
2. Pinned versions recorded in `vendor/ageverify/VERSIONS.md`.
3. `eu_oid4vp` adapter now bridges to the official verifier backend using the
   transaction flow `init presentation -> poll wallet response -> validate
   device response -> persist boolean verdict`.
4. Runtime configuration currently uses:
   - `AGEVERIFY_EU_VERIFIER_BASE_URL`
   - `AGEVERIFY_EU_VERIFIER_TIMEOUT_SECONDS`

## Delivery phases

### Phase A - Source import and contract lock

1. Import upstream into `vendor/ageverify/`.
2. Pin an exact upstream revision in a machine-readable file
   (`vendor/ageverify/VERSIONS.md`).
3. Implement `eu_oid4vp` adapter in this service against a narrow internal
   interface (proof in -> over-age decision out).

### Phase B - Local integration

1. Implement verifier-client code for upstream endpoints/protocol.
2. Add timeout/retry/circuit-breaker settings.
3. Add integration tests with deterministic fixtures.
4. Add negative tests for malformed/expired/unsigned proofs.
5. Add local runtime wiring so the vendored verifier backend can be started
   together with `compliance-service` during development.

### Phase C - Operational readiness

1. Add adapter-specific observability (latency, error rate, decision rate).
2. Add runbook for key rotation, outage handling, and fail-safe behavior.
3. Add legal/compliance evidence page documenting data minimization.

## Acceptance criteria for `eu_oid4vp`

1. No raw PII persisted by this service.
2. Cryptographic proof validation is enforced.
3. Result semantics are explicit (`over_age` threshold-based decision).
4. Full test coverage for success and failure paths.
5. Fallback behavior is deterministic and auditable.