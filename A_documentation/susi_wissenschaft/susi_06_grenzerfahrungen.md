# 06 — Grenzerfahrungen
### SUSI Entwicklungsbericht · Stand Juni 2026

---

## Was dieses Kapitel ist

Dieser Bericht ist kein Portfolio-Stück das nur Erfolge dokumentiert. Grenzerfahrungen gehören dazu — Punkte wo das System gegen eigene Annahmen, technische Grenzen oder konzeptuelle Fehler gelaufen ist. Die folgenden Punkte kamen im Rahmen eines technischen Reviews durch externe ML-Tutoren ans Licht. Sie werden hier nicht als Randnotizen behandelt sondern als vollwertige Erkenntnisse — weil sie das Design zukünftiger Versionen direkt beeinflussen.

---

## Grenzerfahrung 1 — Undokumentierte Score-Skala in der Evaluation

**Was passiert ist:** Die Evaluierungsläufe verwendeten eine 0–5-Skala die nie explizit dokumentiert war. Der Auto-Scorer vergibt Scores 0–5 mit präziser Bedeutung pro Stufe — 0 Ausweichantwort, 1 Halluzination, 2 Training korrekt, 3 RAG korrekt, 4 Generation-Problem, 5 falscher Chunk. Im Bericht stand aber durchgehend "0–2-Skala" und Mittelwerte wie "2.74 / 2.0" — mathematisch unmöglich wenn das Maximum 2 ist.

**Warum das passiert ist:** Die Score-Skala des Auto-Scorers wurde iterativ weiterentwickelt aber nie als explizite Konstante in `config.yaml` oder `evaluator.py` verankert. Verschiedene Läufe liefen mit verschiedenen Versionen des Auto-Scorers — ohne dass die CSVs diese Information als Metadaten trugen. Beim manuellen Auswerten wurde intuitiv bewertet ohne die Skala jedes Mal neu nachzuschauen.

**Was das bedeutet:** Die Korrektheitsprozente waren trotzdem vergleichbar weil `Score ≥ 2` als Schwellenwert über alle Läufe konsistent ist — aber die Durchschnittswerte waren nicht normiert und damit irreführend. Nach externer Prüfung wurden alle historischen Tabellen auf normierte Werte (÷ 3) umgestellt und die Score-Skala vollständig dokumentiert.

**Die Lektion:** Metriken-Definitionen gehören in den Code als Konstanten — nicht in die Dokumentation als Prosa. `MAX_SCORE = 5` und `KORREKT_THRESHOLD = 2` müssen in `evaluator.py` stehen und in jeder CSV als Metadaten-Spalten erscheinen. Jeder Lauf muss selbsterklärend sein ohne Kontextwissen über die verwendete Scorer-Version.

---

## Grenzerfahrung 2 — Die deutsche Sprachbarriere beim Cross-Encoder

**Was passiert ist:** Im Architekturentwurf für den automatisierten Türsteher (Stufe 2 des 3-stufigen Speichermodells) wurde `cross-encoder/nli-deberta-v3-base` als bevorzugtes Modell geplant. Das Modell ist leichtgewichtig, schnell, läuft auf CPU — scheinbar ideal.

**Das Problem:** DeBERTa-NLI-Modelle aus der Standardbibliothek sind auf englischen MNLI-Korpora trainiert. Bei deutschen Eingaben — deutschen SUSIpedia-Chunks und deutschen LLM-Zusammenfassungen — fällt die Precision drastisch. Das Modell erkennt semantische Abweichungen zwischen deutschem Quelltext und deutschem Entwurf nicht zuverlässig. In der Praxis bedeutet das: halluzinierter deutscher Text wird als "korrekt abgeleitet" eingestuft. Der Hauptzweck des Türstehers — Schutz vor Self-Poisoning — funktioniert nicht.

**Warum das übersehen wurde:** Der erste Entwurf war konzeptuell — er hat die Existenz geeigneter Modelle bestätigt aber nicht die Sprachkompatibilität gecheckt. "Cross-Encoder für NLI" klingt generisch; dass die Trainingsdaten entscheidend sind wurde nicht früh genug als Risiko erkannt.

**Die Lösung:** Für deutschsprachige SUSIpedia-Inhalte ist ein mehrsprachiges oder deutsch-optimiertes Modell erforderlich. Kandidaten: `Sahajpreet/german-deberta-v3-base-xnli` oder `amberoad/bert-multilingual-passage-reranking-msmarco`. Vor der Implementierung wird ein Smoke-Test mit bekannten deutschen Halluzinations-Beispielen durchgeführt um die tatsächliche Detection-Rate zu messen.

**Die Lektion:** Sprachkompatibilität ist eine funktionale Anforderung. Bei jedem NLP-Modell das in SUSI eingesetzt wird muss explizit geprüft werden: auf welcher Sprache wurde trainiert, und welche Sprache verarbeitet SUSI?

---

## Grenzerfahrung 3 — Der VRAM-Modellwechsel-Deadlock

