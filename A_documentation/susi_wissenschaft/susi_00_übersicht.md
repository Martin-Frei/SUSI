# SUSI — Selbständige und Schlaue Intelligenzbestie
### Ein lokaler, DSGVO-konformer KI-Assistent — Entwicklungsbericht

**Autor:** Martin Freimuth  
**Zeitraum:** März 2026 – laufend  
**Stack:** Python · Django · HTMX · LangChain · ChromaDB · Ollama · bge-reranker-v2-m3 
**Repository:** github.com/Martin-Frei

---

## Was ist SUSI?

SUSI ist ein vollständig lokal laufender KI-Assistent — kein Cloud-Dienst, keine fremden Server, keine Datenweitergabe. Der Name steht für *Selbständige und Schlaue Intelligenzbestie*. Die zentrale These dieses Berichts: Die Wissensbasis ist das Asset — nicht das Modell. Wer SUSIpedia besitzt, ist unabhängig von Modell-Updates und Anbieter-Entscheidungen. Der Bericht zeigt wie diese These durch systematische Evaluation und iterative Verbesserung empirisch belegt wurde.

Die Designentscheidung dahinter ist ungewöhnlich, aber konsequent:

> *Das Sprachmodell ist austauschbar. Die Wissensbasis ist das eigentliche Asset.*

Was das bedeutet: Egal ob morgen ein besseres Open-Source-Modell erscheint — SUSIpedia, die strukturierte Markdown-Wissensbasis, bleibt. Das Wissen gehört dem Nutzer, nicht dem Anbieter.

---

## Warum überhaupt?

Kommerzielle KI-Assistenten wie Microsoft Copilot oder ChatGPT sind gut — aber sie haben eine strukturelle Schwäche: Wissen verlässt das Unternehmen. Jede Eingabe, jeder Kontext, jede interne Überlegung landet auf fremden Servern.

Für Privatpersonen mag das tolerierbar sein. Für Unternehmen unter DSGVO, AI Act und Geschäftsgeheimnisgesetz ist es ein ernsthaftes Problem.

Die Ausgangsfrage für SUSI war deshalb nicht *"Wie baue ich den besten Chatbot?"* sondern:

> *"Wie baue ich einen KI-Assistenten, der alles lokal verarbeitet, nichts nach außen sendet, und trotzdem mit der Zeit immer smarter wird?"*

→ *Details: [susi_01_motivation.md](susi_01_motivation.md)*

---

## Wie funktioniert das System?

SUSI folgt dem klassischen RAG-Prinzip (Retrieval-Augmented Generation) — aber vollständig lokal:

```
Frage des Nutzers
       ↓
Spracherkennung (ISO 639-1, deterministisch)
       ↓
agent_datum: Reine Kalenderfrage?
  ├─ Ja → Python datetime, ~1ms, kein LLM
  └─ Nein → normale Pipeline
       ↓
Query Rewriting löst Ich-Form und Folgefragen auf
       ↓
Embedding-Modell wandelt Frage in Vektor um
       ↓
ChromaDB sucht die ähnlichsten Wissens-Chunks
       ↓
Reranker sortiert die besten Chunks nach vorne
       ↓
Router wählt das optimale LLM-Profil pro Kategorie
       ↓
Kontext + Frage + System-Prompt
       ↓
Lokales LLM generiert die Antwort
```

Alle Komponenten laufen auf der eigenen Hardware. Kein einziger Byte verlässt das System.

Der Stack hat sich über mehrere Iterationen entwickelt — von einem einfachen Skript zu einem vollständigen Django-Backend mit HTMX-Frontend, differenzieller Ingestion-Pipeline und formalem Evaluierungsframework.

→ *Details: [susi_02_architektur.md](susi_02_architektur.md)*

---

## SUSIpedia — die Wissensbasis

SUSIpedia ist eine strukturierte Sammlung von Markdown-Dateien die als Langzeitgedächtnis des Systems dient. Jede Datei deckt ein klar abgegrenztes Thema ab — von technischen Projektdokumentationen über Lernmaterial bis zu persönlichen Zielen und Lebenslauf.

Eine der wichtigsten praktischen Erkenntnisse aus dem Aufbau der Wissensbasis war inhaltlich, nicht technisch: **Ausformulierte Sätze retrievieren signifikant besser als kompakte Listen.** Embedding-Modelle sind auf natürliche Sprache optimiert — technische Kurznotationen erzeugen Vektoren die schlecht mit natürlichsprachlichen Suchanfragen überlappen.

