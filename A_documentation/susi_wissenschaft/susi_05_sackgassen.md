# 05 — Sackgassen und neue Architektur
### SUSI Entwicklungsbericht · Stand Juli 2026

---

## Vom Experiment zur bewussten Entscheidung

Ein Entwicklungsprozess, der keine Sackgassen kennt, ist kein ehrlicher Entwicklungsprozess. Die folgenden vier Ansätze wurden konzipiert, implementiert — und nach systematischer Analyse bewusst verworfen. Jede verworfene Idee hat das System besser gemacht als jede die von Anfang an funktioniert hat, weil sie das Verständnis für die eigentlichen Risiken geschärft hat.

Der Auslöser für die kritische Analyse war das formale Evaluierungsframework. Erst als Zahlen auf dem Tisch lagen wurde sichtbar was intuitiv nicht erkennbar war: ein System das sich selbst vergiftet produziert keine offensichtlichen Fehler — es produziert plausibel klingende falsche Antworten.

---

## Sackgasse A — Die vollautomatisierte Auto-Save-Pipeline *(Self-Poisoning)*

**Zeitraum:** März – Mai 2026  
**Status:** Deaktiviert (Mai 2026)

**Der Ansatz:** SUSI sollte über einen regelbasierten Filter (`worth_saving()`) und eine LLM-Selbstevaluation (`susi_evaluates()`) eigenständig entscheiden wann eine Konversation als Markdown in die SUSIpedia zurückgeschrieben wird. Der Keyword-Router (`TOPIC_KEYWORDS`) schlug den Zielordner vor, `create_summary()` erstellte die Zusammenfassung, `save_to_susipedia()` schrieb die Datei und rief `ingest.py` automatisch auf.

Das System war vollständig implementiert und lief produktiv. Es fühlte sich nach echter KI an — SUSI lernt aus Gesprächen.

**Warum verworfen — Das Self-Poisoning-Problem:** Wenn das Chat-Modell halluziniert schreibt es seine eigenen Fehler unbemerkt ins Langzeitgedächtnis zurück. Beim nächsten Mal findet das Retrieval diesen falschen Chunk und das LLM bestätigt die Fehlinformation mit noch mehr Überzeugung. Eine zerstörerische Feedback-Schleife, die sich selbst verstärkt.

**Warum verworfen — Die Redundanz-Falle:** Wenn SUSI eine Frage korrekt beantwortet würde eine reine Automatik diese Antwort erneut speichern. Das erzeugt massive Daten-Duplikate im Vektorraum. Doppelte Chunks für denselben Inhalt verzerren die Similarity Scores und zerstören die Retrieval-Präzision durch Kontext-Mixing — exakt das Problem das bei `simulate_top_n_hg.md` manuell entdeckt und behoben wurde.

**Die entscheidende Erkenntnis:** Die Pipeline wurde im Mai 2026 deaktiviert. Die neue 3-Stufen-Architektur 
(siehe unten) ist in Planung (Q3 2026). Der dafür vorgesehene Cross-Encoder 
ist mit bge-reranker-v2-m3 (97% Korrektheit) bereits im Produktivbetrieb.

→ *Reranker-Evolution: [susi_08_produktivbetrieb.md](susi_08_produktivbetrieb.md)*

---

## Sackgasse B — Konsolidierung durch dasselbe LLM

**Zeitraum:** April 2026  
**Status:** Verworfen, nie vollständig implementiert

**Der Ansatz:** Wenn neues Wissen zu einem bestehenden Thema entsteht sollte das Chat-Modell das alte Dokument und das neue Wissen nehmen und eine fusionierte, saubere Version schreiben. Automatische Wissensverdichtung statt wachsender Dateien.

**Warum verworfen — Der Bock als Gärtner:** Es ist strukturell unlogisch, dasselbe Modell, das im Chat Fehler macht, als fehlerfreien Redakteur einzusetzen. Das Modell konzentriert sich beim Umschreiben so stark auf das neue Wissen dass es alte fundamentale Fakten einfach löscht oder vergisst. Regressions-Fehler sind kaum erkennbar weil die fusionierte Version syntaktisch korrekt und inhaltlich plausibel wirkt — aber alte Fakten fehlen.

**Die entscheidende Erkenntnis:** Konsolidierung ist eine redaktionelle Aufgabe. Redaktionelle Aufgaben brauchen menschliches Urteil.

---

## Sackgasse C — Blindes Anhängen ("Upsert & Append")

**Zeitraum:** April 2026  
**Status:** Verworfen

**Der Ansatz:** Neue Erkenntnisse chronologisch mit Datumsstempel unten an die bestehende Master-Datei anhängen. Einfach, schnell, keine Konsolidierung nötig.

