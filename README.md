# AML+18

Open-Source-Compliance-Baustein für Krypto-Zahlungen (USDC) im EU-Raum.
Ziel ist ein eigenständiges, wiederverwendbares Werkzeug, auf dessen Basis
sich eine Börse, ein Umtauschdienst (Exchanger) oder eine Wallet aufbauen
lässt – nicht an ein einzelnes Geschäftsmodell gebunden. Es deckt zwei
regulatorische Anforderungen ab, die ein kleiner CASP (Crypto-Asset Service
Provider) sonst separat bei Anbietern wie Sumsub oder Notabene einkaufen
müsste:

1. **EU Travel Rule** (Verordnung (EU) 2023/1113 „TFR" i. V. m. MiCA) —
   Sanktions-/AML-Screening bei Krypto-Transfers, mit vollständig offener,
   selbst hostbarer Architektur (ein echter Vorteil gegenüber der BaFin,
   die technische Architektur statt bloßer Anbieter-Zusicherungen sehen
   will).
2. **Altersverifikation (18+)** — nicht nur für Adult-Content/PPV-Plattformen,
   sondern grundsätzlich auch für Online-Glücksspiel (GlüStV) einsetzbar,
   architektonisch strikt getrennt von den Travel-Rule-Identitätsdaten
   (DSA Art. 28, JMStV und TFR sind drei unterschiedliche Regelungsregime,
   die nicht in einem Datensatz vermischt werden dürfen).

**Strategie:** Zuerst ein wirklich nützliches, einfach einzusetzendes
Werkzeug schaffen, das kleine CASPs organisch übernehmen — Monetarisierung
kommt erst danach. Der konkrete Anforderungskatalog wird direkt aus den
einschlägigen Rechtsvorschriften abgeleitet, nicht aus eigenen Annahmen
(siehe `ANFORDERUNGEN.md`, sobald verfügbar).

## Komponenten

- **`envoy/`** (hier nicht eingecheckt — vendorierter Klon, siehe unten) —
  [TRISA Envoy](https://github.com/trisacrypto/envoy), MIT-lizenziert,
  selbst gehosteter Travel-Rule-Protokoll-Knoten. Reine Transportschicht:
  kein eingebautes Sanktions-Screening, aber genau ein Erweiterungspunkt
  dafür — ein ausgehender Webhook bei jeder eingehenden Travel-Rule-Nachricht.
- **`compliance-service/`** — der eigentliche Mehrwert: ein Flask-Microservice,
  der Envoys Webhook empfängt, IVMS101-Identitätsdaten gegen echte
  Sanktionslisten prüft (OFAC SDN, EU-Konsolidierte Liste) und mit einer
  expliziten Entscheidung antwortet (Akzeptieren/Prüfen/Ablehnen). Enthält
  außerdem die Oberfläche für den Compliance-Officer (Entscheidungsliste,
  Detailansicht mit Begründung, manuelle Prüfung). Altersverifikation ist
  als eigener, datensparsamer API-Pfad mit Adapter-Schicht umgesetzt:
  synchron für Mock-Nachweise (`POST /age-verify/check`) und zustandsbehaftet
  für die EU-OID4VP-/Verifier-Integration (`POST /age-verify/sessions`,
  `GET /age-verify/sessions/<id>`).
- **`vendor/ageverify/`** — lokal vendorierte Upstream-Komponenten der
  EU Age Verification Blueprint Referenzimplementierung (Verifier-UI,
  Verifier-Backend, technische Spezifikation), damit Anpassungen lokal und
  reproduzierbar weiterentwickelt werden können.

## Einrichtung

```
git clone https://github.com/trisacrypto/envoy.git
cd envoy
git apply ../patches/0001-fsi-set-routing-protocol.patch
git apply ../patches/0002-fix-webhook-default-response-fallthrough.patch
cd .secret && ./generate.sh && cd ..   # bei Problemen unter Windows siehe patches/README.md
export GIT_REVISION=$(git rev-parse --short HEAD)
docker compose build
docker compose up -d
go run ./cmd/fsi gds:init
docker compose exec envoy.local envoy createuser -e admin@envoy.local -r admin
docker compose exec counterparty.local envoy createuser -e admin@counterparty.local -r admin
```

Anschließend, aus `compliance-service/`:

```
cp .env.example .env
# WEBHOOK_AUTH_KEY_ID / WEBHOOK_AUTH_KEY_SECRET eintragen, erzeugt via:
docker compose exec envoy.local envoy hmackey

docker compose -f ../envoy/docker-compose.yaml -f docker-compose.override.yaml \
    --env-file ./.env up -d --build
```

Warum die Reihenfolge der `-f`-Flags und `--env-file` wichtig sind, steht
in `docker-compose.override.yaml` (Compose löst relative Pfade relativ zum
Verzeichnis der zuerst genannten Datei auf).

Die Compliance-Oberfläche ist danach unter `http://localhost:8300/review/`
erreichbar.

Für die lokale EU-Altersverifikationsentwicklung kann der offizielle
Verifier-Backend-Dienst zusammen mit dem Compliance-Service separat gestartet
werden:

```
cp compliance-service/.env.example compliance-service/.env
docker compose -f docker-compose.ageverify.yaml up -d --build
```

Der Stack baut den vendorierten Verifier-Backend-Code lokal zu einem nativen
Image für die Host-Architektur, statt das vorgebaute Upstream-Image unter
Emulation laufen zu lassen.

Dabei setzt der Compose-Stack automatisch:
- `AGEVERIFY_DEFAULT_ADAPTER=eu_oid4vp`
- `AGEVERIFY_EU_VERIFIER_BASE_URL=http://ageverify-verifier:8080`

Danach laufen lokal:
- Compliance-Service: `http://localhost:8300`
- EU Verifier Backend: `http://localhost:8080`

## Altersverifikation API (privacy-preserving)

Der Compliance-Service bietet einen separaten Endpoint für Altersnachweise:

```
POST /age-verify/check
```

Request:

```
{
  "subject_reference": "platform-user-123",
  "proof_token": "opaque-proof-or-mock-token",
  "adapter": "mock|eu_oid4vp"   // optional, default via ENV
}
```

Antwort enthält nur den Altersentscheid (ja/nein) und Metadaten, keine
personenbezogenen Rohdaten aus dem Nachweis.

Relevante ENV-Variablen:

```
AGEVERIFY_DEFAULT_ADAPTER=mock
AGEVERIFY_MIN_AGE=18
AGEVERIFY_EU_VERIFIER_BASE_URL=
AGEVERIFY_EU_VERIFIER_VERIFY_PATH=/verify
AGEVERIFY_EU_VERIFIER_TIMEOUT_SECONDS=5
```

Für den lokalen Einstieg kann der `mock`-Adapter verwendet werden:
- `proof_token=mock:over18` -> `verified=true`
- `proof_token=mock:under18` -> `verified=false`

Die EU-Integration (`eu_oid4vp`) läuft über einen separaten Session-Flow gegen
den offiziellen Verifier-Backend-Dienst:

```
POST /age-verify/sessions
{
  "subject_reference": "platform-user-123",
  "adapter": "eu_oid4vp",
  "min_age": 18
}
```

Antwort:

```
{
  "session_id": "...",
  "status": "pending",
  "transaction_id": "...",
  "request_value": "..."
}
```

Danach Status pollen:

```
GET /age-verify/sessions/<session_id>
```

Für lokale Entwicklung gibt es zusätzlich eine Helper-Seite pro Session:

```
GET /age-verify/sessions/<session_id>/launch
```

Sie rendert einen Deep-Link für Wallets auf demselben Gerät sowie ein
serverseitig generiertes SVG-QR für Cross-Device-Tests.

Sobald der externe Verifier eine Wallet-Antwort verarbeitet hat, persistiert
der Compliance-Service nur noch das finale Alters-Urteil (z. B.
`verified=true`) plus einen Hash des Proof-Artefakts, nicht aber den
Rohnachweis selbst.

Aktuelle ENV-Variablen für den EU-Verifier:

```
AGEVERIFY_EU_VERIFIER_BASE_URL=
AGEVERIFY_EU_VERIFIER_TIMEOUT_SECONDS=5
```

Für einen echten EU-Blueprint-Flow startet der Client zunächst eine Session:

```
POST /age-verify/sessions
```

und pollt anschließend:

```
GET /age-verify/sessions/<session_id>
```

Die offiziell vendorierten EU-Blueprint-Quellen sind in
`vendor/ageverify/` eingecheckt und in `vendor/ageverify/VERSIONS.md`
gepinnt.

## Stand des Projekts

- **Phase 0** (Webhook + HMAC-Auth + IVMS101-Parsing): abgeschlossen,
  Ende-zu-Ende gegen einen echten Zwei-Knoten-Envoy-Stack verifiziert.
- **Phase 1** (echtes Sanktions-Screening): abgeschlossen. OFAC-SDN- und
  EU-Konsolidierte-Parser, phonetisch vorgefilterter Fuzzy-Abgleich
  (rapidfuzz + jellyfish/NYSIIS, MIT — bewusst nicht Beider-Morse/`abydos`,
  da GPLv3+), kyrillische Transliteration, konservative
  Akzeptieren/Prüfen/Ablehnen-Entscheidungslogik. Gegen die echte, aktuelle
  OFAC-SDN-Liste verifiziert (19.210 Einträge) — eine synthetische
  Transaktion mit dem Namen einer real gelisteten Person wurde korrekt zur
  Prüfung markiert.
- **Phase 2** (abgeschlossen): Compliance-Officer-Oberfläche
  (Entscheidungsliste, Detailansicht mit Begründung, manuelle Prüfung mit
  Audit-Log). Noch **ohne Authentifizierung** — vor jedem echten Einsatz
  nachzurüsten.
- **Als Nächstes**: Anforderungskatalog aus den tatsächlichen EU-/DE-
  Rechtstexten (MiCA, TFR, DSA Art. 28, JMStV, GlüStV) ableiten und daraus
  die Roadmap priorisieren; UN-Konsolidierte-Liste als weitere Quelle;
  EU Age Verification Solution (OID4VP) als primären
  Altersverifikations-Adapter integrieren;
  Basis-Authentifizierung für die Compliance-Oberfläche.

Testsuite: `python -m pytest` im Verzeichnis `compliance-service/`.

## Entwicklungsnotizen

Die lokale Entwicklung fand in einer Reihe von Claude-Code-Sitzungen statt —
die vollständige Fehlersuche (Windows-spezifische Stolpersteine, zwei echte
Upstream-Bugs in Envoy gefunden und gepatcht, Erkenntnisse aus der
Verifikation mit Live-Daten) ist im Projektgedächtnis festgehalten und wird
hier nicht dupliziert. `patches/README.md` (Englisch, da an das
Upstream-Projekt gerichtet) dokumentiert die zwei benötigten Envoy-Patches.
