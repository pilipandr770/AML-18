# AML+18

Ein offener, selbst hostbarer Compliance-Baustein für Krypto-Projekte im
EU-Raum. Ziel ist **kein** fertiges Produkt für ein bestimmtes Geschäftsmodell
(Börse, Umtauschdienst, Wallet, Casino, Adult-Plattform) — sondern das
rechtliche Fundament, auf dem solche Projekte aufbauen können: aus einer
bloßen Blockchain-Adresse eine **verifizierte Entität** machen (Sanktionsprüfung,
Nachweis der Kontrolle über eine Self-Hosted-Wallet, Altersverifikation).
Alles, was danach kommt — Glücksspiel-Lizenz, Adult-Content-Freigabe,
Börsenzulassung — ist bewusst nicht Teil dieses Projekts.

Es deckt drei regulatorische Anforderungen ab, die ein kleiner CASP
(Crypto-Asset Service Provider) sonst separat bei Anbietern wie Sumsub oder
Notabene einkaufen müsste:

1. **EU Travel Rule** (Verordnung (EU) 2023/1113 „TFR" i. V. m. MiCA und der
   AMLR) — Sanktions-/AML-Screening bei Krypto-Transfers zwischen zwei
   VASPs (Crypto-Asset Service Providern), über das echte TRISA-Protokoll.
2. **Wallet-Ownership-Verification** — Nachweis der Kontrolle über eine
   Self-Hosted-Wallet-Adresse bei Transfers ab einem konfigurierbaren
   EUR-Schwellenwert (Standard: €1.000), wie von den EBA-Travel-Rule-
   Leitlinien und BaFins § 15a GwG verlangt.
3. **Altersverifikation (18+)** — nicht nur für Adult-Content/PPV-
   Plattformen, sondern grundsätzlich auch für Online-Glücksspiel (GlüStV)
   einsetzbar.

Alle drei sind architektonisch strikt voneinander getrennt (eigene
Datenbanktabellen, keine Verknüpfung) — DSA Art. 28, JMStV, TFR und die
EBA-Leitlinien sind unterschiedliche Regelungsregime, die nicht in einem
Datensatz vermischt werden dürfen. Details und Rechtsgrundlagen:
`ANFORDERUNGEN.md`.

**Strategie:** Zuerst ein wirklich nützliches, einfach einzusetzendes
Werkzeug schaffen, das kleine CASPs organisch übernehmen — mit offenem,
nachvollziehbarem Code, klarer Dokumentation und einer Oberfläche, die ein
Compliance-Officer tatsächlich benutzen kann. Monetarisierung kommt erst
danach.

## Die drei Einstiegspunkte

Jede der drei Anforderungen hat einen eigenen, unabhängigen Einstiegspunkt
für ein anderes Projekt, das diesen Container nutzt:

| Anforderung | Einstiegspunkt | Warum |
|---|---|---|
| Travel-Rule-Screening | Echtes TRISA-Protokoll (`envoy.local:8100`) | TRISA ist ein VASP-zu-VASP-Protokoll — das eigene Projekt muss selbst einen TRISA-Knoten betreiben (z. B. ebenfalls mit vendoriertem Envoy) und sich damit verbinden, nicht nur einen REST-Call machen. |
| Wallet-Ownership-Verification | REST (`/wallet-ownership/*`), API-Schlüssel über `/developer/signup` | Gilt für Self-Hosted-Wallets — dort gibt es keinen zweiten VASP, mit dem man TRISA sprechen könnte. |
| Altersverifikation | REST (`/age-verify/*`), API-Schlüssel über `/developer/signup` | Eigenständige, von Travel-Rule-Identitätsdaten getrennte Prüfung. |

Der Travel-Rule-Weg ist bewusst der „echte", nicht ein vereinfachter
REST-Shortcut: Er zeigt, dass ein anfragendes Projekt tatsächlich über das
offizielle Protokoll sprechen muss, damit seine Transfers automatisch
gescreent werden — nicht nur eine API aufrufen, die man auch umgehen könnte.