**Warum verworfen:** Das löst das Duplikat-Problem auf Dateiebene — aber erzeugt Redundanz und Widersprüche innerhalb derselben Datei. Wenn in Abschnitt 1 (März) steht "Nutze Funktion X" und in Abschnitt 5 (Juni) "Nutze Y statt X" füttert das RAG das LLM mit widersprüchlichen Chunks aus derselben Datei. Das Modell hat keinen Mechanismus um zu erkennen welcher Chunk aktueller ist — es würfelt.

**Die entscheidende Erkenntnis:** Chronologisches Anhängen ist Versionskontrolle ohne Versionskontrolle. Git löst das Problem besser als jeder Append-Mechanismus.

---

## Sackgasse D — Reine mathematische Filter

**Zeitraum:** Mai 2026  
**Status:** Verworfen, nie vollständig implementiert

**Der Ansatz:** Kosinus-Ähnlichkeit zwischen neuem Inhalt und bestehendem Core berechnen. Wenn der neue Text zu ähnlich ist wird das Speichern blockiert — Duplikate werden automatisch verhindert.

**Warum verworfen — False Alarms:** Das System blockiert fälschlicherweise sinnvolle Ergänzungen weil der Vektor-Abstand unter einem Schwellenwert liegt obwohl der Inhalt inhaltlich neu und relevant ist.

**Warum verworfen — Silent Failures:** Ein Tippfehler oder eine leicht abweichende Formulierung verändert den Vektor minimal — Müll schlüpft durch weil er mathematisch "neu genug" wirkt.

**Warum verworfen — Filter-Overload:** Am Ende sitzt der Entwickler vor einer Liste von Blockierungen und Durchlässern und muss manuell entscheiden. Das ist mehr Aufwand als direktes manuelles Review — ohne den Kontext den manuelles Review bietet.

**Die entscheidende Erkenntnis:** Mathematik kann Ähnlichkeit messen aber nicht Relevanz beurteilen. Das ist ein fundamentaler Unterschied.

---

## Die neue Ziel-Architektur — 3-stufiges Speichermodell

Aus den vier Sackgassen entstand eine klare Anforderung: das System soll lernfähig bleiben ohne die Datenhoheit aufzugeben. Die Lösung ist ein **3-stufiges Speichermodell mit asynchroner, mehrschichtiger Validierung** und konsequentem Human-in-the-Loop:

```
Chat-Verlauf
     ↓
[Stufe 1] Kurzzeitgedächtnis (SQLite — persistent, lokal)
     ↓  (expliziter !save Befehl)
[Stufe 2] Modell-Wechsel + automatisierter Türsteher (Quarantäne)
     ↓  (NLI/Cross-Encoder Check bestanden)
[Stufe 3] Human-in-the-Loop Review (SusiInbox im Dashboard)
     ↓  (Freigabe per Klick)
SUSIpedia (.md) → ingest.py → ChromaDB
```

### Stufe 1 — Kurzzeitgedächtnis *(SQLite)* *(produktiv seit 25.06.2026)*

Der aktuelle Chatverlauf wird persistent in einer lokalen SQLite-Tabelle gehalten (`Chat`, `Message`, `QueueItem`). Kein Datenverlust bei Ollama-Crashes. Jede SUSI-Antwort hat einen HitL-Queue-Button — per Klick landet die Antwort als `QueueItem` in der Datenbank für späteres Review. Was in dieser Stufe noch fehlt, ist das explizite `!save`-Kommando aus dem ursprünglichen Konzept: aktuell wird jede Antwort einzeln manuell in die Queue geschickt, nicht ein ganzer bereinigter Chatverlauf auf einen Befehl hin.

### Stufe 2 — Modell-Wechsel und automatisierter Türsteher *(Quarantäne)* *(geplant)*

Auf `!save` — sobald implementiert — gibt das Frontend sofort eine Rückmeldung zurück. Ein asynchroner Django-Task übernimmt die Verarbeitung im Hintergrund während der Nutzer normal weiterarbeiten kann.

**Warum kein permanenter async Worker nötig ist:** `!save` wird selten ausgelöst — realistisch zwei bis drei Mal pro Tag, nicht nach jedem Chat. Das ist kein hochfrequenter Prozess der einen dauerhaft laufenden Worker rechtfertigt. Ein einfacher Background-Task der bei Bedarf gestartet wird ist ausreichend und wartungsärmer.

**Spezialisiertes Zusammenfassungs-Modell:** Der Background-Task weist Ollama an, das logisch stärkere Modell (z.B. llama3.1:8b) zu laden und den bereinigten Chatverlauf in ein fest definiertes Markdown-Template zu gießen. Der Haupt-Thread bleibt dabei für qwen2.5-coder:7b offen — der Chat läuft nahtlos weiter.

