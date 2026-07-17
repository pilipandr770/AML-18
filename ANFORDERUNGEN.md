# Anforderungskatalog: EU-/DE-Rechtsgrundlagen für AML+18

**Zweck dieses Dokuments:** Die Roadmap dieses Projekts soll sich an
tatsächlichen, konkreten Vorgaben des Gesetzgebers orientieren — nicht an
eigenen Annahmen über sinnvolle Architektur. Dieses Dokument sammelt die
einschlägigen Artikel/Paragraphen, ordnet ihnen konkrete technische
Anforderungen zu und markiert den Vertrauensgrad jeder Aussage.

**Methodik und Einschränkung:** Die Angaben stammen aus einer mehrstufigen
Recherche (Web-Suche + Quellenauswertung + gegenadversarische Verifikation)
vom 2026-07-15. Ein Teil der Verifikationsschritte ist wegen
Kapazitätsgrenzen der Recherche-Infrastruktur nicht abgeschlossen worden.
Jede Aussage ist daher mit einem der folgenden Vertrauensgrade markiert:

- 🟢 **Bestätigt** — durch mindestens drei unabhängige Gegenprüfungen bestätigt (3:0 oder besser)
- 🟡 **Quellenbelegt, nicht gegengeprüft** — aus einer Primärquelle (EUR-Lex, BaFin.de, Bundestag.de, EU-Kommission) extrahiert, aber die adversarische Verifikation ist wegen Kapazitätsgrenzen nicht durchgelaufen. Sehr wahrscheinlich korrekt, aber vor einer Veröffentlichung/Beratung gegen den Originaltext prüfen.
- 🔴 **Nicht recherchiert** — für dieses Update nicht untersucht, offener Punkt für die nächste Recherche-Runde.
- ⚠️ **Widersprüchlich** — zwei Quellenaussagen widersprechen sich, Originaltext prüfen.

---

## Teil A — Krypto-Transfers: Travel Rule, MiCA, AML

### A.1 Verordnung (EU) 2023/1113 („TFR" / Travel Rule für Krypto-Transfers)

