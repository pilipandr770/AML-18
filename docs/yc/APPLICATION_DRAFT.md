# Y Combinator application — DRAFT (needs your review; nothing here has been submitted)

Target: YC Winter 2027. The deadline reported to me was **2 November 2026, 20:00 PT — please verify on
ycombinator.com/apply**. Internal target: submit by 1 November.

Items marked **[FOUNDER INPUT]** are facts only you know. Do not submit with any of them guessed.

## One-line description (<= 50 chars)

AI compliance officer for crypto and fintech

## What is your company going to make? (short)

AML+18 is an open-source AI compliance officer for crypto and fintech companies. It screens every inbound
transfer against sanctions lists, checks the funds on-chain, explains every decision, and takes action in the
customer's systems only within a policy the customer sets. By default it only recommends; customers opt in to
letting it act, with explicit consent, two-factor authentication and an instant kill switch.

## What problem are you solving / why now?

Small crypto and fintech teams must check every counterparty and transfer, decide, and document why — usually by
hand or with per-check vendors that return a score with no reasoning and no trustworthy audit trail. LLM agents can
do the routine analyst work, but compliance teams cannot let a model take actions: a prompt injection in a payment
memo, or an outage, must never turn into a released transfer. We built the agent around that constraint:
deterministic sanctions and funds checks set a floor the model cannot lower, a deterministic policy engine sits between
the model and every action, sanctions hits are always decided by a human, and every step lands in a hash-chained journal.

## What is new / how is it different?

- Policy engine in plain code, not prompt instructions: injection resistance does not depend on the model behaving.
- The model can only raise caution; model failure means human review, never auto-clear.
- Tamper-evident journal the owner can verify in the UI.
- MONITOR by default; OPERATE needs recorded consent + TOTP; one-click kill switch.
- Open source and self-hostable (important for regulated customers), with an optional hosted tier.

## What exists today (honest status)

- Working product: sanctions screening (OFAC SDN, EU consolidated list parsers; verified against the live OFAC list),
  Travel Rule webhook (TRISA/Envoy), wallet-ownership verification, age verification, developer portal with API keys,
  multi-tenant isolation and Stripe billing code for a hosted tier, CI.
- New in this application period: the agent, policy engine, hash-chained journal, owner console with 2FA,
  signed operation webhooks, jurisdiction profiles (US/EU), daily digest, one-command demo with five scenarios
  (clean, sanctions match, ambiguous match, over limit, prompt injection) in both modes. ~195 automated tests.
- Limits: testnet and mock ledger only; no mainnet; no customers yet **[FOUNDER INPUT: confirm — do not claim users, revenue or pilots that do not exist]**.

## Who is on the team / why you? **[FOUNDER INPUT]**

Frankfurt-based full-stack engineer and IT consultant; built and maintains the codebase. Fill in: background,
prior shipped products, links, domain experience in compliance, why this problem.

## Who are the customers? How will you reach them?

Initial target: US-facing fintech and crypto companies that must run sanctions/AML checks on incoming transfers
and cannot afford a compliance team (responding to YC's "AI-native compliance infrastructure" request).
Plan: open-source distribution, a hosted tier with a free usage band, direct outreach to small CASP/fintech
operators, integration guides. **[FOUNDER INPUT: any conversations, waitlist, LOIs — only if real.]**

## Business model

Open core. Free self-hosted. Paid hosted tier, usage-based after a free band (billing already implemented with Stripe
test mode). Later: premium policy packs, managed lists, support SLAs.

## Competition

Per-check KYC/AML vendors (screening scores without agentic workflow or reasoning), general workflow automation tools
(no compliance-grade guarantees), and in-house scripts. Our wedge: an agent that is safe to deploy because its limits
are enforced in code and auditable.

## Risks we are explicit about

Regulatory: the system is configuration + tooling, not legal advice; jurisdiction texts are marked
REQUIRES COUNSEL REVIEW and reporting duties are not encoded. Technical: model errors (mitigated by the floor +
policy engine + human escalation), sanctions-list data quality, address-level screening not yet implemented.

## Logistics note for the interview **[FOUNDER INPUT — confirm wording]**

The founder is based in Frankfurt, Germany, and intends to attend the pitch in person. If needed, a US-based family
member (US citizen) can join as a pitch partner in the United States. (Do not describe this person as a cofounder unless that is true.)

## Founder video (1 minute) — outline

Who you are (10 s) → the problem (10 s) → live demo clip from `docs/demo/SCREEN_RECORDING.md` (30 s) → what you will do
in the next 3 months (10 s).