**VRAM-Kontrolle:** Damit Ollama nicht versucht beide Modelle gleichzeitig im VRAM zu halten wird die Umgebungsvariable `OLLAMA_MAX_LOADED_MODELS=1` gesetzt. Das erzwingt dass das Hintergrundmodell das Live-Modell hart ersetzt und nach getaner Arbeit sofort wieder freigibt. qwen2.5-coder:7b wird danach automatisch neu geladen.

**Der automatisierte Türsteher (NLI/Cross-Encoder):** Der Markdown-Entwurf wird durch ein kleines spezialisiertes Cross-Encoder-Modell geprüft (~100M Parameter, läuft auf der CPU) bei temperature=0.0. Die einzige Frage: geht die Zusammenfassung logisch aus den echten Quell-Chunks hervor? Erkennt das Modell eine Abweichung fliegt der Entwurf sofort in den Müll — bevor er die SUSIpedia erreicht. Da der NLI-Check auf der CPU läuft entsteht kein VRAM-Konflikt mit dem aktiven Chat-Modell.

**Wichtige Einschränkung — Sprachbarriere:** Standard-Cross-Encoder-Modelle aus der DeBERTa-Familie (z.B. `cross-encoder/nli-deberta-v3-base`) sind auf englischen Korpora trainiert. Bei deutschen SUSIpedia-Chunks und deutschen Zusammenfassungen entsteht eine hohe False-Negative-Rate — das Modell erkennt Halluzinationen in deutschen Texten nicht zuverlässig. Der Schutz vor Self-Poisoning bricht zusammen.

**Lösung:** Kein Standard-DeBERTa. Stattdessen ein mehrsprachiges Modell:
- `Sahajpreet/german-deberta-v3-base-xnli` (deutsch-optimiert)
- ~~`amberoad/bert-multilingual-passage-reranking-msmarco`~~ (getestet als Reranker, 59% Korrektheit, disqualifiziert — siehe Kapitel 08. Als NLI-Türsteher-Kandidat für Stufe 2 damit ebenfalls nicht mehr erste Wahl.)

Die Modellwahl für den Türsteher ist kein Detail — sie ist eine Sicherheitsanforderung.

### Stufe 3 — Human-in-the-Loop Review *(SusiInbox, geplant — aktuell Django Admin)*

Besteht der Entwurf den automatischen Check landet er in einer Django-Datenbanktabelle (`QueueItem`). Aktuell wird diese Tabelle im Django Admin reviewed; das eigens gestaltete Dashboard mit diskreter Benachrichtigung (`SusiInbox`) ist der noch ausstehende Frontend-Teil dieser Stufe.

Die Kontroll-Matrix zeigt für jeden Vorschlag drei Dinge nebeneinander:

```
| Ursprüngliche Frage | Echte Quell-Chunks | Markdown-Entwurf |
```

Das 5-Sekunden-Review muss nicht während des Chats passieren. Einmal pro Woche die Inbox öffnen — ein Klick auf "Freigeben" schreibt die `.md`-Datei in die SUSIpedia und stößt `ingest.py` an, ein Klick auf "Löschen" verwirft den Entwurf.

Abgelehntes Material wandert in eine `RejectedSaves`-Tabelle — perfektes Testmaterial für zukünftige Prompt-Optimierungen und ein automatisch wachsendes Negativ-Trainingsset.

---

## Was diese Evolution bedeutet

Die vier Sackgassen haben ein gemeinsames Muster: sie alle versuchen menschliches Urteil durch Automatismus zu ersetzen. Das ist in einem System das persönliches Langzeitgedächtnis verwaltet der falsche Ansatz.

Die neue Architektur dreht das Verhältnis um: die KI ist ein hocheffizienter Sekretär der Entwürfe vorschreibt und vorprüft. Der Mensch behält die absolute Datenhoheit über das Langzeitgedächtnis. Das ist kein Kompromiss — es ist das richtige Designprinzip für ein System das dauerhaft zuverlässig bleiben soll.

> *"Human-in-the-Loop ist keine Einschränkung der KI. Es ist die Voraussetzung für Vertrauen in die KI."*

---

→ *Zurück zur Übersicht: [susi_00_übersicht.md](susi_00_übersicht.md)*  
→ *Weiter: [susi_06_grenzerfahrungen.md](susi_06_grenzerfahrungen.md)*  
→ *Produktivbetrieb: [susi_08_produktivbetrieb.md](susi_08_produktivbetrieb.md)*  
*Stand: Juli 2026 · Martin Freimuth*