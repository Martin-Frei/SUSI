# SUSI — Kapitel 08c — Evaluierung & Optimierung
Datum: 2026-07-21
Status: aktiv
Zeitraum: 18. Juni – 21. Juli 2026

---

## Kapitel 08c — Wie gut ist SUSI?

Dieses Kapitel dokumentiert die Evaluierungsläufe C bis G und die Erweiterungen am Auto-Scorer. Der Fokus verschob sich nach Lauf C (Parameter-Optimierung abgeschlossen) auf die Qualität der Produktiv-Komponenten: Router-Tracking, Modellvergleiche, Bug-Diagnose und Performance-Optimierung.

→ *Pipeline-Kernkomponenten: [susi_08_produktivbetrieb_pipeline.md](susi_08_produktivbetrieb_pipeline.md)*
→ *Infrastruktur und Tooling: [susi_08_produktivbetrieb_infrastruktur.md](susi_08_produktivbetrieb_infrastruktur.md)*

---

## Lauf C — Parameter-Optimierung abgeschlossen (18.–20.06.)

Lauf C umfasste 293 Fragen, 20 Parameterkombinationen und 5.860 Runs.

### Konfigurationsvergleich

Die Konfiguration mit k=3 ohne Reranker erzielte einen Ø Score von 2.97 bei 98% Korrektheit. Die Konfiguration mit k=7 mit Reranker erzielte Ø 3.01 bei 100%. Das Modell `qwen2.5-coder:7b` erzielte Ø 3.02 bei 100%, `llama3.1:8b` Ø 2.98 bei 99%. Der `similarity`-Algorithmus erzielte Ø 3.01, `mmr` Ø 2.99.

### Ergebnisse nach Kategorie

Die Kategorie `projekte` erzielte Ø 3.02 bei 99% Korrektheit. Die Kategorie `persoenlich` erzielte Ø 3.00 bei 99%. Die Kategorie `lernen` erzielte Ø 2.99 bei 100%. Die Kategorie `susi` erzielte Ø 2.95 bei 98% — die schwächste Kategorie.

### Kernerkenntnis

Parameter-Unterschiede betragen maximal 0.07 Punkte und sind damit statistisch irrelevant. Der größte Hebel war Dokumentqualität — die Hit Rate stieg von 36% auf 91% allein durch bessere Quelldokumente und optimierte Chunk-Größen. Die Phase der Parameter-Optimierung ist abgeschlossen.

---

## Läufe D, E, F, G — Qualitätsmessung der Produktiv-Komponenten

### Lauf D — Router-Tracking (24.06.)

`evaluator.py` und `analyse_csv.py` wurden um `router_profil` und `router_korrekt` erweitert. Neue CSV-Spalten ermöglichen Router-Accuracy-Auswertung pro Kategorie. Router-Accuracy liegt stabil bei ~70%, die Kategorie `technisch` ist mit 60% die schwächste.

### Lauf E — qwen3 Thinking-Test (27.06.)

293 Fragen × 2 Konfigurationen (thinking=on vs. thinking=off). Ergebnis: 0.011 Punkte Unterschied — statistisch irrelevant. `qwen3:8b` (96.9% Korrektheit) liegt praktisch gleichauf mit `qwen2.5-coder:7b` aus Lauf C (97.1%). Das `thinking`-Flag bringt für SUSIs Anwendungsfälle keinen messbaren Vorteil. `qwen2.5-coder:7b` bleibt primäres Produktionsmodell.

### Lauf F — Doppeltes Rewriting gefunden (27.06.)

`ask_susi_eval()` rief intern `ask_susi()` auf — Queries wurden doppelt umgeschrieben. Kostete ~16 Prozentpunkte Korrektheit. Nach Fix: Kategorie `technisch` mit 60% als strukturell schwächste identifiziert. Details: [susi_06_grenzerfahrungen.md — Grenzerfahrung 6](susi_06_grenzerfahrungen.md).

### Lauf G — ValueCheck False Positives und Diagnostic Score 6 (15.07.)

Identisches Setup wie Lauf F2: 40 Fragen, `--live`, vollständige Pipeline. Erster Durchlauf zeigte 70.0% Gesamtkorrektheit — deutlich schlechter als die 92.5% aus F2.

Die Diagnose ergab: ValueCheck produzierte 10 False Positives. Beispiel: Referenz sagt "bge-m3 übertrifft nomic-embed-text um Faktor 18", Antwort sagt "um 52 Prozentpunkte". Beides korrekt, verschiedene Darstellung desselben Sachverhalts. ValueCheck extrahierte die 18, fand sie nicht in der Antwort und setzte Diagnostic Score 1 (Halluzination). Das Mapping `DIAG_ZU_QUALITAET[1] = 0` machte daraus Quality Score 0.