**Was passiert ist:** Das 3-stufige Speichermodell sieht vor dass auf `!save` das Chat-Modell (qwen2.5-coder:7b) kurz durch ein Zusammenfassungs-Modell (llama3.1:8b) ersetzt wird. In der Theorie klingt das nach einem eleganten spezialisierten Workflow. In der Praxis entsteht ein potenzieller Deadlock.

Ollama lädt ein Modell vollständig in den VRAM und entlädt es nur auf expliziten Befehl oder bei Timeout. Der Wechsel von qwen2.5-coder auf llama3.1 — und zurück — dauert auf der RTX 3090 zwischen 5 und 15 Sekunden. Wenn dieser Wechsel synchron im Request-Response-Zyklus passiert friert das HTMX-Frontend ein. Der Nutzer sieht kein Feedback, Requests hängen in der Queue.

**Warum das lösbar ist:** `!save` wird selten ausgelöst — realistisch zwei bis drei Mal pro Tag, nicht nach jedem Chat. Das rechtfertigt keinen dauerhaft laufenden Worker, aber es macht einen einfachen asynchronen Background-Task sinnvoll. Der `!save`-Befehl gibt sofort eine Statusmeldung zurück, der Task läuft im Hintergrund, `OLLAMA_MAX_LOADED_MODELS=1` verhindert dass beide Modelle gleichzeitig VRAM belegen.

**Die Lektion:** Jede Operation die Ollama-Modelle wechselt ist eine potenzielle Blockade. Das Muster "seltener Trigger → async Task → Statusfeedback ans Frontend" ist die richtige Antwort — nicht ein komplexer permanenter Worker.

*→ Implementierungsplan: [susi_07_roadmap.md — Phase 1](susi_07_roadmap.md)*

---

## Grenzerfahrung 4 — Das Tabellen-Verbot war zu radikal

**Was passiert ist:** Die SUSIpedia-Formatierungsregeln verbieten Tabellen vollständig. Die Begründung war korrekt: Tabellen-Zellen sind kurze, kontextfreie Fragmente die schlecht chunken und noch schlechter retrieven. Ein Chunk der nur `| 0.671 | 0.126 |` enthält liefert keinen semantischen Vektor.

**Das übersehene Problem:** Strukturierte Daten — Konfigurationsparameter, API-Antwortformate, Enum-Definitionen, Score-Tabellen — lassen sich in Fließtext zwingen, aber dabei verlieren sie Präzision und Lesbarkeit. Ein LLM das auf einen Chunk mit "Die Konfiguration besteht aus chunk_size mit dem Wert 1000 und overlap mit dem Wert 50 und top_k mit dem Wert 5..." trifft ist schlechter bedient als eines das einen validen YAML-Block findet.

**Die Lösung:** Das Verbot wird präzisiert. Markdown-Tabellen bleiben verboten. Erlaubt sind JSON- und YAML-Codeblöcke für echte strukturierte Daten. Bedingung: jeder Codeblock muss von einem H2-Ankersatz umgeben sein der den Inhalt in Prosa beschreibt. Das Embedding-Modell greift die Prosa für Retrieval, das LLM greift den Codeblock für Generierung. Beide bekommen was sie brauchen.

**Die Lektion:** Formatierungsregeln brauchen eine explizite Begründung warum eine Struktur verboten ist — nicht nur das Verbot selbst. Wenn die Begründung klar ist ergibt sich die Ausnahme logisch daraus.

---

## Was die Grenzerfahrungen gemeinsam haben

Alle vier Punkte teilen ein Muster: eine Entscheidung, die auf einem gültigen Prinzip basierte, hat einen blinden Fleck in der Umsetzung. Skalen-Konsistenz war kein Gedanke wert weil die Evaluation "ja funktioniert". DeBERTa war kein Gedanke wert weil "Cross-Encoder für NLI" ausreichend spezifisch klang. Modellwechsel waren kein Gedanke wert weil das Konzept stimmte.

Das externe Review hat diese blinden Flecken sichtbar gemacht. Das ist der Wert eines zweiten Augenpaars — nicht weil die eigene Analyse falsch war, sondern weil Implizites explizit wird.

**Status der Auto-Save-Pipeline (Stand Juni 2026):** Der Code ist noch aktiv in `query.py` — er wurde nicht entfernt weil das Prinzip "kein Abriss ohne Ersatz" gilt. Die 3-Stufen-Architektur befindet sich in der durch Grenzerfahrung 2 und 3 informierten Planungsphase. Sobald der asynchrone Background-Task und der mehrsprachige NLI-Türsteher implementiert sind wird die alte Pipeline deaktiviert. Bis dahin läuft die alte Auto-Save-Pipeline noch aktiv — sie wird bewusst selten und nur bei eindeutig korrekten Antworten ausgelöst.

*→ Implementierungsplan: [susi_07_roadmap.md — Phase 2](susi_07_roadmap.md)*

---

*→ Zurück zur Übersicht: [susi_00_uebersicht.md](susi_00_uebersicht.md)*  
*→ Weiter: [susi_07_roadmap.md](susi_07_roadmap.md)*  
*Stand: Juni 2026 · Martin Freimuth*