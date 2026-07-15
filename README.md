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
  aktuell nur als Schnittstelle + isoliertes Datenmodell angelegt — noch
  keine echte Anbieter-Anbindung.

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
  Altersverifikations-Adapter (Zyphe / EU Age Verification Solution);
  Basis-Authentifizierung für die Compliance-Oberfläche.

Testsuite: `python -m pytest` im Verzeichnis `compliance-service/`.

## Entwicklungsnotizen

Die lokale Entwicklung fand in einer Reihe von Claude-Code-Sitzungen statt —
die vollständige Fehlersuche (Windows-spezifische Stolpersteine, zwei echte
Upstream-Bugs in Envoy gefunden und gepatcht, Erkenntnisse aus der
Verifikation mit Live-Daten) ist im Projektgedächtnis festgehalten und wird
hier nicht dupliziert. `patches/README.md` (Englisch, da an das
Upstream-Projekt gerichtet) dokumentiert die zwei benötigten Envoy-Patches.
