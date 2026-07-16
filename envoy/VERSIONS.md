# Vendored Envoy Source

Pinned on 2026-07-16.

- envoy
  - repo: https://github.com/trisacrypto/envoy
  - commit: b09186b1fa4b4af7175591e1fcba9d0e40f9b337
  - date: 2026-06-16

Two local patches are applied directly in this vendored copy (not kept as
a separate clone-then-apply step) -- see `patches/README.md` for what each
one fixes and why. Working tree state matches `git apply` of both patches
on top of the pinned commit above.
