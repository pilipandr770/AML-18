# Local patches to `trisacrypto/envoy`

This project builds on [TRISA Envoy](https://github.com/trisacrypto/envoy) (MIT
licensed), vendored directly into `envoy/` (see `envoy/VERSIONS.md` for the
pinned upstream commit) the same way `vendor/ageverify/` is vendored — as
regular committed files, not a fork or submodule.

Both patches below are already applied in the committed `envoy/` tree — no
setup step is needed. They're kept here as `.patch` files for provenance and
because both are real upstream bugs worth reporting as GitHub issues against
`trisacrypto/envoy`. If `envoy/` is ever re-vendored from a fresh upstream
clone, re-apply them with:

```
cd envoy
git apply ../patches/0001-fsi-set-routing-protocol.patch
git apply ../patches/0002-fix-webhook-default-response-fallthrough.patch
```

## What each patch fixes

**`0001-fsi-set-routing-protocol.patch`** — `cmd/fsi/account.go`

The bundled `fsi` dev/test CLI's `makePrepare()` builds an `api.Routing{}`
without setting the (now required) `Protocol` field, causing
`[422] invalid field routing.protocol: unknown protocol` whenever you run
`go run ./cmd/fsi tests:run` following envoy's own README instructions.
One-line fix: set `Protocol: "trisa"`.

**`0002-fix-webhook-default-response-fallthrough.patch`** — `pkg/trisa/transfer.go`

`WebhookResponse()` calls `s.DefaultResponse(...)` when a webhook reply's
`transfer_action` is the `"default"` sentinel, but was missing a `return`
after it — execution fell through into a switch statement that always hit
`default: return internalError`, logged as
`"no error or payload on webhook callback response"`. This breaks *every*
webhook integration that ever needs Envoy's default/passthrough handling
(both a literal HTTP 204 reply and an explicit `"transfer_action":"default"`
JSON reply hit it). Fix: `return s.DefaultResponse(payload, p)` directly.

See `compliance-service/` for how these interact with the actual webhook
integration, and the project's Claude memory notes for the full debugging
trail that led to finding both of these.
