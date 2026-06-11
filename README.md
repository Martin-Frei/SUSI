# SUSI – Selbständige und Schlaue Intelligenzbestie

> Vollständig lokaler, datenschutzkonformer KI-Assistent mit RAG-Wissensbasis.  
> Kein einziges Byte verlässt den lokalen Rechner.

---

## Was ist SUSI?

SUSI ist ein persönlicher KI-Assistent der komplett lokal läuft – keine Cloud, keine externen APIs, keine Datenweitergabe. Die Wissensbasis heißt **SUSIpedia**: eine wachsende Sammlung von Markdown-Dateien die Martins Projekte, Lernnotizen, Code-Kontext und persönliche Informationen enthält.

Das System kombiniert **Retrieval-Augmented Generation (RAG)** mit lokalen LLMs über Ollama. SUSIpedia ist der eigentliche Kern – das System ist modell-agnostisch und funktioniert mit jedem Ollama-Modell.

---

## Tech Stack

| Komponente | Technologie |
|---|---|
| Backend | Django |
| Frontend | HTMX |
| LLM | Ollama – `qwen2.5-coder:7b` |
| Embeddings | `nomic-embed-text` (bge-m3 in Evaluation) |
| Vector Store | ChromaDB (lokal) |
| Orchestrierung | LangChain |
| Wissensbasis | SUSIpedia – Markdown Files |

**Hardware:** AMD Ryzen 9 5900X · 32 GB RAM · RTX 3090 24 GB VRAM

---

## Projektstruktur

```
SUSI/
├── docs/                    ← SUSIpedia Wissensbasis
│   ├── susi_vision.md       ← Wurzeldokument
│   ├── coding/              ← Projekte: GMM, StockPredict, HouseOfStocks
│   ├── lernen/              ← AI, ML, RAG, Python, HTMX, ...
│   ├── martin/              ← Lebenslauf, Profil, Ziele
│   ├── job/                 ← Jobsuche, Bewerbungen, CV
│   ├── projekte/            ← Projektdokumentation
│   ├── hobbys/              ← Tanzen, Interessen
│   ├── familie/             ← Familiäre Kontexte
│   └── technik/             ← RAG-Einstellungen, Roadmap
├── rag/
│   ├── ingest.py            ← Markdown → ChromaDB (Upsert mit Hash-Erkennung)
│   └── query.py             ← Frage → Retrieval → LLM → Antwort
├── core/                    ← Django App
├── susi_project/            ← Django Settings
├── susi_env/                ← Virtual Environment
├── chroma_db/               ← Lokale Vektordatenbank
│   └── doc_hashes.json      ← Änderungserkennung via MD5
└── manage.py
```

---

## Setup & Start

### 1. venv aktivieren
```powershell
cd C:\Users\tsinn\VSCode\Repos\SUSI
susi_env\Scripts\activate
```

### 2. Docs indexieren (nur bei Änderungen nötig)
```powershell
python rag/ingest.py
```

### 3. SUSI starten
```powershell
python rag/query.py
```

### Alles neu indexieren (Reset)
```powershell
Remove-Item -Recurse -Force chroma_db\*
python rag/ingest.py
```

---

## Wie RAG funktioniert

```
Frage eingeben
     ↓
Frage → Embedding (nomic-embed-text)
     ↓
ChromaDB: Top-k ähnliche Chunks aus SUSIpedia
     ↓
Chunks + Frage + System Prompt → Ollama LLM
     ↓
Antwort ausgeben
     ↓
worth_saving() → susi_evaluates() → bei JA: in SUSIpedia speichern
     ↓
ingest.py läuft automatisch im Hintergrund
```

---

## SUSIpedia – Philosophie

```
Eine .md Datei    = Ein klar abgegrenztes Thema
Ein ## Abschnitt  = Ein Arbeitsschritt mit Datum
Max 3 Ebenen      = Lebensbereich → Projekt → Aspekt
```

**Wichtige Regel:** Immer ausgeschriebene Sätze statt kompakter Listen.  
Kompakte Listen werden vom Retrieval schlecht gefunden.

- ❌ `Champion: xlf_regime = MIXED AND hg-score >= -1.0`  
- ✅ `Die Champion Strategy filtert wo xlf_regime gleich MIXED ist und hg-score größer oder gleich -1.0 ist.`

---

## Bekannte Punkte

- Pydantic V1 Warning bei Python 3.14 → ignorieren, funktioniert trotzdem
- k=5 reicht manchmal nicht → bei komplexen Themen `k` erhöhen
- Interview-Prep Chunks können bei CV-Fragen stören → Metadata-Filtering geplant

---

## Evaluation

SUSI hat ein vollständiges RAG-Evaluierungs-Framework (`tools/evaluation/`):

- **Testset:** 80–100 Fragen über 10 Kategorien
- **Grid Search:** Embedding-Modell · Chunk-Größe · k · Temperatur · Prompt
- **Metriken:** BERTScore + ROUGE-L + automatischer Scorer
- **Ergebnis:** Von ~29% auf ~97% korrekte Antworten durch systematische Optimierung

**Beste Parameterkombination:**  
`bge-m3` · Chunk 1000 · Overlap 50 · k=5 · `llama3.1:8b` · Temp 0.0 · `praezise_CoT` Prompt

---

## Roadmap

### Stufe 1 – Coding Assistent (aktiv ✅)
Lokaler RAG mit Ollama + ChromaDB + LangChain + Django/HTMX.

### Stufe 2 – Physischer Assistent (geplant)
Arduino + Raspberry Pi · Sensoren · Smart Home via Home Assistant.

### Stufe 3 – Persönlicher Lebensassistent (Vision)
Vollständiges Second Brain · LangChain Agents · eigenständiges Handeln.

### Edge MCP Server (Ausblick)
Spezialisierte kleine Modelle auf Raspberry Pis als MCP-Server.  
SUSI auf dem Hauptrechner orchestriert diese als Tools über MCP-Protokoll.

---

## Sicherheit & Datenschutz

- Läuft vollständig lokal, keine Cloud-Abhängigkeiten
- Festplatte verschlüsselt via BitLocker
- Persönliche Ordner zusätzlich via VeraCrypt (geplant)
- Geplant: Zugang nur via Gesichtserkennung (Raspberry Pi)

---

## Verwandte Projekte

| Projekt | Beschreibung |
|---|---|
| **StockPredict V2** | LSTM + XGBoost Aktienvorhersage, deployed auf Railway |
| **Global Market Mood (GMM)** | Sentiment-Analyse globaler Finanznachrichten |
| **HouseOfStocks** | Portfolio-Dashboard mit Django + Supabase |

---

*Entwickler: Martin Freimuth · [github.com/Martin-Frei](https://github.com/Martin-Frei) · Stand: Mai 2026*
