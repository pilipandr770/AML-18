# AML+18 AI compliance agent

An AI compliance officer for crypto and fintech. It screens every inbound transfer,
explains every decision, and acts only within the policy the owner sets.
It sits on top of the existing AML+18 modules and is **off by default** (`AGENT_ENABLED=false`);
nothing about a self-hosted deployment changes unless you turn it on.

## What it does

For each inbound transfer (`POST /agent/transfers`, or a deposit seen by the testnet monitor):

1. **Deterministic checks run first** and set a floor the model can never go below:
   sanctions screening of the counterparty (existing matcher, stricter for the agent: any candidate at or
   above the review threshold is a hit), sanctions-list coverage/freshness for the project's jurisdiction
   profile, and an on-chain check that the transaction exists, has enough confirmations, and matches
   amount and deposit address.
2. **The model reviews** with a small whitelisted toolset and records a classification
   (`clear`, `needs_review`, `recommend_block`) plus an explanation.
3. **The policy engine decides what may happen** (plain code, no model).
4. Everything is written to a **hash-chained, append-only journal**; the owner sees it in the console.

Tools (thin wrappers over existing services; no DB, key or filesystem access of their own):
`screen_transfer`, `get_sanctions_freshness`, `check_wallet_ownership`, `verify_incoming_funds`,
`list_pending_reviews`, `record_decision`, `execute_operation`, `write_report`, `notify_owner`.

## Modes (per client)

| | MONITOR (default) | OPERATE |
|---|---|---|
| Screens, classifies, explains, reports | yes | yes |
| Changes anything in the client's systems | **never** | only signed instructions for operations the owner consented to, inside the policy |
| Enabled by | default | owner, with a fresh TOTP code and an explicit consent record (who, when, which operations) |

An *operation* is a signed webhook to the client's system (`release`, `hold`, `reject`, confirm/reject
wallet ownership, close a simple review case). The agent never holds keys and never moves funds.
A **kill switch** returns to MONITOR instantly and revokes consent; clearing it needs a TOTP code and does
not re-enable OPERATE.

## Policy engine (deterministic)

Policy JSON (validated by Pydantic, frozen, unknown fields rejected): `enabled_operations`,
`max_amount_per_operation`, `daily_cap`, `allowed_assets`, `allowed_chains`, `blocked_jurisdictions`,
`require_human_above`, `new_counterparty_rule` (`allow` | `require_human` | `block`). An empty policy denies everything.

Hard invariants (not configurable):

- Kill switch or MONITOR mode: record a recommendation only.
- A sanctions match, or a fuzzy match above the review threshold, is **never** handled automatically.
- The model can only **raise** caution. Anything other than an explicit `clear` goes to a human, and a
  `clear` cannot override a deterministic `review`/`rejected`.
- The agent cannot change its own policy or mode: no tool or route reachable by it does so. Only the
  authenticated owner can.
- If the model is unavailable, times out, is rate-limited or returns nothing usable, the case becomes
  `needs_review`, never auto-clear.

## Threat model highlights

- **Prompt injection.** Counterparty name and memo are untrusted external text: always passed as quoted
  `{"untrusted_text": ...}` data, length-limited and stripped of control characters. Protection does not rely
  on the prompt: even a model that obeys a malicious memo cannot execute anything, because the policy engine and
  deterministic floor sit between the model and every action. Attempts are visible in the journal.
- **Tampering.** Each journal entry hashes its content plus the previous entry's hash; the ORM refuses
  UPDATE/DELETE on journal rows; `verify_chain()` flags any edit, deletion or re-hash, and the console shows the result.
- **Owner access.** Password + TOTP, lockout after repeated failures, CSRF tokens, no session secret = no login.
- **Secrets** come from the environment only. Chain access is read-only: a deterministic mock ledger or an EVM
  **testnet** RPC. There is no mainnet configuration, no signing and no key storage anywhere in the agent.

## Jurisdiction profiles

`DeveloperProject.jurisdiction` is `US` or `EU` (default `EU`). It decides which sanctions sources must be loaded
and fresh for a clear to be trustworthy (US: OFAC SDN; EU: EU consolidated list + OFAC SDN) and which notes are
shown to the owner. All legal texts are configuration (`app/agent/jurisdiction.py`) marked **REQUIRES COUNSEL REVIEW**;
reporting duties and thresholds are deliberately not encoded.

## Running it

```bash
# one command, from a clean checkout (uses a throwaway SQLite db, mock ledger, bundled fixture sanctions list)
python scripts/demo/run_demo.py                 # real model if ANTHROPIC_API_KEY/ANTHROPIC_MODEL are in .env
python scripts/demo/run_demo.py --offline       # deterministic stand-in, no network
python scripts/demo/run_demo.py --serve         # then open the owner console on http://127.0.0.1:8310/owner/login
```

The demo runs five cases in MONITOR and then OPERATE: clean transfer (auto-clear), sanctions match (escalated, never
automatic), ambiguous match (escalated with explanation), over the limit (needs approval), injection in the memo
(treated as data, logged, no action).

In the full stack set in `.env`: `AGENT_ENABLED=true`, `ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL`, a strong `SECRET_KEY`,
optionally `AGENT_CHAIN_ADAPTER=evm` + `AGENT_EVM_RPC_URL` (Sepolia), `AGENT_EXECUTOR=webhook`, `SMTP_*` for the daily digest.
Then register a project (`/developer/signup`), create the owner at `/owner/register`, and send transfers to `POST /agent/transfers`.

## Operation webhook (OPERATE mode)

`POST <project webhook_url>` with JSON `{operation, case_id, external_ref, tx_hash, amount, asset, chain}` and headers
`X-AML18-Signature: t=<unix>,v1=<hex HMAC-SHA256 of "<t>.<body>" with the per-project secret>` and
`Idempotency-Key: <case_id>:<operation>`. The secret is shown once to the owner when OPERATE is first enabled.

## Known limits

Early software. Testnet and mock ledger only. Amounts compared with a 1e-9 tolerance (SQLite float noise). The
deposit monitor opens cases without KYC data, so they go to a human until identity data is supplied. Address-level
(crypto wallet) screening against sanctions entries is not implemented. Not legal advice.
