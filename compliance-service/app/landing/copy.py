"""Landing-page copy, EN and DE. One template, two dictionaries."""

EN = {
    "lang": "en",
    "title": "AML+18 – AI compliance officer for crypto and fintech",
    "desc": "Screen customers, wallets and incoming transfers against official sanctions lists. An AI agent explains every decision and never acts outside the policy you set. Open source.",
    "nav": {"how": "How it works", "plans": "Pricing", "docs": "Docs", "faq": "FAQ", "cta": "Start a pilot"},
    "hero": {
        "pill": "Open source · EU & US · pilot programme open",
        "h1": "An AI compliance officer that <em>explains</em> every decision.",
        "lead": "Screen customers, wallet addresses and incoming transfers against 8 official sanctions lists. "
                "The agent reviews each transfer, writes down why, and can never act outside the limits you set.",
        "cta1": "Start a free pilot", "cta2": "Read the integration guide", "cta3": "Ask the assistant",
        "hint": "Move your cursor: the red nodes are sanctioned wallets inside a transfer network.",
    },
    "how": {
        "eyebrow": "How it works",
        "h2": "You call our API. We answer with a decision and the reasons.",
        "sub": "No access to your systems, no data migration. Your developers add one HTTPS call where a customer is onboarded or a transfer arrives.",
        "boxes": [
            ("Your product", "A deposit arrives or a customer signs up. Your backend sends us the name, wallet address or transfer details."),
            ("AML+18", "Sanctions lists, address match, on-chain check, then the AI agent reviews and writes the explanation."),
            ("Your decision", "You get accepted, review or rejected, with reasons. Release, hold or reject in your own system, or let us signal it."),
        ],
    },
    "path": {
        "eyebrow": "Your integration path",
        "h2": "From signup to first screened transfer in an afternoon.",
        "sub": "Most companies only need steps 1 to 3. Steps 4 and 5 are optional and can wait.",
        "steps": [
            ("you", "You", "Register a project", "Name, contact email, optional webhook URL. You receive an API key, shown once. On the hosted service we activate new projects after a quick review."),
            ("you", "You", "Call the API from your backend", "<code>Authorization: Bearer &lt;key&gt;</code> on every request. Screen a name, a wallet address, or send an incoming transfer to the agent."),
            ("us", "Us", "Act on the decision", "Every answer is accepted, review or rejected, with the matched list entry and a plain-language explanation. You decide what your system does."),
            ("opt", "Optional", "Open the compliance dashboard", "Create an owner account (password + authenticator app) to read explanations, approve held cases, set policy and download reports."),
            ("opt", "Optional", "Let the agent act (OPERATE mode)", "Give us one webhook URL. With your explicit consent the agent sends signed release / hold / reject instructions, inside your limits. A kill switch reverts at once."),
        ],
        "foot": "You never give us access to your systems or your own API. We only ever call one URL, and only if you switch OPERATE on.",
    },
    "demo": {
        "eyebrow": "See the answer",
        "h2": "Real response format, real sanctions data.",
        "sub": "Two calls to the screening API. The first wallet is not listed, the second is an address published by OFAC.",
        "tab1": "Ordinary wallet", "tab2": "Sanctioned wallet", "label": "Example response",
        "ok": "No match. Your system can proceed.", "bad": "Exact match on an OFAC-listed address. A human decides; never released automatically.",
    },
    "inside": {
        "eyebrow": "What is inside", "h2": "Everything a small team needs, nothing it has to build.",
        "cards": [
            ("Sanctions screening", "OFAC, EU, UN, UK, Switzerland, Canada and Australia lists, refreshed daily. Handles reordered names, transliteration and aliases."),
            ("Wallet address check", "Exact match against addresses published in OFAC entries, for the currencies OFAC lists, such as Bitcoin, Ethereum and Tron."),
            ("AI compliance agent", "Reviews each incoming transfer, verifies the funds on-chain, classifies and explains. It can only raise caution, never lower it."),
            ("Policy and kill switch", "Limits, allowed assets and chains, blocked countries. Sanctions hits are always handled by a human. One click back to monitor-only."),
            ("Tamper-evident journal", "Every decision is hash-chained and append-only. Edits or deletions are detected and shown in the dashboard."),
            ("Age, wallet proof and Travel Rule", "18+ verification for gambling and adult services, proof that a customer controls a wallet, and Travel Rule messaging through the open-source TRISA Envoy node."),
        ],
    },
    "trust": {
        "eyebrow": "Why you can trust an AI here", "h2": "The model advises. Plain code decides.",
        "sub": "Between the model and any action sit a deterministic sanctions floor and a policy engine written as ordinary code. Counterparty text is treated as untrusted data, so a malicious memo cannot instruct the agent. The agent holds no keys and cannot move funds.",
        "pts": ["Fails closed: no model answer means a human reviews", "Open source (MIT): read every rule", "Self-host any time with the same API"],
    },
    "plans": {
        "eyebrow": "Pricing", "h2": "Free during the pilot. Simple plans after.",
        "sub": "We are looking for a handful of design partners. Indicative plans below; final prices are set with pilot feedback.",
        "note": "Indicative pricing, not final. Pilot partners keep favourable terms. Self-hosting is free forever.",
        "items": [
            {"name": "Pilot", "price": "Free", "per": "design partners", "hot": False, "cta": "Apply for a pilot", "feat": [
                "Screening and wallet checks", "AI agent in MONITOR mode", "Compliance dashboard", "Direct support from the founder", ("OPERATE mode", False)]},
            {"name": "Starter", "price": "from €49", "per": "/ month", "hot": False, "cta": "Join the waitlist", "feat": [
                "Fixed monthly volume", "AI agent in MONITOR mode", "Compliance dashboard and reports", "Daily email digest", ("OPERATE mode", False)]},
            {"name": "Growth", "price": "from €199", "per": "/ month", "hot": True, "cta": "Join the waitlist", "feat": [
                "Higher volume", "OPERATE mode with signed webhooks", "Policy engine and kill switch", "Priority support", "Custom jurisdiction profile"]},
            {"name": "Self-hosted", "price": "Free", "per": "MIT licence", "hot": False, "cta": "View on GitHub", "feat": [
                "Run it on your own servers", "Same API as the hosted service", "Optional paid support and SLA", "Move between hosted and self-hosted"]},
        ],
    },
    "faq": {
        "eyebrow": "FAQ", "h2": "Questions we hear first",
        "items": [
            ("Do I give you access to my API or my systems?", "No. Your developers call our API with a key. You send us only the data of the person or transfer to check. The one thing we may call is a single webhook URL you provide, and only if you enable OPERATE mode."),
            ("Does the AI make the final call?", "No. The model can raise caution but never lower it. Sanctions matches always go to a human, and every action passes a policy engine written as ordinary code."),
            ("Is this legal advice or a certified product?", "No. It is early open-source software with a pilot programme: testnet and mock ledger only for on-chain checks, no mainnet, no certification. Reporting duties are not encoded and legal texts are marked for counsel review."),
            ("Where does the data live?", "On the hosted service in an EU data centre (Frankfurt). Or run it yourself: it is MIT licensed."),
            ("What does a pilot involve?", "Free access in exchange for honest feedback and a short call every two weeks. You can stop at any time."),
        ],
    },
    "final": {"h2": "Be one of the first design partners.", "sub": "Free during the pilot. Tell us how you handle sanctions screening today and we will help you connect.", "cta": "Start a free pilot", "cta2": "Ask the assistant"},
    "footer": {"l": "AML+18, open source (MIT). Not legal advice.", "links": [("Docs", "/docs/"), ("GitHub", "https://github.com/pilipandr770/AML-18"), ("Developer portal", "/developer/")]},
    "chat": {"title": "Ask about AML+18", "sub": "AI assistant", "hello": "Hi! I can explain how AML+18 works and how your developers connect it. What would you like to know?",
             "ph": "Ask a question…", "send": "Send",
             "chips": ["How do we connect?", "Do you need access to our API?", "What does it cost?", "What does the agent do?"]},
    "code_ok": '{\n  "listed": false,\n  "decision": "accepted",\n  "matches": []\n}',
    "code_bad": '{\n  "listed": true,\n  "decision": "rejected",\n  "matches": [{\n    "address": "0x8576acc5…353c",\n    "currency": "ETH",\n    "source": "OFAC_SDN",\n    "programs": ["CYBER2", "ELECTION-EO13848"]\n  }]\n}',
}