| # | Aussage | Fundstelle | Grad |
|---|---|---|---|
| A1 | Die Verordnung gilt ab **30. Dezember 2024** und erweitert den Rahmen der Verordnung (EU) 2015/847 auf Krypto-Transfers von in der EU registrierten Zahlungs-/Krypto-Dienstleistern. | [EUR-Lex, Zusammenfassung](https://eur-lex.europa.eu/EN/legal-content/summary/information-accompanying-transfers-of-funds-and-certain-crypto-assets.html) | 🟢 |
| A2 | Krypto-Transfers müssen von Auftraggeber- und Begünstigtenangaben begleitet werden: **Name, DLT-Adresse, Krypto-Konto-Nummer**. | [EUR-Lex, Zusammenfassung](https://eur-lex.europa.eu/EN/legal-content/summary/information-accompanying-transfers-of-funds-and-certain-crypto-assets.html) | 🟢 |
| A3 | Für Transfers zwischen zwei CASPs gibt es **keine Bagatellgrenze** — vollständige Auftraggeber-/Begünstigtenangaben sind immer erforderlich. Für Transfers von/zu **Self-Hosted-Wallets (unhosted)** gilt ab **€1.000** eine zusätzliche Pflicht: Prüfen, ob der Begünstigte die Adresse tatsächlich besitzt/kontrolliert. | [EUR-Lex](https://eur-lex.europa.eu/EN/legal-content/summary/information-accompanying-transfers-of-funds-and-certain-crypto-assets.html) | 🟢 |
| A4 | **Präzisiert gegen den Volltext** (vorherige Fassung hatte die Oder-Verknüpfung falsch dargestellt). Nach Art. 14(1) TFR müssen für den Auftraggeber mitgeführt werden: (a) Name; (b) DLT-Adresse (falls DLT-basiert) und Krypto-Konto-Nummer, sofern ein solches Konto existiert und für die Transaktion genutzt wird; (c) Krypto-Konto-Nummer (falls **nicht** DLT-basiert); (d) **entweder** [Adresse inkl. Land + amtliche Dokumentennummer + Kundennummer] **oder alternativ** Geburtsdatum/-ort — diese vier Felder sind kein Blumenstrauß frei kombinierbarer Alternativen, sondern zwei feste Bündel, von denen eines vollständig vorliegen muss; (e) LEI (oder gleichwertige Kennung), sofern im Nachrichtenformat vorgesehen und vom Auftraggeber bereitgestellt. Nach Art. 14(2) sind für den Begünstigten nur Name, DLT-Adresse und/oder Krypto-Konto-Nummer sowie LEI nötig — **kein** Adress-/Geburtsdatum-Bündel wie beim Auftraggeber (die volle Identitätsprüfung nach (d) gilt nur für den Auftraggeber). | [EUR-Lex, konsolidierter Volltext, Art. 14(1)-(2)](https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=CELEX:32023R1113) | 🟢 |
| A5 | **Geklärt durch Prüfung des Verordnungsvolltexts (EUR-Lex, konsolidierte Fassung).** Art. 2(4) enthält *zwei getrennte, beide mit „(a)"/„(b)" durchnummerierte* Ausschlusslisten innerhalb desselben Absatzes — eine für Geldtransfers (PSPs), eine eigene für Krypto-Transfers (CASPs). Das ist vermutlich die Ursache des scheinbaren Widerspruchs: je nachdem, welche der beiden „(a)"-Listen eine Quelle gelesen hat, kam sie zu einem anderen Ergebnis. Der krypto-spezifische Ausschluss lautet wörtlich: „This Regulation shall not apply to a transfer of crypto-assets where any of the following conditions is met: (a) both the originator and the beneficiary are crypto-asset service providers acting on their own behalf; (b) the transfer constitutes a person-to-person transfer of crypto-assets carried out without the involvement of a crypto-asset service provider." Ergänzt durch Erwägungsgrund 22, der dieselbe Regel im Vorspann vorwegnimmt. **Praktische Bedeutung:** Das ist **kein** genereller Freibrief für CASP-zu-CASP-Transfers — er greift nur, wenn *beide* Seiten für eigene Rechnung handeln (z. B. Treasury-Bewegungen zwischen den eigenen Wallets zweier Börsen), nicht bei den weitaus häufigeren kundenveranlassten CASP-zu-CASP-Transfers (z. B. Kunde verschiebt Guthaben von Börse A zu Börse B). Für Letztere gilt weiterhin uneingeschränkt die Nulltoleranz-Regel aus Erwägungsgrund 27 („no exemption ... should be granted to domestic low-value transfers of crypto-assets"). Für unseren Envoy-Demo-Flow (kundenveranlasste Transfers zwischen `counterparty.local` und `envoy.local`) ändert sich dadurch **nichts** — der bleibt vollständig im Anwendungsbereich. Der Ausschluss wäre nur relevant, falls das Projekt künftig einen reinen Eigenbestand-Transfer-Anwendungsfall (Proprietary-Treasury-Feature) abbilden wollte, was aktuell nicht geplant ist. | [EUR-Lex, konsolidierter Volltext, Art. 2(4) + Erwägungsgrund 22](https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=CELEX:32023R1113) | 🟢 |
| A6 | Die Verordnung gilt ausdrücklich **unbeschadet** der EU- und nationalen Sanktionsregime (z. B. VO (EG) 1210 xxx, restriktive Maßnahmen). Verpflichtete müssen interne Strategien/Verfahren/Kontrollen zur Umsetzung dieser Sanktionsmaßnahmen unterhalten — **das ist die rechtliche Grundlage für unser Sanktions-Screening**, nicht nur eine Nice-to-have-Ergänzung. | EUR-Lex, Volltext | 🟡 |

### A.2 EBA Travel-Rule-Leitlinien (Guidelines)

| # | Aussage | Fundstelle | Grad |
|---|---|---|---|
| A7 | Die EBA-Leitlinien gelten ab **30. Dezember 2024** und heben die alten gemeinsamen Leitlinien JC/GL/2017/16 auf. | [EBA PDF](https://www.eba.europa.eu/sites/default/files/2024-07/6de6e9b9-0ed9-49cd-985d-c0834b5b4356/Travel%20Rule%20Guidelines.pdf) | 🟢 |
| A8 | Für Self-Hosted-Adressen muss der CASP prüfen, ob der Transfer **≥ €1.000** ist; oberhalb dieser Schwelle sind mindestens eine der folgenden Verifikationsmethoden zu nutzen: (a) unbeaufsichtigte Fernidentifizierung nach den Leitlinien zu Remote Customer Onboarding, (b) — , (c) Senden eines vordefinierten Testbetrags, (d) digitale Signatur einer bestimmten Nachricht mit dem zur Adresse gehörenden Schlüssel. **Das ist eine konkrete, technisch umsetzbare Anforderungsliste für ein zukünftiges Wallet-Ownership-Verification-Modul.** | [EBA PDF](https://www.eba.europa.eu/sites/default/files/2024-07/6de6e9b9-0ed9-49cd-985d-c0834b5b4356/Travel%20Rule%20Guidelines.pdf) | 🟢 |
| A9 | Für CASPs/ICASPs (nicht für klassische Zahlungsdienstleister) soll es eine Übergangsfrist bis **31. Juli 2025** zur Systemanpassung geben. | EBA PDF | 🟡 |

### A.3 AMLR — Verordnung (EU) 2024/1624 (neue EU-AML-Verordnung)

| # | Aussage | Fundstelle | Grad |
|---|---|---|---|
| A10 | Erwägungsgrund 14 der AMLR nimmt Krypto-Dienstleister ausdrücklich als Verpflichtete in den Anwendungsbereich auf, zur Minderung von Geldwäsche-/Terrorismusfinanzierungsrisiken. | [EUR-Lex AMLR](https://eur-lex.europa.eu/eli/reg/2024/1624/oj) | 🟡 |
| A11 | Verpflichtete (inkl. CASPs) müssen Transaktionen mit Self-Hosted-Wallets in ihre **unternehmensweite Risikobewertung** einbeziehen. | EUR-Lex AMLR | 🟡 |
| A12 | Die AMLR verlangt ein **Sanktionslisten-Screening** (targeted financial sanctions) der Kundenbasis gegen benannte Personen/Einrichtungen — **direkte Rechtsgrundlage für genau das, was unser `compliance-service` bereits umsetzt.** | EUR-Lex AMLR | 🟡 |

### A.4 BaFin-Leitfaden (Auslegungs- und Anwendungshinweise „AuA", GwG 2025)

Dies ist die für ein in Deutschland/DACH ausgerichtetes Projekt **wichtigste
Einzelquelle** — die deutsche Aufsicht konkretisiert die EU-Vorgaben:

| # | Aussage | Fundstelle | Grad |
|---|---|---|---|
| A13 | BaFins AuA verpflichtet Krypto-Dienstleister als **auftraggebende** Krypto-Dienstleister, die in Art. 14(1)/(2) TFR spezifizierten Angaben zu übermitteln, und als **begünstigende** Krypto-Dienstleister, den Erhalt dieser Daten sicherzustellen **und zu verifizieren** — einschließlich bei Self-Hosted-Adressen, wo oberhalb von €1.000 geeignete Maßnahmen zur Eigentums-/Kontrollverifikation zu treffen sind. | [BaFin AuA GwG 2025 (PDF)](https://www.bafin.de/SharedDocs/Downloads/EN/Auslegungsentscheidung/dl_ae_auas_gw2025_en.pdf) | 🟡 |
| A14 | BaFin bestätigt die Anwendung der TFR ab 30.12.2024 und verlangt von Verpflichteten (Kreditinstitute, Zahlungsinstitute, E-Geld-Institute, CASPs) interne Verfahren nach **§ 6 Abs. 4a GwG** (in Umsetzung von § 25g Abs. 2 KWG / § 27 Abs. 1 Nr. 4 ZAG). | BaFin AuA GwG 2025 | 🟡 |
| A15 | **§ 15a GwG** verlangt eine gesonderte **verstärkte Sorgfaltspflicht** bei Krypto-Transfers von/zu Self-Hosted-Adressen: Verpflichtete müssen nicht nur das allgemeine Geldwäsche-/Terrorismusfinanzierungsrisiko, sondern konkret das Risiko der **Nichtumsetzung/Umgehung von Sanktionen** (targeted financial sanctions, Proliferationsfinanzierung) ermitteln, bewerten und mindern — u. a. durch Blockchain-Analyse und Kontrollverifikation der Adresse (z. B. Referenztransfer oder signierte Nachricht). **Ein bloßer Wallet-Screenshot genügt hierfür ausdrücklich nicht.** | BaFin AuA GwG 2025 | 🟡 |

**Unmittelbare Konsequenz für die Roadmap:** § 15a GwG + die EBA-Leitlinien
(A8) beschreiben zusammen ein konkretes Feature: ein
**Wallet-Ownership-Verification-Modul** für Self-Hosted-Adressen oberhalb
€1.000 (Testtransfer oder signierte Nachricht), das über das bestehende
Namens-Screening hinausgeht.

**Status (2026-07-15): implementiert.** `compliance-service/app/wallet_ownership/`
bietet beide in A8 genannten Methoden — signierte Herausforderungsnachricht
(sofort einsatzbereit, keine Blockchain-Infrastruktur nötig) und einen
EVM-Testtransfer-Adapter (benötigt eine fremdfinanzierte Sender-Wallet +
RPC-Endpunkt, standardmäßig nicht konfiguriert). Der Schwellenwert (Standard
€1.000) ist über `WALLET_OWNERSHIP_THRESHOLD_EUR` konfigurierbar. Die
signierte-Nachricht-Methode wurde live gegen den laufenden Service verifiziert;
die Testtransfer-Methode ist nur unit-getestet (RPC-Calls gemockt), noch nicht
gegen ein echtes Testnetz validiert. Offen: automatische Anbindung an den
bestehenden Webhook-/Screening-Entscheidungspfad (aktuell ein eigenständig
aufrufbarer Endpunkt, siehe `PROJECT_STATUS.md`).

---

## Teil B — Altersverifikation (18+)

### B.1 DSA Art. 28 + Leitlinien der EU-Kommission (14. Juli 2025)

| # | Aussage | Fundstelle | Grad |
|---|---|---|---|
| B1 | Die EU-Kommission veröffentlichte am **14. Juli 2025** Leitlinien zu Art. 28(1) DSA zum Schutz Minderjähriger, anwendbar auf alle Online-Plattformen, die für Minderjährige zugänglich sind (außer Kleinst-/Kleinunternehmen). | [EU-Kommission](https://digital-strategy.ec.europa.eu/en/library/commission-publishes-guidelines-protection-minors) | 🟡 |
| B2 | **Die Leitlinien der Kommission verweisen ausdrücklich auf das „Age Verification Blueprint" unter ageverification.dev als empfohlenen Ansatz speziell für den Zugang zu Erwachseneninhalten** — neben EU-Digital-Identity-Wallets und Altersschätzung (Age Estimation) für risikoärmere Szenarien. | EU-Kommission | 🟡 |
| B3 | Art. 28(1) DSA verpflichtet Anbieter von für Minderjährige zugänglichen Online-Plattformen zu angemessenen und verhältnismäßigen Maßnahmen für ein hohes Schutzniveau (Privatsphäre, Sicherheit) Minderjähriger. | [eu-digital-services-act.com](https://www.eu-digital-services-act.com/Digital_Services_Act_Article_28.html) | 🟡 |
| B4 | Deutschland setzt Art. 28 DSA über **§§ 24a Abs. 1 und 10a JuSchG** um; **§ 24a Abs. 2 Nr. 3 JuSchG** verlangt konkret technische Mittel zur Altersverifikation für nutzergenerierte audiovisuelle Inhalte. | [Bundestag, Wissenschaftlicher Dienst](https://www.bundestag.de/resource/blob/1108608/WD-8-049-25.pdf) | 🟡 |

**Bedeutung für dieses Projekt:** Punkt B2 ist eine direkte, aktuelle
Bestätigung, dass die **EU Age Verification Solution (ageverification.dev)**
die von der Kommission selbst empfohlene Lösung für genau unseren
Anwendungsfall (Zugang zu Erwachseneninhalten) ist — nicht nur eine
technische Option unter vielen. Das stützt die im Projektplan bereits
getroffene Entscheidung, diese Lösung (statt einer rein proprietären
Alternative wie Zyphe) als primäres Ziel für die spätere
Altersverifikations-Integration zu verfolgen.

### B.2 JMStV (Jugendmedienschutz-Staatsvertrag) — „Geschlossene Benutzergruppe"

| # | Aussage | Fundstelle | Grad |
|---|---|---|---|
| B5 | Nach **§ 4 Abs. 2 Satz 2 JMStV** dürfen relativ unzulässige Angebote (z. B. Pornografie) verbreitet werden, wenn der Anbieter durch eine **geschlossene Benutzergruppe** sicherstellt, dass Kinder/Jugendliche keinen Zugang haben. Nach aktueller KJM-Praxis ist dafür ein **zweistufiges Verfahren** erforderlich: (1) einmalige **Identifizierung mit persönlichem Kontakt** (face-to-face), (2) **Altersverifizierte Zugangsbestätigung bei jeder weiteren Nutzung**. | [Bundestag, Wissenschaftlicher Dienst](https://www.bundestag.de/resource/blob/1108608/WD-8-049-25.pdf) | 🟡 |
| B6 | Eine reine Selbstauskunft (Checkbox-Klick) ist nach JMStV **ausdrücklich nicht ausreichend** — verlangt wird ein robustes, verlässliches Verifikationssystem. Die KJM (Kommission für Jugendmedienschutz) ist die zuständige Aufsichtsbehörde. | [avpassociation.com](https://avpassociation.com/germany/) | 🟡 |

**Bedeutung für dieses Projekt:** Punkt B5 ist die konkreteste, am direktesten
umsetzbare Anforderung im gesamten Altersverifikations-Teil. Sie beschreibt
exakt zwei technische Schritte, die ein Altersverifikationsmodul abbilden
muss — eine einmalige, stärkere Identifizierung und danach eine leichtgewichtige,
aber verifizierte Zugangsbestätigung pro Sitzung/Nutzung. Das deckt sich im
Prinzip mit dem Zero-Knowledge-Proof-Modell der EU Age Verification Solution
(einmaliger Ausweisabgleich, danach nur noch ein Ja/Nein-Nachweis), sollte
aber **konkret gegen § 4 Abs. 2 JMStV und die aktuelle KJM-Prüfpraxis**
abgeglichen werden, bevor eine Implementierung als JMStV-konform bezeichnet
wird.

### B.3 GlüStV (Glücksspielstaatsvertrag) — Online-Glücksspiel/Casino

🔴 **Nicht recherchiert.** Die entsprechende Such-Anfrage ist in dieser
Recherche-Runde technisch fehlgeschlagen (Verbindungsabbruch), bevor
überhaupt Quellen gefunden wurden. Es liegen **keine** belastbaren Angaben
zu GlüStV-Vorschriften (Registrierung, OASIS-Sperrdatei, LUGAS-Limits,
Identitätsprüfung vor Echtgeld-Einsatz) vor. Da der Nutzer explizit
Casino/Glücksspiel als weiteren Anwendungsfall für die Altersverifikation
genannt hat, ist das der **wichtigste offene Punkt** für die nächste
Recherche-Runde — konkret zu klären:

- Welcher Paragraph des GlüStV 2021 verlangt Identitätsprüfung vor
  Echtgeld-Spiel, und welcher Standard wird dafür verlangt (reicht die
  EU Age Verification Solution / ein KJM-ähnliches Verfahren, oder ist ein
  eigenes, glücksspielrechtlich akkreditiertes Verfahren nötig)?
- Wie funktioniert die Anbindung an OASIS (Spielersperrsystem) und LUGAS
  (Limitsystem) technisch — gibt es eine offene/dokumentierte Schnittstelle?
- Gilt das GlüStV-Regime **zusätzlich zu** oder **statt** JMStV/DSA Art. 28
  für Glücksspielanbieter?

---

## Rückschlüsse für die Roadmap

1. **Das Sanktions-Screening (bereits gebaut) hat jetzt eine explizite
   Rechtsgrundlage**, nicht nur eine plausible Annahme: TFR Art. 14 i. V. m.
   AMLR (targeted financial sanctions screening) und BaFins § 15a GwG.
2. **Wallet-Ownership-Verification für Self-Hosted-Adressen oberhalb €1.000
   ist implementiert** (`app/wallet_ownership/`, signierte Nachricht + EVM-
   Testtransfer) — siehe Detailstatus in Teil A.4 und `PROJECT_STATUS.md`.
   Offen bleibt die automatische Anbindung an den Webhook-/Screening-Pfad.
3. **Die Wahl der EU Age Verification Solution als Zielarchitektur für die
   Altersverifikation ist durch die Kommissions-Leitlinien vom 14.07.2025
   bestätigt** (nicht nur eine von mehreren Optionen).
4. **JMStV §4 Abs. 2 liefert das konkreteste technische Lastenheft** für ein
   Altersverifikationsmodul: einmalige Identifizierung + wiederkehrende
   verifizierte Zugangsbestätigung.
5. **GlüStV/Glücksspiel ist komplett offen** — vor jeder Aussage zu
   „Einsatz im Online-Casino" muss diese Lücke geschlossen werden.
6. ~~Der Punkt A5 (⚠️ widersprüchlich)~~ **A5 ist geklärt** (2026-07-17,
   siehe Tabelle oben): Art. 2(4) enthält zwei getrennte „(a)"-Ausschlusslisten
   (Geld vs. Krypto) im selben Absatz — daraus resultierte der scheinbare
   Widerspruch. Der krypto-spezifische Ausschluss ist real, aber eng gefasst
   (nur CASP-zu-CASP „on their own behalf", nicht kundenveranlasste
   Transfers) und betrifft den aktuellen Envoy-Demo-Flow nicht. Nebenbefund:
   A4 enthielt eine falsche Oder-Verknüpfung der Auftraggeberfelder — jetzt
   korrigiert. Offener Folgepunkt: prüfen, ob `screening/decision.py` die
   präzise Bündel-Logik aus Art. 14(1)(d) (Adresse+Land+Dokumentnummer+
   Kundennummer **oder** Geburtsdatum/-ort, nicht freie Einzelfeld-Alternative)
   tatsächlich so validiert, statt nur „irgendein Feld vorhanden".

---

*Letzte Aktualisierung: 2026-07-17. A5 und A4 gegen den konsolidierten
EUR-Lex-Volltext von VO (EU) 2023/1113 geprüft und korrigiert/bestätigt
(🟢). Nächster Recherche-Schritt: GlüStV-Vorschriften gezielt
nachrecherchieren; prüfen, ob die Art.-14(1)(d)-Bündel-Logik im
Screening-Code korrekt abgebildet ist.*
