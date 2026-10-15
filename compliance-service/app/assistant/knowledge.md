# AML+18 knowledge base (used by the public site assistant)

## What AML+18 is
AML+18 is an open-source (MIT) compliance layer for crypto and fintech companies in the EU and US. It screens
people, wallet addresses and incoming transfers against official sanctions lists, explains every decision, and adds an
AI compliance agent that reviews each inbound transfer. It is early software: a pilot programme is open and
testnet / mock ledger only for on-chain checks (no mainnet yet). It is not legal advice and not a licensed
compliance officer; a human stays responsible for decisions.

## Who it is for
Small crypto exchanges, wallets, payment and fintech companies, and online gambling operators that must screen
customers and incoming transfers but cannot afford a full compliance stack or a dedicated team.

## How a customer connects (the integration path)
1. Register a project on the website (name, contact email, optional webhook URL). You get an API key, shown once.
   On the hosted service a new project is reviewed and activated by the operator (usually within one working day).
2. Your developers call our REST API from your backend with `Authorization: Bearer <API key>`.
   You do NOT give us access to your systems or your API. We never see your customers' passwords or your keys.
3. Typical calls: screen a customer name (`POST /screening/check-name`), screen a wallet address
   (`POST /screening/check-address`), and send each incoming transfer to the agent (`POST /agent/transfers`).
4. You act on the answer in your own system. Decisions are `accepted`, `review` (a human must look) or `rejected`.
5. Optional: create an owner account for the compliance dashboard (`/owner/register`, password plus authenticator app)
   to read explanations, approve held cases, set policy and download reports.
6. Optional later: switch the agent from MONITOR to OPERATE. Then the agent may send signed webhook instructions
   (release, hold, reject) to a URL you give us. We only call that URL; you verify the HMAC signature.

So: your developers integrate our API into your product. You give us only (a) the data of the transfer or person being
checked and (b) optionally one webhook URL that we call in OPERATE mode.

## Modes
- MONITOR (default): the agent screens, classifies and explains. It changes nothing in your systems, ever.
- OPERATE: only after the owner enables it with a fresh authenticator code and explicit consent; only for operations
  the owner allowed; only inside the owner's policy (limits, assets, chains, blocked countries). A kill switch returns
  to MONITOR instantly.
- Sanctions matches and ambiguous matches are never handled automatically: they always go to a human.

## What gets checked
Sanctions lists loaded automatically: US OFAC SDN and Consolidated, EU Financial Sanctions (FSF), UN Security Council,
UK OFSI list, Swiss SECO, Canada SEMA, Australia DFAT. Name matching handles reordering, transliteration, aliases and
suffixes. Wallet addresses are matched exactly against addresses listed by OFAC. Lists refresh daily; the agent refuses to
auto-clear if the lists required for your jurisdiction (US or EU) are stale.

## Trust and safety
Every decision is written to an append-only, hash-chained journal; tampering is detectable and shown in the dashboard.
The AI model can only raise caution, never lower it: a deterministic sanctions floor and a plain-code policy engine sit
between the model and any action. Text from counterparties (names, memos) is treated as untrusted data (prompt-injection
resistant). The agent holds no keys and cannot move funds. Owner login uses password + authenticator app.

## Other modules
Wallet ownership verification (prove a customer controls a wallet), age verification (18+ check for gambling and
adult services), Travel Rule messaging through the vendored open-source TRISA Envoy node.

## Pricing (pilot phase)
Pilot programme: free for the first design-partner companies (screening, wallet checks, AI agent in MONITOR mode, dashboard,
direct support from the founder) in exchange for honest feedback. Indicative plans after the pilot, NOT final:
Starter from about 49 EUR per month (fixed monthly volume, MONITOR mode, dashboard, daily digest) and Growth from about
199 EUR per month (higher volume, OPERATE mode with signed webhooks, policy engine, priority support).
Self-hosted is free forever (MIT licence) with optional paid support. Final prices will be set with pilot feedback.
Self-hosting is free forever and you can move between hosted and self-hosted without changing your integration.

## Limits you should know
Early software, no mainnet, no formal certification. Reporting duties and thresholds are not encoded; legal texts are
marked for counsel review. Do not treat output as legal advice.

## Contact
Use the signup form to start a pilot, or open an issue on GitHub (github.com/pilipandr770/AML-18). Operator: andrii-it.de.