DE = {
    "lang": "de",
    "title": "AML+18 – KI-Compliance-Officer für Krypto und Fintech",
    "desc": "Kunden, Wallets und eingehende Transfers gegen offizielle Sanktionslisten prüfen. Ein KI-Agent erklärt jede Entscheidung und handelt nie außerhalb Ihrer Regeln. Open Source.",
    "nav": {"how": "So funktioniert's", "plans": "Preise", "docs": "Doku", "faq": "FAQ", "cta": "Pilot starten"},
    "hero": {
        "pill": "Open Source · EU & USA · Pilotprogramm offen",
        "h1": "Ein KI-Compliance-Officer, der jede Entscheidung <em>begründet</em>.",
        "lead": "Kunden, Wallet-Adressen und eingehende Transfers gegen 8 offizielle Sanktionslisten prüfen. "
                "Der Agent bewertet jeden Transfer, hält die Gründe fest und kann nie außerhalb Ihrer Grenzen handeln.",
        "cta1": "Kostenlosen Pilot starten", "cta2": "Integrationsleitfaden lesen", "cta3": "Assistent fragen",
        "hint": "Bewegen Sie den Cursor: Rote Knoten sind sanktionierte Wallets in einem Transfer-Netzwerk.",
    },
    "how": {
        "eyebrow": "So funktioniert's",
        "h2": "Sie rufen unsere API auf. Wir antworten mit Entscheidung und Begründung.",
        "sub": "Kein Zugriff auf Ihre Systeme, keine Datenmigration. Ihre Entwickler fügen einen HTTPS-Aufruf dort ein, wo ein Kunde angelegt wird oder ein Transfer eingeht.",
        "boxes": [
            ("Ihr Produkt", "Eine Einzahlung kommt an oder ein Kunde registriert sich. Ihr Backend sendet uns Name, Wallet-Adresse oder Transferdaten."),
            ("AML+18", "Sanktionslisten, Adressabgleich, On-Chain-Prüfung, dann bewertet der KI-Agent und schreibt die Begründung."),
            ("Ihre Entscheidung", "Sie erhalten accepted, review oder rejected samt Gründen. Freigeben, halten oder ablehnen in Ihrem System, oder wir signalisieren es."),
        ],
    },
    "path": {
        "eyebrow": "Ihr Integrationsweg",
        "h2": "Von der Anmeldung zum ersten geprüften Transfer an einem Nachmittag.",
        "sub": "Die meisten Unternehmen brauchen nur die Schritte 1 bis 3. Schritt 4 und 5 sind optional.",
        "steps": [
            ("you", "Sie", "Projekt registrieren", "Name, Kontakt-E-Mail, optional Webhook-URL. Sie erhalten einen API-Schlüssel, einmalig angezeigt. Im gehosteten Dienst schalten wir neue Projekte nach kurzer Prüfung frei."),
            ("you", "Sie", "API aus Ihrem Backend aufrufen", "<code>Authorization: Bearer &lt;key&gt;</code> bei jeder Anfrage. Einen Namen oder eine Wallet-Adresse prüfen oder einen eingehenden Transfer an den Agenten senden."),
            ("us", "Wir", "Auf die Entscheidung reagieren", "Jede Antwort ist accepted, review oder rejected, mit Treffer in der Liste und Erklärung in Klartext. Was Ihr System daraus macht, entscheiden Sie."),
            ("opt", "Optional", "Compliance-Dashboard öffnen", "Owner-Konto anlegen (Passwort + Authenticator-App), um Begründungen zu lesen, gehaltene Fälle freizugeben, Regeln zu setzen und Berichte zu laden."),
            ("opt", "Optional", "Agent handeln lassen (OPERATE-Modus)", "Geben Sie uns eine Webhook-URL. Mit Ihrer ausdrücklichen Zustimmung sendet der Agent signierte Freigabe-/Halte-/Ablehnungs-Anweisungen innerhalb Ihrer Grenzen. Ein Kill-Switch stoppt sofort."),
        ],
        "foot": "Sie geben uns nie Zugriff auf Ihre Systeme oder Ihre eigene API. Wir rufen höchstens eine URL auf, und nur wenn Sie OPERATE einschalten.",
    },
    "demo": {
        "eyebrow": "Die Antwort ansehen",
        "h2": "Echtes Antwortformat, echte Sanktionsdaten.",
        "sub": "Zwei Aufrufe der Screening-API. Die erste Wallet ist nicht gelistet, die zweite ist eine von OFAC veröffentlichte Adresse.",
        "tab1": "Normale Wallet", "tab2": "Sanktionierte Wallet", "label": "Beispielantwort",
        "ok": "Kein Treffer. Ihr System kann fortfahren.", "bad": "Exakter Treffer auf eine OFAC-Adresse. Ein Mensch entscheidet; nie automatische Freigabe.",
    },
    "inside": {
        "eyebrow": "Was drin ist", "h2": "Alles, was ein kleines Team braucht, ohne es selbst zu bauen.",
        "cards": [
            ("Sanktions-Screening", "Listen von OFAC, EU, UN, UK, Schweiz, Kanada und Australien, täglich aktualisiert. Erkennt vertauschte Namen, Transliteration und Aliase."),
            ("Wallet-Adressprüfung", "Exakter Abgleich mit in OFAC-Einträgen veröffentlichten Adressen, für die von OFAC gelisteten Währungen, etwa Bitcoin, Ethereum und Tron."),
            ("KI-Compliance-Agent", "Bewertet jeden eingehenden Transfer, prüft die Mittel on-chain, klassifiziert und erklärt. Er kann Vorsicht nur erhöhen, nie senken."),
            ("Regeln und Kill-Switch", "Limits, erlaubte Assets und Chains, gesperrte Länder. Sanktionstreffer prüft immer ein Mensch. Ein Klick zurück in den reinen Beobachtungsmodus."),
            ("Manipulationssicheres Journal", "Jede Entscheidung ist hash-verkettet und nur anfügbar. Änderungen oder Löschungen werden erkannt und im Dashboard angezeigt."),
            ("Alter, Wallet-Nachweis und Travel Rule", "18+-Verifikation für Glücksspiel und Erwachsenenangebote, Nachweis der Wallet-Kontrolle und Travel-Rule-Nachrichten über den Open-Source-Knoten TRISA Envoy."),
        ],
    },
    "trust": {
        "eyebrow": "Warum man hier einer KI vertrauen kann", "h2": "Das Modell berät. Normaler Code entscheidet.",
        "sub": "Zwischen Modell und jeder Aktion liegen eine deterministische Sanktions-Untergrenze und eine als gewöhnlicher Code geschriebene Regel-Engine. Text von Gegenparteien gilt als nicht vertrauenswürdig, ein bösartiger Verwendungszweck kann den Agenten nicht anweisen. Der Agent besitzt keine Schlüssel und bewegt keine Gelder.",
        "pts": ["Fail-closed: ohne Modellantwort prüft ein Mensch", "Open Source (MIT): jede Regel lesbar", "Jederzeit selbst hosten, gleiche API"],
    },
    "plans": {
        "eyebrow": "Preise", "h2": "Im Pilot kostenlos. Danach einfache Pläne.",
        "sub": "Wir suchen eine Handvoll Design-Partner. Unverbindliche Pläne unten; endgültige Preise legen wir mit dem Pilot-Feedback fest.",
        "note": "Unverbindliche Preise. Pilotpartner behalten günstige Konditionen. Selbst hosten bleibt dauerhaft kostenlos.",
        "items": [
            {"name": "Pilot", "price": "Kostenlos", "per": "Design-Partner", "hot": False, "cta": "Für Pilot bewerben", "feat": [
                "Screening und Wallet-Prüfung", "KI-Agent im MONITOR-Modus", "Compliance-Dashboard", "Direkter Support vom Gründer", ("OPERATE-Modus", False)]},
            {"name": "Starter", "price": "ab 49 €", "per": "/ Monat", "hot": False, "cta": "Auf die Warteliste", "feat": [
                "Festes Monatsvolumen", "KI-Agent im MONITOR-Modus", "Dashboard und Berichte", "Täglicher E-Mail-Digest", ("OPERATE-Modus", False)]},
            {"name": "Growth", "price": "ab 199 €", "per": "/ Monat", "hot": True, "cta": "Auf die Warteliste", "feat": [
                "Höheres Volumen", "OPERATE-Modus mit signierten Webhooks", "Regel-Engine und Kill-Switch", "Prioritäts-Support", "Eigenes Jurisdiktionsprofil"]},
            {"name": "Selbst gehostet", "price": "Kostenlos", "per": "MIT-Lizenz", "hot": False, "cta": "Auf GitHub ansehen", "feat": [
                "Auf Ihren eigenen Servern", "Gleiche API wie der gehostete Dienst", "Optional bezahlter Support mit SLA", "Wechsel zwischen gehostet und selbst gehostet"]},
        ],
    },
    "faq": {
        "eyebrow": "FAQ", "h2": "Die häufigsten Fragen",
        "items": [
            ("Geben wir Ihnen Zugriff auf unsere API oder Systeme?", "Nein. Ihre Entwickler rufen unsere API mit einem Schlüssel auf. Sie senden uns nur die Daten der zu prüfenden Person oder des Transfers. Aufrufen dürfen wir höchstens eine von Ihnen genannte Webhook-URL, und nur wenn Sie den OPERATE-Modus aktivieren."),
            ("Trifft die KI die endgültige Entscheidung?", "Nein. Das Modell kann Vorsicht nur erhöhen. Sanktionstreffer gehen immer an einen Menschen, und jede Aktion durchläuft eine als gewöhnlicher Code geschriebene Regel-Engine."),
            ("Ist das Rechtsberatung oder ein zertifiziertes Produkt?", "Nein. Es ist frühe Open-Source-Software im Pilotprogramm: On-Chain-Prüfung nur auf Testnet und Mock-Ledger, kein Mainnet, keine Zertifizierung. Meldepflichten sind nicht abgebildet, juristische Texte sind zur Prüfung durch Rechtsbeistand markiert."),
            ("Wo liegen die Daten?", "Im gehosteten Dienst in einem EU-Rechenzentrum (Frankfurt). Oder selbst betreiben: MIT-lizenziert."),
            ("Was beinhaltet der Pilot?", "Kostenloser Zugang gegen ehrliches Feedback und ein kurzes Gespräch alle zwei Wochen. Sie können jederzeit aufhören."),
        ],
    },
    "final": {"h2": "Seien Sie einer der ersten Design-Partner.", "sub": "Im Pilot kostenlos. Erzählen Sie uns, wie Sie Sanktionsprüfung heute handhaben, wir helfen beim Anbinden.", "cta": "Kostenlosen Pilot starten", "cta2": "Assistent fragen"},
    "footer": {"l": "AML+18, Open Source (MIT). Keine Rechtsberatung.", "links": [("Doku", "/docs/"), ("GitHub", "https://github.com/pilipandr770/AML-18"), ("Entwicklerportal", "/developer/")]},
    "chat": {"title": "Fragen zu AML+18", "sub": "KI-Assistent", "hello": "Hallo! Ich erkläre, wie AML+18 funktioniert und wie Ihre Entwickler es anbinden. Was möchten Sie wissen?",
             "ph": "Frage stellen…", "send": "Senden",
             "chips": ["Wie binden wir an?", "Brauchen Sie Zugriff auf unsere API?", "Was kostet es?", "Was macht der Agent?"]},
    "code_ok": '{\n  "listed": false,\n  "decision": "accepted",\n  "matches": []\n}',
    "code_bad": '{\n  "listed": true,\n  "decision": "rejected",\n  "matches": [{\n    "address": "0x8576acc5…353c",\n    "currency": "ETH",\n    "source": "OFAC_SDN",\n    "programs": ["CYBER2", "ELECTION-EO13848"]\n  }]\n}',
}

COPY = {"en": EN, "de": DE}