Diese Erkenntnis hat die gesamte Dokumentationspraxis verändert. Jede neue Datei folgt seitdem einem definierten Format das auf optimales Retrieval ausgelegt ist — nicht auf menschliche Lesbarkeit.

→ *Details: [susi_03_susipedia.md](susi_03_susipedia.md)*

---

## Wie wird Qualität gemessen?

Qualität ohne Messung ist eine Behauptung. Deshalb wurde früh ein formales Evaluierungsframework aufgebaut — statt das System einfach zu benutzen und für "gut genug" zu befinden.

Das Framework misst auf zwei Ebenen:

**Retrieval-Ebene:** Findet das System überhaupt den richtigen Wissens-Chunk? Ein eigens entwickeltes `retrieval_check.py`-Skript beantwortet genau diese Frage — ohne LLM, schnell, reproduzierbar. Die Erkenntnis daraus ist fundamental: Was das Retrieval nicht findet, kann kein Prompt der Welt reparieren.

**End-to-End-Ebene:** Baut das LLM aus dem richtigen Chunk auch die richtige Antwort? Gemessen wird mit BERTScore (semantische Ähnlichkeit), ROUGE-L (lexikalischer Recall) und manuellem Scoring auf einer 0–2-Skala.

Die Kombination beider Ebenen macht sichtbar wo ein Problem wirklich liegt — im Retrieval oder in der Generierung. Das ist der Unterschied zwischen systematischer Optimierung und Raten.

→ *Details: [susi_04_evaluation.md](susi_04_evaluation.md)*

---

## Was nicht funktioniert hat — und warum das wichtig ist

Ein Entwicklungsbericht ohne Fehler ist Marketing, keine Dokumentation.

Im Verlauf der Entwicklung wurden vier Architekturansätze identifiziert und bewusst verworfen:

**Vollautomatische Auto-Save-Pipeline:** Das System sollte eigenständig entscheiden wann eine Konversation in die Wissensbasis zurückgeschrieben wird. Das Risiko: Halluziniert das Modell, schreibt es seine eigenen Fehler ins Langzeitgedächtnis. Eine zerstörerische Feedback-Schleife.

**LLM-basierte Konsolidierung:** Das Chat-Modell sollte alte und neue Wissensdokumente fusionieren. Das Problem: Dasselbe Modell das im Chat Fehler macht ist kein zuverlässiger Redakteur.

**Blindes Anhängen:** Neue Erkenntnisse chronologisch an bestehende Dateien anhängen führt zu widersprüchlichen Chunks — das Modell fängt an zu würfeln.

**Rein mathematische Filter:** Kosinus-Ähnlichkeit als einziger Qualitätsfilter erzeugt False Alarms und Silent Failures gleichzeitig.

Die Lösung ist eine **3-stufige Architektur mit Human-in-the-Loop**: Kurzzeitgedächtnis 
→ automatisierter Türsteher (Cross-Encoder) → asynchrones Review-Dashboard. Die KI schreibt 
Entwürfe vor, der Mensch behält die Datenhoheit. Die alte Auto-Save-Pipeline wurde im Mai 2026 
deaktiviert — die neue Architektur befindet sich in Planung (Q3 2026).

→ *Details: [susi_05_sackgassen.md](susi_05_sackgassen.md)*

---

## Ehrliche Rollenverteilung

SUSI ist kein GPT-4-Ersatz. Das war nie das Ziel.

| Aufgabe | SUSI | Claude / ChatGPT |
|---------|------|-----------------|
| Persönliches Gedächtnis | ✅ | ❌ |
| Projektdokumentation abrufen | ✅ | ❌ |
| Lokale Verarbeitung ohne Cloud | ✅ | ❌ |
| Code-Review, komplexes Debugging | ❌ | ✅ |
| Neue technische Konzepte erklären | ❌ | ✅ |

SUSI und externe KI-Assistenten sind komplementär, nicht kompetitiv. Die Kombination ist stärker als jedes einzelne System.

→ *Details: [susi_06_grenzerfahrungen.md](susi_06_grenzerfahrungen.md)*

---

## Wohin geht die Reise?

**Phase 1 — Lokaler RAG-Assistent (aktiv):**  
Das Kernsystem läuft produktiv. Evaluierungsframework ist aufgebaut, erste Messläufe sind abgeschlossen, die Wissensbasis wächst kontinuierlich.

