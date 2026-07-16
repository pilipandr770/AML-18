# Local patches to `trisacrypto/envoy`

This project builds on [TRISA Envoy](https://github.com/trisacrypto/envoy) (MIT
licensed), vendored directly into `envoy/` (see `envoy/VERSIONS.md` for the
pinned upstream commit) the same way `vendor/ageverify/` is vendored — as
regular committed files, not a fork or submodule.

All patches below are already applied in the committed `envoy/` tree — no
setup step is needed. They're kept here as `.patch` files for provenance.
0001 and 0002 are real upstream bugs worth reporting as GitHub issues against
`trisacrypto/envoy`; 0003 and 0004 are local-sandbox customizations, not
upstream bugs. If `envoy/` is ever re-vendored from a fresh upstream clone,
re-apply the ones still relevant with:

```
cd envoy
git apply ../patches/0001-fsi-set-routing-protocol.patch
git apply ../patches/0002-fix-webhook-default-response-fallthrough.patch
git apply ../patches/0003-generate-sh-openssl-compat.patch
git apply ../patches/0004-distinctive-local-vasp-names.patch
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

**`0003-generate-sh-openssl-compat.patch`** — `.secret/generate.sh`

`-copy_extensions copyall` (used when signing the local sandbox's test
certs) requires OpenSSL 3.0+; Git for Windows bundles OpenSSL 1.1.1, which
doesn't have it, silently dropping the SAN (subjectAltName) from the signed
certs and breaking TLS hostname verification between the local nodes.
Replaced with `-extfile` passing an explicit SAN, which produces an
identical result on both 1.1.1 and 3.0+.

**`0004-distinctive-local-vasp-names.patch`** — `cmd/fsi/fixtures/localhost/*.pb.json`

The stock fixture data registers both local sandbox nodes under generic
names ("Localhost Development", "Localhost Counterparty"). Renamed to
"Zephyrion Sandbox Node" / "Quillmark Custody Node": the originals happen
to fuzzy-match unrelated real OFAC-sanctioned entities purely because they
contain common English words ("Development"), which made every local demo
transfer come back `review` regardless of the actual originator/beneficiary
identity — confusing for anyone trying to see a clean `accepted` decision.
Verified the replacement names score well below the review threshold
against the full ingested sanctions list (see
`examples/travel-rule-demo/README.md`).

See `compliance-service/` for how these interact with the actual webhook
integration, and the project's Claude memory notes for the full debugging
trail that led to finding these.
