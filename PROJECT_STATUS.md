# Project Status

Date: 2026-07-15
Repository: AML-18

## Summary

The project is in an active integration stage for age verification (AV) based on EU OID4VP/OID4VCI flows.
Core local infrastructure is running, and end-to-end flow reaches verifier session creation and polling.

A real, fresh AV credential has been successfully issued from upstream issuer endpoints.
The current blocker is at verifier direct-post payload format: verifier expects a wallet DeviceResponse, while the issued artifact is a raw mdoc credential.

## What Is Implemented

- Local AV stack orchestration through docker-compose for compliance service + verifier.
- Compliance API endpoints for AV checks and AV session lifecycle.
- Session-start and polling flow integrated in local compliance service.
- Request-value parsing and response-uri/state extraction tested in local runs.
- Live issuer integration explored and exercised to obtain non-expired AV credential.

## Verified Results

- Local compliance endpoint responds and processes AV-related requests.
- Session creation works and returns session identifiers + request payload.
- Polling remains stable and returns pending state while verification callback is not accepted.
- Issuer flow succeeds:
  - pre-authorized code + tx_code obtained
  - access token obtained
  - AV mdoc credential issued (fresh validity window)

## Current Blocker

Verifier direct-post endpoint requires vp_token that can be decoded as an MSO mdoc DeviceResponse.
Current submitted payload contains a raw issued mdoc credential and is rejected with:

- InvalidVpToken
- DeviceResponse cannot be decoded

Additionally, generated response_uri may point to https://localhost/... (port 443), which may be unreachable in local setup depending on routing.

## Risks

- E2E success currently depends on obtaining/generating a valid wallet DeviceResponse, not only issuing credential.
- Environment TLS/trust constraints require careful handling for upstream endpoints.
- Manual/CLI payload transport can introduce formatting issues for large structured fields.

## Recommended Next Steps

1. Add or integrate a wallet simulator/tool capable of producing valid DeviceResponse from issued credential context.
2. Align verifier public URL / response_uri with actually reachable local endpoint (host/port/protocol).
3. Re-run full session flow and verify terminal state becomes verified=true.
4. Add automated integration test covering successful local positive AV session path.
5. Keep temporary artifacts (tmp/vendor) out of versioned source unless explicitly needed.

## Operational Notes

- Local compliance service port used in this setup: 8300.
- Local verifier service port used in this setup: 8080.
- Upstream AV issuer calls may require curl -k in this environment due certificate trust chain issues.

## Status

Overall status: in progress.

Backend integration is significantly advanced, and the remaining gap is narrowed to wallet DeviceResponse generation/transport for final verifier acceptance.