## Komponenten

- **`envoy/`** — [TRISA Envoy](https://github.com/trisacrypto/envoy),
  MIT-lizenziert, lokal vendoriert (siehe `envoy/VERSIONS.md` für die
  gepinnte Upstream-Revision, `patches/README.md` für lokale Anpassungen).
  Reine Transportschicht: kein eingebautes Sanktions-Screening, aber genau
  ein Erweiterungspunkt dafür — ein ausgehender Webhook bei jeder
  eingehenden Travel-Rule-Nachricht, hier an `compliance.local` angebunden.
  Der lokale Stack enthält zusätzlich `counterparty.local` (Stand-in für
  ein fremdes, andockendes Projekt) und `gds.local` (eine vollständig
  lokale, selbst-enthaltene TRISA-Verzeichnisdienst-Sandbox — keine
  Registrierung bei einem echten Testnet nötig).
- **`compliance-service/`** — der eigentliche Mehrwert: ein Flask-Microservice
  mit drei unabhängigen Modulen:
  - `screening/` + `webhook/` — empfängt Envoys Webhook, prüft IVMS101-
    Identitätsdaten gegen echte Sanktionslisten (OFAC SDN, EU-Konsolidierte
    Liste) und antwortet mit einer expliziten Entscheidung
    (Akzeptieren/Prüfen/Ablehnen).
  - `wallet_ownership/` — Signatur-Challenge- und EVM-Testtransfer-basierte
    Verifikation der Kontrolle über eine Self-Hosted-Wallet-Adresse.
  - `ageverify/` — datensparsamer Altersnachweis, mit Mock-Adapter für
    lokale Entwicklung und EU-OID4VP-Adapter für den echten Blueprint-Flow.
  - `review_ui/` — die Oberfläche für den Compliance-Officer
    (Entscheidungsliste, Detailansicht mit Begründung, manuelle Prüfung).
  - `developer_portal/` — das Entwicklerportal: Projekt registrieren,
    API-Schlüssel erhalten, Integrationsanleitung. Gate für die beiden
    REST-APIs (`wallet_ownership`, `ageverify`), die ohne gültigen
    API-Schlüssel `401` zurückgeben.
- **`vendor/ageverify/`** — lokal vendorierte Upstream-Komponenten der
  EU Age Verification Blueprint Referenzimplementierung (Verifier-UI,
  Verifier-Backend, technische Spezifikation).
- **`examples/travel-rule-demo/`** — Demo-Skripte, die den Travel-Rule-
  Einstiegspunkt end-to-end vorführen (siehe unten).

## Schnellstart

Voraussetzungen: Docker, Docker Compose, Go (für `cmd/fsi`, Envoys
eingebautes Test-Tool), Git Bash/`openssl` unter Windows für die lokale
Zertifikatsgenerierung.

```
powershell -File scripts/bootstrap.ps1
```

Das Skript ist idempotent — bereits vorhandene Zertifikate, GDS-Registrierung,
API-Schlüssel und der Webhook-HMAC-Key werden übersprungen, nicht neu
erzeugt (Flag `-Reset` erzwingt eine vollständige Neuinitialisierung). Es
erledigt:

1. `.env` aus `.env.example` anlegen, `GIT_REVISION` setzen.
2. Lokale TLS-Sandbox-Zertifikate erzeugen (`envoy/.secret/generate.sh`).
3. `docker compose build && docker compose up -d` — startet den gesamten
   Stack: `gds.local`, `envoy.local`, `counterparty.local`,
   `compliance.local`, `ageverify-verifier`.
4. Beide TRISA-Knoten bei der lokalen Verzeichnis-Sandbox registrieren
   (`go run ./cmd/fsi gds:init`).
5. API-Schlüssel für `envoy.local`/`counterparty.local` erzeugen (für
   `cmd/fsi` und die Demo-Skripte — landen ausschließlich in
   `envoy/tmp/creds/*.txt`, gitignored, nie in der Konsolenausgabe).
6. Den Webhook-HMAC-Key erzeugen und in `.env` eintragen, damit
   `envoy.local` und `compliance.local` sich gegenseitig authentifizieren
   können.

Danach:
- Compliance-Officer-Oberfläche: `http://localhost:8300/review/`
- Envoy Web-UI: `http://localhost:8000/`
- EU-Verifier-Backend: `http://localhost:8080/`

## Travel-Rule-Demo (Einstiegspunkt-Nachweis)

```
python examples/travel-rule-demo/send_transfer.py --clean
python examples/travel-rule-demo/send_transfer.py --flagged
```

Der erste Aufruf schickt einen Transfer mit sauberen, synthetischen
Identitäten von `counterparty.local` (Stand-in für ein fremdes Projekt) an
`envoy.local` — Ergebnis in der Officer-Oberfläche: **accepted**. Der
zweite Aufruf verwendet einen Namen, live abgefragt aus der bereits
eingespielten OFAC-/EU-Sanktionsliste — Ergebnis: **review**/**rejected**,
mit sichtbarem Treffer, Score und Begründung. Details:
`examples/travel-rule-demo/README.md`.

## Entwicklerportal (`/developer/`)

Einstiegspunkt für ein fremdes Projekt, das die beiden REST-APIs nutzen
will (Wallet-Ownership, Altersverifikation) — keine Anmeldung nötig,
sofort ein API-Schlüssel:

```
curl -X POST http://localhost:8300/developer/signup \
  --data-urlencode "name=Mein Projekt" \
  --data-urlencode "contact_email=dev@mein-projekt.example"
```

Antwort enthält den API-Schlüssel **einmalig** im Klartext (`aml18_sk_...`)
— er wird serverseitig nur als Hash gespeichert und kann nicht erneut
angezeigt werden. Bei Verlust: `POST /developer/api-key/rotate` mit dem
aktuellen Schlüssel als Bearer-Token, oder neu registrieren. Übersicht mit
Integrationsbeispielen: `http://localhost:8300/developer/`.

Beide folgenden REST-APIs verlangen den Schlüssel als Bearer-Token — ohne
gültigen, aktiven Schlüssel antworten sie mit `401`.

## Wallet-Ownership-Verification API

```
GET  /wallet-ownership/requirement?transfer_amount_eur=1500
POST /wallet-ownership/challenges          {"network": "ETH", "address": "0x..."}
POST /wallet-ownership/verifications       {"method": "signed_message", "challenge_id": "...", "signature": "0x..."}
GET  /wallet-ownership/verifications/<id>
```

Jeder Aufruf mit `Authorization: Bearer aml18_sk_...`. Zwei Methoden (beide
aus der EBA-Leitlinien-Liste zulässiger Verfahren): `signed_message`
(Server-Nonce signieren, sofort einsatzbereit, keine
Blockchain-Infrastruktur nötig) und `test_transfer` (kleiner EVM-Transfer,
benötigt `WALLET_OWNERSHIP_EVM_RPC_URL` + `WALLET_OWNERSHIP_EVM_SENDER_PRIVATE_KEY`
in `.env`).

## Altersverifikation API (privacy-preserving)

```
POST /age-verify/check
Authorization: Bearer aml18_sk_...
{
  "subject_reference": "platform-user-123",
  "proof_token": "opaque-proof-or-mock-token",
  "adapter": "mock|eu_oid4vp"
}
```

Antwort enthält nur den Altersentscheid (ja/nein) und Metadaten, keine
personenbezogenen Rohdaten aus dem Nachweis. Für den lokalen Einstieg:
`proof_token=mock:over18` -> `verified=true`, `proof_token=mock:under18` ->
`verified=false`.

Die EU-Integration (`eu_oid4vp`, Standard-Adapter in diesem Stack) läuft
über einen zustandsbehafteten Session-Flow:

```
POST /age-verify/sessions        {"subject_reference": "...", "adapter": "eu_oid4vp"}   # Bearer-Token erforderlich
GET  /age-verify/sessions/<id>                                                          # Bearer-Token erforderlich
GET  /age-verify/sessions/<id>/launch   # Deep-Link + QR für Wallet-Tests -- bewusst ohne Auth (Browser/Wallet-App öffnet direkt)
```

`scripts/run_ageverify_e2e_device_response.ps1` automatisiert den
kompletten Flow von der Credential-Ausstellung bis zur Verifikation gegen
den lokalen Stack.

## Stand des Projekts

- **Travel-Rule-Screening**: abgeschlossen und end-to-end über das echte
  TRISA-Protokoll verifiziert (siehe Demo oben). OFAC-SDN- und
  EU-Konsolidierte-Parser, phonetisch vorgefilterter Fuzzy-Abgleich
  (rapidfuzz + jellyfish/NYSIIS, MIT — bewusst nicht Beider-Morse/`abydos`,
  da GPLv3+), kyrillische Transliteration, konservative
  Akzeptieren/Prüfen/Ablehnen-Entscheidungslogik. Gegen die echte, aktuelle
  OFAC-SDN-Liste verifiziert (19.210 Einträge).
- **Wallet-Ownership-Verification**: `signed_message`-Methode live
  verifiziert; `test_transfer`-Methode nur unit-getestet, noch nicht gegen
  ein echtes Testnetz validiert.
- **Altersverifikation**: `eu_oid4vp`-Adapter end-to-end gegen den
  vendorierten Referenz-Issuer und -Verifier verifiziert, inklusive
  automatisierter frischer Credential-Ausstellung.
- **Entwicklerportal**: Selbstbedienungs-Registrierung + API-Schlüssel
  live über Browser-Formular und curl verifiziert; `wallet_ownership`- und
  `ageverify`-REST-Endpunkte (mit Ausnahme der Wallet-App-Deep-Link-Seiten
  `/launch`/`qr.svg`) sind jetzt hinter dem Schlüssel geschlossen (vorher:
  komplett offen — ein echtes, jetzt geschlossenes Sicherheitsloch).
- **Compliance-Officer-Oberfläche**: Entscheidungsliste, Detailansicht mit
  Begründung, manuelle Prüfung mit Audit-Log. Noch **ohne
  Authentifizierung** — vor jedem echten Einsatz nachzurüsten.
- **Offen**: GlüStV-Rechtsgrundlagen für den Glücksspiel-Anwendungsfall
  (siehe `ANFORDERUNGEN.md`, Teil B.3); automatische Anbindung der
  Wallet-Ownership-Prüfung an den Webhook-/Screening-Entscheidungspfad
  (aktuell ein eigenständig aufrufbarer Endpunkt); Basis-Authentifizierung
  für die Compliance-Oberfläche; Entwicklerportal-Zugang hat noch kein
  Login/Recovery jenseits des einmalig gezeigten Schlüssels (Rotation via
  `/developer/api-key/rotate` funktioniert, Passwort-Login nicht — bewusstes
  MVP-Scoping).

Testsuite: `python -m pytest` im Verzeichnis `compliance-service/`.

## Entwicklungsnotizen

Die lokale Entwicklung fand in einer Reihe von Claude-Code-Sitzungen statt —
die vollständige Fehlersuche (Windows-spezifische Stolpersteine, mehrere
echte Upstream-Bugs in Envoy gefunden und gepatcht, Erkenntnisse aus der
Verifikation mit Live-Daten) ist im Projektgedächtnis festgehalten und wird
hier nicht dupliziert. `patches/README.md` (Englisch, da teilweise an das
Upstream-Projekt gerichtet) dokumentiert die lokalen Envoy-Anpassungen.