Fix: neuer Diagnostic Score 6 ("ValueCheck-Konflikt"). Wird vergeben wenn ValueCheck `"falsch"` meldet aber BERT > 0.65 und ROUGE > 0.15. Score 6 hat `manuell: True` und Quality-Mapping `None` → RAGAS bewertet in der Grauzone-Phase statt hart auf 0 abzustrafen. `MAX_SCORE` steigt von 5 auf 6, die Diagnostic Scale ist jetzt 0–6.

Ergebnisse nach Fix: 82.4% automatisch bewertet (34 von 40), manuell korrigiert 93.8%. Die Differenz kommt von 6 unbewerteten Grauzone-Fragen. Router-Accuracy stabil bei 67.5% (27/40). Wichtiger Nebenbefund: die ~100 Britannica-Artikel in ChromaDB kontaminieren das bestehende Routing nicht — kein Score-0-Fall enthielt `docs/wissen/`-Quellen.

**Zur Einordnung der Router-Accuracy:** Die 67.5% messen die Übereinstimmung mit der erwarteten Kategorie. Sie sind nicht identisch mit der Antwort-Korrektheit — eine falsch geroutete Frage kann trotzdem korrekt beantwortet werden, weil die Chunks thematisch überlappen und die LLM-Parameter zwischen den Profilen nur minimal differieren (max. 0.07 Punkte, Lauf C). Die Router-Accuracy ist ein Diagnose-Werkzeug, kein Zielwert.

---

## Evaluierungs-Erweiterungen (06.–07.07.)

### ValueCheck (06.07.)

`tools/evaluation/valuecheck.py` — deterministischer Pre-Check für numerische Korrektheit. Extrahiert Zahlen, Daten und Wochentage aus Referenz und Antwort und vergleicht direkt, bevor BERTScore und ROUGE-L berechnet werden. Läuft zwischen Ausweich-Check und ROUGE/BERT-Baum. Wochentage DE/EN als Enum, deutsche Zahlwörter 2–12 (ein/eine ausgenommen wegen Artikel-Kollision), Jahres-Erkennung nur 1990–2035. Rollout-Schalter `VALUECHECK_HART`: True=Score 0 hart, False=Grauzone.

### Referenz-Loader (06.07.)

`tools/evaluation/referenz_loader.py` — rendert dynamische Platzhalter (`{heute}`, `{heute+21}`, `{tage_seit:YYYY-MM-DD}`) beim Laden der Testfragen aus `date.today()`. Testsets veralten nicht mehr ab dem Folgetag.

### DIAG_ZU_QUALITAET als zentrale Konstante (06.07.)

Vorher in `grid_run.py`, `ragas_scorer.py` und `analyse_csv.py` dreifach dupliziert. Jetzt zentral in `auto_scorer.py` definiert. `grid_run.py` importiert die Konstante — die anderen zwei folgen.

---

## Reranker-Performance — 120s → 3–5s (21.07.)

Das Reranking dauerte bei bestimmten Queries 100–130s statt 3–5s. Query-abhängig, nicht reihenfolge-abhängig. Die VRAM-Theorie wurde widerlegt — Root Cause waren Monster-Chunks aus dem alten `RecursiveCharacterTextSplitter` (→ susi_08_produktivbetrieb_infrastruktur.md, Ingest-Umbau).

Neben `_split_oversized()` wurden zwei weitere Schichten gefixt. `_warmup()` in `core/apps.py` erzeugte einen eigenen `CrossEncoder()` auf GPU der nie benutzt wurde — der Singleton in `query.py` lud nochmal auf CPU. Fix: Warmup ruft jetzt `get_reranker()` auf, eine Instanz, auf CPU. `CrossEncoder(RERANKER_MODEL, device="cpu")` mit `os.environ["CUDA_VISIBLE_DEVICES"] = ""` ganz oben in `query.py` verhindert VRAM-Konflikte mit Ollama.

Ergebnis: India-Query von 120.8s auf 3.4s, Germany von 112.7s auf 5.1s, Japan von 102.7s auf 3.2s.

---

## Stand: Juli 2026 · Martin Freimuth

→ Zurück zur Übersicht: `susi_00_übersicht.md`
→ Zurück: `susi_08_produktivbetrieb_infrastruktur.md`