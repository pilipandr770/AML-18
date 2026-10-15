# Pilot prospects and outreach (working document)

Status: 2026-10-15. Desk research from web search only; nothing here has been contacted. Verify every fact on the
company's own site before writing to anyone. Facts marked (secondhand) come from news or aggregator pages.

## Who actually needs this

Market context (secondhand, cointelegraph / ESMA coverage): the MiCA transition period ended on 1 July 2026. Firms
without a MiCA authorisation must stop serving EU clients, only a minority of pre-MiCA national registrations have
converted, and regulators check whether the promised AML and sanctions staffing really exists (Austria's FMA reportedly
froze new business at KuCoin EU over vacant AML roles). The pain we sell into: small teams that must screen customers
and transfers but cannot hire a full compliance function.

Good fit: small CASPs and crypto-adjacent regulated firms (custody, OTC, wallets, payments, crypto ATMs), companies
that are hiring a first compliance or AML officer (the open job is the pain), gambling operators that need age checks.
Poor fit: large licensed exchanges and banks; they already run commercial screening stacks.

## Concrete leads found (verify before use)

| Company | Why it fits | Evidence | Fit |
|---|---|---|---|
| **Kurant GmbH** (Vienna; crypto ATMs, subsidiary of Coinfinity) | Strict KYC from the first cent, ATM network in AT/DE/ES, hiring "Leitung Compliance / Geldwäschebeauftragte/r" | job posting and Dealroom profile (secondhand) | high |
| **Coinfinity** (Austria; Kurant's parent) | Bitcoin broker, same regulatory load | news coverage (secondhand) | medium |
| **Fung** (Amsterdam) | Pre-seed crypto/fiat payments startup aiming for DNB regulation and MiCA readiness | Silicon Canals (secondhand, date unknown) | medium |
| **Confirmo** (Slovakia) | Crypto payment gateway, MiCA approval reported Dec 2025 | CB Insights / search (secondhand) | medium |
| **Tangany** (Munich) | B2B custody, MiCAR licence 2025, 3B EUR custody claimed by the company | company blog, AMF register | low to medium (probably already has a stack; could still be a second-opinion or backup screening layer) |
| Anonymous "European crypto company growing in the DACH region" | Michael Page is hiring a MiCAR compliance team in Germany (posting dated 26 May 2026) | Michael Page posting | unknown; a recruiter will not forward a cold pitch, but the posting proves the pain exists |

Not recommended as targets: Bitpanda, Coinbase, BitGo Europe, Crypto Finance (Frankfurt), Commerzbank, DZ Bank, Trade
Republic. They have dedicated compliance teams and vendor stacks; use them only as examples of who holds licences.

Could not verify at all: Honeycoin (Berlin). Search returned nothing; check their site and Impressum first.

## How to build the real list (the part search could not do)

1. **ESMA interim MiCA register of CASPs** (public CSV, updated roughly weekly): filter by home state and by services
   such as "transfer services" or "exchange"; sort out the small names. Needs a download, so ask first.
2. **BaFin company register** for Kryptoverwahrgeschäft and related permissions (Germany).
3. **Job boards**: web3.career, StepStone, LinkedIn for "MiCAR", "Geldwäschebeauftragter", "AML Officer" at crypto
   companies with fewer than 50 staff. A company hiring its first AML person is the best lead.
4. **Warm routes in Frankfurt**: local blockchain and fintech meetups, the Bundesblock/Bitkom-style associations, and
   TechQuartier. Introductions beat cold outreach; verify event dates and organisers yourself.
5. **United States** (only if you decide to target it): small crypto startups on Y Combinator's Work at a Startup list
   and in the Techstars / a16z portfolio lists. Different regulator (FinCEN, OFAC), same product; the US-profile is built.

## Rules for contacting them (Germany)

Unsolicited marketing e-mail to businesses is restricted under UWG § 7 (consent generally required; "presumed consent"
is narrow). Safer routes: a personal LinkedIn message with a specific reason, a warm introduction, a call to the
published contact line, or a reply to a job posting that is clearly about compliance. Always include the Impressum data
(already on the site), identify yourself, and make opting out trivial. Get legal advice if you plan a mailing; this
paragraph is a practical note, not legal advice.

## Outreach draft (English, short)

Subject: Sanctions screening for a small compliance team (free pilot)

> Hi {first name},
> I saw that {company} {specific fact: is hiring an AML officer / runs the crypto ATM network / just got its MiCA licence}.
> I built AML+18, an open-source sanctions and wallet-screening layer with an AI agent that explains every decision
> and never acts outside limits you set. Your developers call a REST API; you give us no access to your systems.
> I am looking for 3 to 5 design partners for a free pilot and honest feedback. A 20-minute call, or I can send a
> short integration guide: https://aml.andrii-it.de/docs/
> Andrii Pylypchuk, Frankfurt am Main, andrii-it.de

## Outreach draft (Deutsch, kurz)

Betreff: Sanktions-Screening für ein kleines Compliance-Team (kostenloser Pilot)

> Hallo {Vorname},
> mir ist aufgefallen, dass {Firma} {konkreter Anlass: einen Geldwäschebeauftragten sucht / das Krypto-Automatennetz betreibt / kürzlich die MiCAR-Erlaubnis erhalten hat}.
> Ich habe AML+18 gebaut: eine Open-Source-Schicht für Sanktions- und Wallet-Prüfung mit einem KI-Agenten, der jede
> Entscheidung begründet und nie außerhalb Ihrer Grenzen handelt. Ihre Entwickler rufen eine REST-API auf; Sie geben
> uns keinen Zugriff auf Ihre Systeme. Ich suche 3 bis 5 Design-Partner für einen kostenlosen Pilot mit ehrlichem Feedback.
> 20 Minuten Gespräch, oder ich schicke Ihnen den Integrationsleitfaden: https://aml.andrii-it.de/docs/
> Andrii Pylypchuk, Frankfurt am Main, andrii-it.de

## Honest expectations

Large licensed players will not switch for a free pilot. The realistic first customers are very small teams without a
compliance stack, or teams that want a second screening layer. Track every contact and objection; the feedback itself is
the output of this phase, and it is what the YC application should be built on.
