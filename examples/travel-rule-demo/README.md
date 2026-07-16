# Travel Rule entry-point demo

Proves that an external wallet/CASP connecting to this container over the
real TRISA protocol gets screened automatically, with no code of its own
beyond speaking TRISA. `counterparty.local` stands in for that external
project -- it's the same vendored Envoy binary as `envoy.local`, just a
second instance, registered as a separate VASP in the local sandbox
directory (`gds.local`).

## Why the direction matters

`compliance.local`'s webhook is wired to `envoy.local`
(`TRISA_WEBHOOK_URL` in `docker-compose.yml`). Envoy only calls its webhook
for transfers it *receives*, so the demo must send **from
`counterparty.local` to `envoy.local`** -- the reverse of Envoy's own
built-in `cmd/fsi tests:trisa` command, which sends the other way and would
never touch our webhook.

## Prerequisites

1. The full stack running: `docker compose up -d` (or `scripts/bootstrap.ps1`).
2. `envoy/tmp/creds/counterparty_local_apikey.txt` present (created by
   `scripts/bootstrap.ps1`, or manually via
   `docker exec <counterparty container> envoy createapikey all`).
3. Python deps: `pip install requests` (already in `compliance-service/.venv`
   if you've set that up).

## Run it

```
python send_transfer.py --clean
```

Sends a transfer between two clean, synthetic identities. Expect the
compliance officer UI (`http://localhost:8300/review/`) to show
**accepted**.

```
python send_transfer.py --flagged
```

Sends a transfer where the originator's name is pulled live from the
already-ingested OFAC/EU sanctions data (a random `entity_type='person'`
row from `compliance-service`'s own database -- nothing hardcoded, so it
stays valid across list updates). Expect the officer UI to show
**review** or **rejected**, with the real match, its score, and the
matched sanctions-list entry visible in the decision detail page.

## What you're actually looking at

Open the decision detail page for each transaction
(`http://localhost:8300/review/<id>`) and compare the **Auftraggeber**
(originator) match panel between the two runs: the clean run's person-level
score stays low (`below_review_threshold`); the flagged run's person-level
score is a strong match (often 100.0 for an exact name) against a real
OFAC/EU-consolidated entry, with `rule_branch: high_score_uncorroborated` --
flagged for human review rather than auto-rejected, since name alone
(without a corroborating DOB/nationality match) isn't treated as
sufficient for an automatic reject. That's the actual compliance-officer
proof point: the system doesn't just pass everything through, and it shows
its reasoning, not just a verdict.
