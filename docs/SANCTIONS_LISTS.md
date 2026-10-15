# Sanctions lists

AML+18 ingests every open, machine-readable sanctions list below, refreshes each independently
(`sanctions-cron`, default daily; one failing source never blocks the others) and screens names and
cryptocurrency addresses against all of them. Each parser was verified against the real published file
(record counts below are from the files downloaded on 2026-10-15).

| Source id | Publisher / list | Format | Records | Notes |
|---|---|---|---|---|
| `OFAC_SDN` | US Treasury OFAC, Specially Designated Nationals | XML | 19,430 | Includes ~1,000 listed crypto addresses (`Digital Currency Address - XBT/ETH/TRX/USDT/...`) |
| `OFAC_CONSOLIDATED` | OFAC Consolidated (non-SDN) lists | XML (same schema as SDN) | 481 | |
| `EU_FSF` | EU Financial Sanctions Files (consolidated) | XML | 6,233 | Uses the EU's published public access token (`PUBLIC_TOKEN`, overridable) |
| `UN_CONSOLIDATED` | UN Security Council Consolidated List | XML | 1,010 | |
| `UK_SANCTIONS_LIST` | UK Sanctions List (FCDO; replaced the OFSI consolidated list) | XML | 6,397 | Open Government Licence v3.0 |
| `CH_SECO` | Swiss SECO sanctions list | XML | 7,112 | De-listed targets skipped; wallets extracted from free text |
| `CA_SEMA` | Canada, Special Economic Measures Act consolidated list | XML | 5,707 | See limitations |
| `AU_DFAT` | Australia DFAT Consolidated Sanctions List | XLSX | 4,009 | |

All eight together: 50,379 entities, 1,118 listed crypto addresses, ingest ≈ 1 minute.

## Screening

- **Names**: phonetic blocking on the first and last significant name tokens (legal-form suffixes, particles and generic
  business words such as "Ltd", "Trading", "Group" are ignored so "Coral Energy" finds "Coral Energy PTE Ltd"), then
  order-insensitive token scoring. A token subset only counts when at least two tokens are shared, so one-word aliases do
  not match every person with that given name. Checked on the real data: ordinary Western names produce 0–1 weak hits,
  while real listed names are found with suffix, reordering and aliases.
- **Crypto addresses**: exact match (EVM addresses case-insensitive, other chains exact) against active entities in active
  snapshots. `POST /screening/check-address`; the agent screens the sender address and treats a hit as
  `recommend_block` that is never automatic. Addresses that appear only in free text (UK, SECO) are extracted by pattern.
- Changing the blocking logic bumps `INDEX_VERSION`, which is part of each list's content hash, so all lists re-index on their next refresh.

## Jurisdiction profiles

A "clear" requires the profile's *required* lists to be loaded and fresh (US: `OFAC_SDN`; EU: `EU_FSF` + `OFAC_SDN`).
*Recommended* lists are screened when loaded and reported when missing, but do not gate a clear. All legal readings of
these lists are configuration marked **REQUIRES COUNSEL REVIEW**.

## Limitations

- Canada JVCFOA (Magnitsky) has no separate machine-readable file that could be found; only the SEMA file is ingested.
- Canada SEMA carries no addresses; DFAT identity-document numbers are free text and are not parsed.
- Only the first date of birth / nationality is promoted to the normalized fields (all values are kept in the raw record).
- Lists not published as open data (e.g. commercial PEP / adverse-media datasets) are out of scope.
- Terms of use: the UK list is published under the Open Government Licence v3.0 ("Contains public sector information
  licensed under the Open Government Licence v3.0"); SECO data is Swiss open government data. Check each publisher's current
  terms before redistributing the data itself (this project downloads it at runtime and does not bundle it).
