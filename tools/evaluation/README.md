# SUSI Evaluation Pipeline

Systematischer Grid-Lauf zur Optimierung der RAG-Parameter.

## Verzeichnis-Struktur

```
tools/evaluation/
├── config.yaml          ← Parameter-Konfiguration (du hast das schon)
├── testfragen.json      ← Gold-Set: Smoke (4) + Full (40 Fragen)
├── indexer.py           ← Baut ChromaDB Collections offline
├── grid_run.py          ← Haupt-Script: fuehrt alle Kombinationen durch
├── evaluator.py         ← Scoring-Logik + CSV-Auswertung
├── README.md            ← Diese Datei
├── chroma_eval/         ← Wird automatisch erstellt (ChromaDB Collections)
└── eval_results.csv     ← Wird automatisch erstellt (Ergebnisse)
```

## Ablauf in 4 Schritten

### Schritt 1 — Gold-Set pruefen

Die `testfragen.json` enthaelt Fragen mit `MANUELL PRUEFEN` als Referenzantwort.  
**Vor dem ersten Lauf:** Oeffne die JSON-Datei und ersetze alle Referenzantworten  
mit den tatsaechlichen Antworten aus deinen SUSIpedia-Dateien.

**Wichtig:** Die Fragen muessen eindeutig aus den Dokumenten beantwortbar sein.

### Schritt 2 — Indexer (einmalig)

```bash
cd C:\Users\tsinn\VSCode\Repos\SUSI
susi_env\Scripts\activate

# Trockenlauf: nur Kombinationen anzeigen
python tools/evaluation/indexer.py --dry-run

# Collections aufbauen (dauert je nach Hardware einige Minuten)
python tools/evaluation/indexer.py
```

Der Indexer baut fuer jede Kombination aus (Embedding-Modell × Chunk-Size × Overlap × Separator)  
eine eigene ChromaDB Collection. Laeuft einmalig, dann gecacht.

### Schritt 3 — Grid-Lauf

```bash
# Smoke-Test: 4 Fragen, prueft ob Pipeline laeuft
python tools/evaluation/grid_run.py --mode smoke

# Mit manueller Bewertung (empfohlen fuer ersten Lauf)
python tools/evaluation/grid_run.py --mode smoke --manual

# Voller Lauf (40 Fragen)
python tools/evaluation/grid_run.py --mode full --manual

# Nur bestimmtes LLM testen (Debug)
python tools/evaluation/grid_run.py --mode smoke --llm qwen2.5-coder:7b --embedding nomic-embed-text

# Kombinationen zaehlen ohne auszufuehren
python tools/evaluation/grid_run.py --dry-run
```

Der Lauf kann jederzeit mit Ctrl+C unterbrochen werden.  
Beim naechsten Start werden abgeschlossene Laeufe automatisch uebersprungen.

### Schritt 4 — Auswertung

```bash
# Top-10 beste Kombinationen anzeigen
python tools/evaluation/grid_run.py --summary

# Direkt ueber evaluator.py
python tools/evaluation/evaluator.py --csv tools/evaluation/eval_results.csv --top 10
```

## Kombinationsrechnung

Mit den Standard-Einstellungen (aktive Parameter):

| Parameter          | Werte | Aktiv |
|--------------------|-------|-------|
| Embedding-Modelle  | 5     | 3     |
| Chunk-Sizes        | 5     | 5     |
| Overlaps           | 4     | 4     |
| Separatoren        | 3     | 3     |
| **Collections**    |       | **180** |
| Top-K              | 6     | 6     |
| Algorithmen        | 3     | 2     |
| Score-Thresholds   | 5     | 5     |
| LLMs               | 7     | 3     |
| Temperatures       | 5     | 5     |
| System-Prompts     | 5     | 3     |
| **Gesamt (Smoke)** |       | **~81.000** |

**Empfehlung fuer den Start:** config.yaml stark einschraenken!  
Zum Beispiel: 1 Embedding × 2 Chunk-Sizes × 2 Overlaps × 1 Separator = 4 Collections,  
dann × 2 Top-K × 1 Algorithmus × 1 LLM × 2 Temperatures × 2 Prompts = 32 Laeufe.

## Manuelle Referenzantworten eintragen

Die `testfragen.json` enthaelt Platzhalter `MANUELL PRUEFEN`.

Beispiel wie eine fertige Frage aussieht:
```json
{
  "id": "tech_01",
  "frage": "Welches Embedding-Modell verwendet SUSI aktuell?",
  "referenzantwort": "SUSI verwendet aktuell nomic-embed-text als Embedding-Modell mit 768 Dimensionen und einer Kontextlaenge von 8192 Token.",
  "quelldatei": "technik/rag_einstellungen.md",
  "schwierigkeit": "einfach"
}
```

## Tipps

- **Erst Smoke-Test laufen lassen** — prueft ob alles technisch funktioniert
- **Referenzantworten zuerst eintragen** — sonst kann die manuelle Bewertung nicht sinnvoll erfolgen
- **config.yaml reduzieren** fuer den ersten Lauf — weniger Parameter, schneller Ergebnis
- **RTX 3090 kommt:** Dann `rtx_3090_24gb` in `hardware_profiles` aktivieren und groessere Modelle freischalten
- **Judge-Modell:** `--judge` nur aktivieren wenn ANTHROPIC_API_KEY gesetzt ist, verursacht Kosten

## Naechste Erweiterungen (nach erstem erfolgreichen Lauf)

- [ ] Heatmap-Visualisierung der Ergebnisse (matplotlib)
- [ ] RAGAS-Integration fuer automatische Faithfulness-Messung
- [ ] BERTScore fuer semantischen Vergleich
- [ ] Automatischer Report als Markdown