**Phase 2 — Physische Integration (geplant):**  
Spezialisierte kleine Modelle auf Raspberry Pi als Edge-MCP-Server. Sprachsteuerung via Whisper, Kamera-Integration, Home Assistant Anbindung. SUSI hört zu, sieht und handelt.

**Phase 3 — Persönlicher KI-Agent (Vision):**  
Vollständige Integration privater und beruflicher Wissensbasis. SUSI als proaktiver Assistent der nicht nur antwortet, sondern vorausdenkt.

**Geschäftspotenzial:**  
Die Architektur ist nicht nur für den persönlichen Einsatz gedacht. Lokale, DSGVO-konforme RAG-Assistenten für mittelständische Unternehmen — als Alternative zu Microsoft Copilot für Firmen die ihre Daten nicht in die Cloud geben wollen oder dürfen. Der Kerngedanke — die Wissensbasis als dauerhaft eigenes Asset — ist für Unternehmen strategisch attraktiv.

→ *Details: [susi_07_roadmap.md](susi_07_roadmap.md)*

---

## Sieben Kernerkenntnisse

1. **Die Wissensbasis ist das Asset** — nicht das Modell. Wer SUSIpedia besitzt ist unabhängig von Modell-Updates und Anbieter-Entscheidungen.
2. **Dokumentqualität schlägt Modellgröße** — ausformulierte Sätze retrievieren besser als kompakte Listen, egal wie gut das Embedding-Modell ist.
3. **Retrieval vor Generation messen** — was das Retrieval nicht findet kann kein Prompt reparieren. Erst die Retrieval-Ebene verstehen, dann optimieren.
4. **Human-in-the-Loop ist kein Kompromiss** — es ist das richtige Designprinzip für ein System das dauerhaft zuverlässig bleiben soll.
5. **Einfachheit ist eine Architekturentscheidung** — ein Modell das gut funktioniert schlägt drei Agenten die sich gegenseitig stören.
6. **Language ≠ Computation** — LLMs sollen routen und generieren, nicht rechnen. Für Datum, Alter und Differenzen ist ein deterministisches Tool immer überlegen.
7. **Similarity-Metriken messen Ähnlichkeit, nicht Korrektheit** — BERTScore und ROUGE-L erkennen nicht ob eine Zahl falsch ist. Numerisch präzise Domänen brauchen deterministischen Pre-Check.

---


## Produktivbetrieb (Juni – Juli 2026)

Seit Abschluss der Evaluierungsphase ist SUSI in den Produktivbetrieb übergegangen und wird aktiv weiterentwickelt. Die wichtigsten Komponenten:

- **Router:** Retrieval-getriebenes Profil-System mit 6 Kategorien (susi, projekte, lernen, persoenlich, technik, wissen). `ROUTER_MIN_SCORE = 0.5` als Gate für Out-of-Domain-Fallback
- **Reranker:** bge-reranker-v2-m3 (97% Korrektheit) nach Evolution über drei Modell-Generationen
- **Query Rewriting:** LLM-basiertes Umschreiben von Ich-Form und Folgefragen vor dem Retrieval; Fachbegriffe werden nicht übersetzt
- **Lauf C:** 5.860 Runs bestätigen — Parameter-Unterschiede sind minimal, Dokumentqualität ist der größte Hebel
- **Tool Use:** `agent_datum` löst Kalender- und Altersfragen deterministisch, `agent_britannica` als Live-Fallback für Out-of-Domain-Fragen
- **Chat-History:** SQLite-Persistenz mit HitL-Queue-Button seit 25.06.2026
- **Läufe D–G:** Router-Tracking, qwen3-Thinking-Test (kein Vorteil), doppeltes Rewriting gefunden und gefixt, ValueCheck False Positives → Diagnostic Score 6

→ *Pipeline: [susi_08_produktivbetrieb_pipeline.md](susi_08_produktivbetrieb_pipeline.md)*   
→ *Infrastruktur: [susi_08_produktivbetrieb_infrastruktur.md](susi_08_produktivbetrieb_infrastruktur.md)*   
→ *Evaluierung: [susi_08_produktivbetrieb_evaluation.md](susi_08_produktivbetrieb_evaluation.md)*    
  

---

*Stand: Juli 2026 — Dokument wird laufend aktualisiert*  
*Martin Freimuth · github.com/Martin-Frei*  
*Stack: Python · Django · HTMX · LangChain · ChromaDB · Ollama · bge-reranker-v2-m3*