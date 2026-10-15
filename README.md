# AML+18

[![CI](https://github.com/pilipandr770/AML-18/actions/workflows/ci.yml/badge.svg)](https://github.com/pilipandr770/AML-18/actions/workflows/ci.yml)

**An AI compliance officer for crypto and fintech.** It screens every inbound transfer, explains every decision, and
acts only within the policy you set. Open source (MIT), self-hostable, with an optional hosted tier.

> Deutsche Fassung: [README.de.md](README.de.md)

AML+18 is built on a set of independent compliance modules (sanctions screening, EU Travel Rule over TRISA,
wallet-ownership verification, age verification). The **agent** (`compliance-service/app/agent/`) automates the
routine analyst work on top of them. Its design rule: the model never decides what is *allowed* — deterministic
checks set a floor it cannot lower, and a deterministic policy engine sits between the model and every action.

## Try the agent in one command

```bash
python scripts/demo/run_demo.py            # real model if ANTHROPIC_API_KEY / ANTHROPIC_MODEL are in .env, else offline stand-in
python scripts/demo/run_demo.py --serve    # afterwards: owner console at http://127.0.0.1:8310/owner/login
```

Five cases run through the real pipeline in **MONITOR** (recommend only) and then **OPERATE** mode (acts, within policy):
clean transfer (auto-clear), sanctions match (always a human), ambiguous match (escalated with explanation),
over the limit (needs approval), prompt injection in the memo (treated as data, logged, no action). Uses a throwaway
SQLite database, a mock ledger and a small bundled sanctions fixture — no real funds, no mainnet.

Full description, threat model and configuration: **[docs/AGENT.md](docs/AGENT.md)**.

## Key guarantees (enforced in code, covered by tests)

- Sanctions and fuzzy matches are never processed automatically.
- The model can only raise caution; if it is down, slow or rate-limited the case goes to a human, never to auto-clear.
- Counterparty names and memos are untrusted data; a malicious memo cannot trigger an action.
- MONITOR by default. OPERATE needs the owner's recorded consent plus a fresh TOTP code; a kill switch returns to MONITOR instantly.
- The agent cannot change its own policy or mode. It holds no keys and moves no funds.
- Every step is written to an append-only, hash-chained journal; tampering is detected and shown in the console.

## Modules

| Module | Purpose | Entry point |
|---|---|---|
| `agent/` | AI compliance officer, policy engine, journal, owner console | `POST /agent/transfers`, `/owner/` (off unless `AGENT_ENABLED=true`) |
| `screening/` + `webhook/` | Sanctions screening (OFAC SDN, EU FSF) and Travel Rule webhook for the vendored TRISA Envoy node | TRISA protocol, `POST /screening/check-name` |
| `wallet_ownership/` | Proof of control over self-hosted wallets (EBA / BaFin § 15a GwG) | `/wallet-ownership/*` (API key) |
| `ageverify/` | Privacy-preserving 18+ proof, EU OID4VP | `/age-verify/*` (API key) |
| `developer_portal/` | Self-service registration, API keys | `/developer/` |
| `billing/` | Optional hosted-tier metering and Stripe (`BILLING_ENABLED=true`) | `/billing/*` |
| `review_ui/` | Travel Rule decision review console | `/review/` |

Travel Rule, wallet ownership and age verification stay architecturally separate (own tables, no cross-links): they
are different regulatory regimes and must not be mixed in one record. The agent has its own tables, keyed by project.

## Quick start (full stack)

Requirements: Docker + Compose, Go (for Envoy's `cmd/fsi`), Git Bash / `openssl` on Windows.

```bash
powershell -File scripts/bootstrap.ps1     # Windows
bash scripts/bootstrap.sh                  # Linux/macOS
```

The idempotent script creates `.env`, generates sandbox TLS certs, builds and starts the stack (TRISA sandbox, Envoy,
compliance service, Postgres, EU age-verification verifier, sanctions cron), registers the nodes and wires the webhook key.
Then: home `http://localhost:8300/`, developer portal `/developer/`, review console `/review/`.

To enable the agent in the stack set in `.env`: `AGENT_ENABLED=true`, `ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL`, a strong
`SECRET_KEY`; then register a project at `/developer/signup`, create the owner at `/owner/register`.
The UI is English by default; set `UI_LOCALE=de` for German.

## Keeping sanctions lists current

The `sanctions-cron` service refreshes OFAC SDN and the EU consolidated list on an interval
(`SANCTIONS_CRON_INTERVAL_SECONDS`, default daily), each source independently. Both consoles show the age of each active list,
in red once older than `SANCTIONS_STALENESS_WARNING_DAYS` (default 7). The agent additionally refuses to clear a transfer if a
list required by the project's jurisdiction profile (US: OFAC SDN; EU: EU FSF + OFAC SDN) is missing or stale.

## Hosted tier (open core)

The same code runs self-hosted (free, no limits) or as a hosted tier (`BILLING_ENABLED=true`): wallet-ownership and
age-verification calls are metered per project, with a free monthly band and a Stripe subscription above it
(`docker-compose.hosted.yml` adds a Caddy HTTPS proxy; the base compose file is untouched). Travel Rule / TRISA stays self-host-only.
Tenant isolation is enforced per API key (`tests/test_tenant_isolation.py`).

## Status

- Sanctions screening, Travel Rule over real TRISA, wallet ownership (signed message live-verified; test transfer unit-tested),
  age verification (EU OID4VP verified end-to-end), developer portal, Postgres + Alembic migrations, CI, multi-tenancy + billing: done.
- Agent: MONITOR/OPERATE, policy engine, journal, owner console with 2FA, signed operation webhooks, jurisdiction profiles,
  daily digest, English/German UI, one-command demo: done. **Testnet / mock ledger only.**
- Open: address-level (wallet) sanctions screening, mainnet support (intentionally absent), authentication on the Travel Rule review console,
  automatic link between wallet-ownership checks and the Travel Rule decision path, and legal review of the jurisdiction texts
  (all marked REQUIRES COUNSEL REVIEW).

This project is tooling, not legal advice, and does not by itself satisfy any regulatory obligation. Licences and permits for
your business model are out of scope. Legal research notes: [ANFORDERUNGEN.md](ANFORDERUNGEN.md).

Tests: `cd compliance-service && python -m pytest`.

## License

MIT for this project's own code (see `LICENSE`). Vendored third-party code keeps its own upstream licence:
`envoy/` (MIT, trisacrypto/envoy) and `vendor/ageverify/` (mostly Apache-2.0; the technical specification is CC BY 4.0).
