# EU AV Blueprint Vendor Sources

This file pins the upstream source set for local vendoring.

## Core verifier path (priority)

1. Basic Verifier UI:
   - https://github.com/eu-digital-identity-wallet/av-web-verifier-ui
2. Verifier Backend:
   - https://github.com/eu-digital-identity-wallet/av-srv-web-verifier-endpoint-23220-4-kt
3. Technical specification:
   - https://github.com/eu-digital-identity-wallet/av-doc-technical-specification

## Ecosystem references (secondary)

1. Android wallet app:
   - https://github.com/eu-digital-identity-wallet/av-app-android-wallet-ui
2. iOS wallet app:
   - https://github.com/eu-digital-identity-wallet/av-app-ios-wallet-ui
3. Issuer service:
   - https://github.com/eu-digital-identity-wallet/av-srv-web-issuing-avw-py
4. Cinema showcase frontend:
   - https://github.com/eu-digital-identity-wallet/av-verifier-frontend-cinema

## Local directory layout recommendation

- vendor/ageverify/av-web-verifier-ui/
- vendor/ageverify/av-srv-web-verifier-endpoint-23220-4-kt/
- vendor/ageverify/av-doc-technical-specification/

## Integration boundary

`compliance-service` remains the policy decision point and stores only
privacy-preserving outputs. Protocol-specific complexity remains in the
vendored verifier stack.