# 04 — Evaluation
### SUSI Entwicklungsbericht · Stand Juli 2026

---

## Warum formale Evaluation?

Qualität ohne Messung ist eine Behauptung. SUSI wurde nicht einfach benutzt und für "gut genug" befunden. Von Anfang an war klar dass ein System das täglich genutzt wird und wächst eine objektive Datenbasis braucht — nicht Intuition.

Das Evaluierungsframework beantwortet zwei fundamentale Fragen:

1. **Retrieval-Frage:** Findet das System überhaupt den richtigen Wissens-Chunk?
2. **Generierungs-Frage:** Baut das LLM aus dem richtigen Chunk auch die richtige Antwort?

Diese Trennung ist entscheidend. Was das Retrieval nicht findet kann kein Prompt der Welt reparieren. Was das Retrieval findet aber das LLM falsch beantwortet ist ein anderes Problem mit einer anderen Lösung.

---

## Die Evaluierungs-Konfiguration

Alle Läufe werden durch `tools/evaluation/config.yaml` gesteuert — eine einzige Datei die festlegt welche Embedding-Modelle, Chunk-Größen, Top-K-Werte, LLMs und Prompts gegeneinander getestet werden. Das macht jeden Lauf reproduzierbar und verhindert dass Parameter-Entscheidungen im Code versteckt sind.

```yaml
meta:
  name: "SUSI RAG Evaluation v2 — Fokus-Lauf"
  version: "2.0"
  datum: "2026-05-25"
  docs_path: "docs"
  fragen_path: "tools/evaluation/testfragen.json"
  seed: 42

data_engineering:
  chunk_sizes:   [300, 750, 850, 1000, 1150, 1300]   # über alle Läufe getestet
  chunk_overlaps: [50]
  separators:    ["## ", "### ", "\n\n", "\n", " "]

  embedding_models:
    - name: "nomic-embed-text"   # Lauf 1 — Baseline
    - name: "bge-m3"             # Läufe 3–8 — aktiv
    - name: "mxbai-embed-large"  # Lauf 2 — Vergleich

  embedding_device: "cuda"

retrieval:
  top_k_values:  [3, 5, 7, 8, 9]   # über alle Läufe getestet
  algorithms:
    - name: "similarity"   # aktiv in allen Läufen
    - name: "mmr"          # evaluiert in Lauf C — Ø 2.99 vs. similarity Ø 3.01, statistisch irrelevant
  score_thresholds: [null]

generation:
  llm_models:
    - name: "qwen2.5-coder:7b"   # aktiv
    - name: "llama3.1:8b"        # aktiv

  temperatures: [0.0]

  system_prompts:
    - name: "susi_standard"
    - name: "praezise_alt"
    - name: "praezise_neu"          # aktiv
    - name: "praezise_Chain_of_Thought"
    - name: "praezise_hybrid"
```

Der Grid-Runner (`grid_run.py`) zieht alle aktiven Kombinationen aus dieser Config und läuft sie sequenziell durch. Ein Lauf mit 4 Fragen × 5 Prompts × 2 k-Werten ergibt 40 Einträge in der CSV — ohne eine einzige manuelle Konfigurationsänderung zwischen den Läufen.

---

## Die Metriken

### BERTScore *(eingeführt 24.05.2026)*

BERTScore misst die semantische Ähnlichkeit zwischen generierter Antwort und Referenzantwort. Anders als exakte String-Vergleiche erkennt BERTScore auch Synonyme und umformulierte Aussagen. Wertebereich 0–1, wobei >0.85 als sehr gut gilt.

Wichtige Zusatzmetrik: `max_chunk_bert` — der BERTScore des besten gefundenen Chunks gegen die Referenzantwort. Die Differenz `delta = antwort_bert - max_chunk_bert` zeigt wo das Problem liegt: negativer Delta bedeutet der Chunk hatte die Information aber das LLM hat sie verloren — ein Generation-Problem. Positiver Delta bedeutet das LLM hat mehr geantwortet als im Chunk stand — Halluzinations-Verdacht.

### ROUGE-L *(eingeführt 26.05.2026)*

ROUGE-L misst die längste gemeinsame Teilfolge zwischen generierter Antwort und Referenz — lexikalisch, nicht semantisch. Das ist die schärfere Metrik bei falschen Eigennamen oder falschen Modellbezeichnungen: BERTScore würde "nomic-embed-text" und "bge-m3" als semantisch ähnlich bewerten weil beide Embedding-Modelle sind. ROUGE-L erkennt dass die Namen verschieden sind und gibt einen niedrigen Score. Die Kombination beider Metriken deckt beide Fehlertypen ab.

### Der Auto-Scorer *(entwickelt Mai–Juni 2026)*

Der Auto-Scorer (`auto_scorer.py`) ist das zentrale Werkzeug um den manuellen Bewertungsaufwand bei hunderten von Grid-Läufen auf ein handhabbares Maß zu reduzieren. Er wurde iterativ weiterentwickelt — die Schwellenwerte wurden empirisch aus echten Bewertungsdaten kalibriert, nicht theoretisch festgelegt.

**Die vollständige Score-Skala (0–5):**

| Score | Kategorie | Bedeutung |
|-------|-----------|-----------|
| 0 | Ausweichantwort | SUSI antwortet "nicht verfügbar" — Prompt zu strikt oder Retrieval leer |
| 1 | Halluzination | LLM erfindet komplett — kein Chunk, kein Training |
| 2 | Training korrekt | Richtiger Chunk nicht gefunden, LLM antwortet aus eigenem Training |
| 3 | RAG korrekt ✅ | Richtiger Chunk gefunden, richtige Antwort — das Ziel |
| 4 | Generation-Problem | Chunk war gut aber LLM hat die Information verloren |
| 5 | Falscher Chunk | Retrieval hat in die falsche Kategorie gezeigt |

**Korrektheit** ist definiert als Score ≥ 2 — also alles ab "Training korrekt" aufwärts. Score 3 ist das eigentliche Ziel: RAG hat funktioniert. Score 2 bedeutet das LLM hatte Recht aber aus dem falschen Grund.

**Der Entscheidungsbaum des Auto-Scorers:**

```
1. Ausweich-Phrase erkannt?           → Score 0  (Konfidenz: hoch)
2. ROUGE-L < 0.05?
   └── max_chunk_rougeL < 0.10?       → Score 5  (falscher Chunk)
   └── max_chunk_bert > 0.70?         → Score 4  (Generation-Problem)
   └── sonst                          → Score 1  (Halluzination)
3. ROUGE-L > 0.15 + BERT > 0.65?     → Score 3  (RAG korrekt)
4. ROUGE-L > 0.15 + Delta > 0.10?    → Score 2  (Training korrekt)
5. Alles andere                       → Grauzone → manuell
```

**Schwellenwerte — aus echten Daten kalibriert:**

```
Basis: 768 Läufe aus dem ersten Grid-Lauf (24.05.2026)
Score 3 (korrekt): antwort_rougeL Ø 0.343 | antwort_bert Ø 0.784
Score 0 (falsch):  antwort_rougeL Ø 0.099 | antwort_bert Ø 0.644

Automatisierungsgrad: ~72% (erste Version) → ~86% (nach Kalibrierung)
Genauigkeit automatischer Entscheidungen: ~88%
```

**Die Grauzone — Human-in-the-Loop:**

Alles was nicht eindeutig in eine Kategorie fällt landet in der Grauzone. Der Auto-Scorer zeigt dann Frage, Referenz, generierte Antwort und alle Metriken an und wartet auf manuelle Eingabe. Das ist kein Versagen des Systems — es ist das Designprinzip. ~14% aller Läufe wurden manuell bewertet, ~86% automatisch. Manuelle Bewertung bleibt der Gold Standard; der Auto-Scorer reduziert den Aufwand auf die wirklich ambivalenten Fälle.

**Entwicklung des Auto-Scorers:**

Der Auto-Scorer wurde nicht einmalig gebaut und dann eingefroren. Jede größere Evaluierungsrunde hat neue Grenzfälle aufgedeckt die zu Anpassungen der Schwellenwerte oder neuen Ausweich-Phrasen geführt haben. Die aktuelle Version in `auto_scorer.py` ist das Ergebnis mehrerer Iterationen über den Zeitraum Mai–Juni 2026. Das ist selbst ein Beleg für das Kernprinzip des Projekts: systematische Messung führt zu systematischer Verbesserung.

---

## Die Evaluierungsläufe — chronologisch

**Zur Struktur der Smoke-Läufe:** Alle Läufe 1–7 sind Grid-Läufe — dasselbe Set von 4 Testfragen wird über viele Konfigurationskombinationen (Embedding-Modell, Chunk-Größe, Top-K, Prompt) gelaufen. Die Zeilenzahl in der CSV entspricht der Anzahl der Konfigurationsläufe, nicht der Anzahl verschiedener Fragen. Das erlaubt schnelle Parametertests ohne den Aufwand eines vollständigen Evaluierungslaufs. Lauf 8 ist der erste echte Breitenlauf mit 40 verschiedenen Fragen über alle 4 Kategorien.

**Zur Normierung:** Der Ø-Score (normiert) wird berechnet als `mean(score_manuell) ÷ 3`. Korrektheit ist definiert als Anteil der Läufe mit `score_manuell ≥ 2`. Scores 4 und 5 sind valide Auto-Scorer-Kategorien (Generation-Problem bzw. falscher Chunk) und zählen als nicht korrekt.

### Lauf 1 — Baseline *(24.05.2026)*

```
Config: nomic-embed-text | chunk=300/o50 | k=5 | similarity | qwen2.5-coder:7b | temp=0.0 | prompt=susi_standard
Grid: 4 Testfragen × 192 Konfigurationen = 768 Läufe gesamt
```

| Metrik | Wert |
|--------|------|
| Korrektheit (Score≥2) | 48% |
| Manuell Ø (normiert) | 0.57 |
| BERTScore Ø | 0.671 |
| ROUGE-L Ø | 0.126 |

**Kategorien:**

| Kategorie | Korrekt | Ø Score (normiert) |
|-----------|---------|---------|
| technisch | 91/112 | 0.54 |
| lernen | 54/129 | 0.40 |
| persoenlich | 27/67 | 0.33 |
| projekte | 18/86 | 0.17 |

**Kernerkenntnis:** Technische Fragen funktionieren gut, Projektfragen versagen. nomic-embed-text mit chunk=300 ist die schwächste Konfiguration — 48% Korrektheit bedeutet dass mehr als die Hälfte aller Antworten falsch oder unvollständig sind. Das ist die Baseline von der aus alles verbessert wurde.

---

### Lauf 2 — Embedding-Wechsel *(25.05.2026)*

```
Config: mxbai-embed-large | chunk=300/o50 | k=5 | similarity | qwen2.5-coder:7b | temp=0.0 | prompt=susi_standard
Grid: 4 Testfragen × 2 Prompts × k=5/8 × Chunk-Varianten = 194 Läufe gesamt
```

| Metrik | Wert |
|--------|------|
| Korrektheit (Score≥2) | 61% |
| Manuell Ø (normiert) | 0.68 |
| BERTScore Ø | 0.711 |
| ROUGE-L Ø | 0.199 |

**Kategorien:**

| Kategorie | Korrekt | Korrektheit |
|-----------|---------|-------------|
| technisch | 49/49 | 100% |
| lernen | 33/48 | 69% |
| persoenlich | 32/49 | 65% |
| projekte | 4/48 | 8% |

**Kernerkenntnis:** Allein durch den Wechsel von nomic-embed-text auf mxbai-embed-large steigt die Korrektheit von 48% auf 61% — ohne eine einzige Änderung am LLM oder Prompt. Technische Fragen erreichen 100%, Projekt-Fragen versagen mit 8% fast vollständig. Die Kategorie Projekte ist das klare Schwachstellen-Signal das alle weiteren Experimente motiviert.

---

### Lauf 3 — bge-m3 Einstieg *(25.05.2026)*

```
Config: bge-m3 | chunk=1000/o50 | k=8 | similarity | qwen2.5-coder:7b | temp=0.0 | prompt=susi_standard
Grid: 4 Testfragen × 2 Prompts × 16 Chunk-Varianten = 128 Läufe gesamt
```

| Metrik | Wert |
|--------|------|
| Korrektheit (Score≥2) | **94%** |
| Manuell Ø (normiert) | 0.91 |
| BERTScore Ø | 0.706 |
| ROUGE-L Ø | 0.220 |

**Kernerkenntnis:** bge-m3 mit chunk=1000 erreicht sofort 94% Korrektheit — deutlich besser als mxbai-embed-large mit 65%. Größere Chunks liefern mehr Kontext pro Retrieval und entschärfen das Fragmentierungsproblem das bei chunk=300 dominiert. Damit ist bge-m3 das klare Embedding-Modell für alle weiteren Experimente.

---

### Lauf 4 — chunk=850–1300, k=8 *(25.05.2026)*

```
Config: bge-m3 | chunk=850–1300/o50 | k=8 | similarity | qwen2.5-coder:7b | temp=0.0 | prompt=praezise
Grid: 4 Testfragen × 2 Prompts × 4 Chunk-Größen (850/1000/1150/1300) = 128 Läufe gesamt
```

| Metrik | Wert |
|--------|------|
| Korrektheit (Score≥2) | 91% |
| Manuell Ø (normiert) | 0.89 |
| BERTScore Ø | 0.720 |
| ROUGE-L Ø | 0.263 |

**Kernerkenntnis:** chunk=850–1300 mit k=8 liefert 91% — minimal weniger als bge-m3 mit chunk=1000 in Lauf 3 (94%). chunk=1000 scheint das bessere Gleichgewicht zu treffen. k=8 birgt außerdem das Risiko von Kontext-Mixing. Das wird in nachfolgenden Läufen untersucht.

---

### Lauf 5 — chunk=1000 vs 1300, bge-m3 vs mxbai *(27.05.2026)*

```
Config: bge-m3 + mxbai-embed-large | chunk=1000+1300/o50 | k=8 | similarity | 2 Prompts
Grid: 4 Testfragen × 2 Embeddings × 2 Chunk-Größen × 2 Prompts = 64 Läufe gesamt
```

| Kombination | Korrektheit |
|-------------|-------------|
| bge-m3 + chunk=1000 | **100%** |
| bge-m3 + chunk=1300 | 94% |
| mxbai + chunk=1000 | 94% |
| mxbai + chunk=1300 | 88% |

**Kernerkenntnis:** bge-m3 mit chunk=1000 erreicht in diesem Lauf 100% — die stärkste Einzelkombination im gesamten Grid. Chunk=1300 ist minimal schlechter, mxbai-embed-large fällt gegenüber bge-m3 zurück. Das bestätigt chunk=1000 als optimale Größe und bge-m3 als klares Embedding-Modell der Wahl.

---

### Lauf 6 — Prompt-Varianten *(27.05.2026)*

Drei Grid-Läufe mit bge-m3 | chunk=1000 | k=3–9 und verschiedenen System-Prompts (64 + 32 + 80 = 176 Läufe über 4 Testfragen):

```
praezise_alt:             97% Korrektheit | 0.94 normiert  (32 Fragen)
praezise_neu:             91% Korrektheit | 0.91 normiert  (32 Fragen)
praezise_Chain_of_Thought: 100% Korrektheit | 1.00 normiert  (21 Läufe — kleine Stichprobe!)
```

**Kernerkenntnis:** Der Prompt macht einen messbaren Unterschied — aber erst wenn das Retrieval gut genug ist. Bei schlechtem Retrieval (Lauf 1: 48%) hilft kein Prompt der Welt. Bei gutem Retrieval (bge-m3 + chunk=1000) kann ein präziser Prompt die letzten Prozentpunkte herausholen.

---

### Lauf 7 — k=3 statt k=8 *(27.05.2026)*

```
Config: bge-m3 | chunk=1000/o50 | k=3+5 | similarity | qwen2.5-coder:7b | temp=0.0 | 5 Prompts
Grid: 4 Testfragen × 5 Prompts × k=3/5 × 4 Configs = 160 Läufe gesamt
```

| Metrik | Wert |
|--------|------|
| Korrektheit (Score≥2) | 81% |
| Manuell Ø (normiert) | 0.50 |
| BERTScore Ø | 0.723 |
| ROUGE-L Ø | 0.272 |

**Kernerkenntnis:** k=3 statt k=8 liefert 81% — schlechter als k=8 in den vorherigen Smoke-Tests. Das ist überraschend und widerspricht der Intuition, dass weniger Chunks weniger Kontext-Mixing bedeuten. Mögliche Erklärung: bei k=3 fehlt manchmal der entscheidende ergänzende Chunk der nur bei Hit@4 oder Hit@5 auftaucht (vgl. Retrieval Check: Hit@3 = 65%, Hit@5 = 70%). Der Smoke-Test lief zudem über alle 5 Prompt-Varianten gleichzeitig — unterschiedliche Prompts können das Ergebnis verzerren.

---

### Lauf 8 — Großer Full-Run *(27.05.2026)*

```
Config: bge-m3 | chunk=1000/o50 | k=5 | similarity | 2 LLMs × 3 Prompts
Breitenlauf: 40 Testfragen × 6 Konfigurationen = 240 Läufe — alle 4 Kategorien
LLMs: qwen2.5-coder:7b + llama3.1:8b
Prompts: praezise_neu | praezise_Chain_of_Thought | praezise_hybrid
```

| Metrik | Wert |
|--------|------|
| Korrektheit gesamt (Score≥2) | 60% |
| Manuell Ø (normiert) | 0.69 |
| BERTScore Ø | 0.684 |
| ROUGE-L Ø | 0.202 |

**Nach LLM:**

| LLM | Korrektheit |
|-----|-------------|
| qwen2.5-coder:7b | 62% |
| llama3.1:8b | 58% |

**Nach Prompt:**

| Prompt | Korrektheit |
|--------|-------------|
| praezise_neu | 64% |
| praezise_Chain_of_Thought | 59% |
| praezise_hybrid | 57% |

**Nach Kategorie:**

| Kategorie | Korrekt | Korrektheit |
|-----------|---------|-------------|
| technisch | 42/60 | 70% |
| persoenlich | 36/60 | 60% |
| projekte | 33/59 | 56% |
| lernen | 33/60 | 55% |

**Kernerkenntnis:** Der erste vollständige Lauf über alle Kategorien, zwei LLMs und drei Prompts zeigt 60% Korrektheit. qwen2.5-coder:7b schlägt llama3.1:8b leicht (62% vs 58%) — der Coder-Fokus zahlt sich auch bei allgemeinen Fragen aus. `praezise_neu` ist der beste Prompt (64%). Der wichtigste Fortschritt gegenüber Lauf 2: Projekte von 8% auf 56% — allein durch bge-m3 und chunk=1000. Der Unterschied zwischen Smoke-Test-Ergebnissen (~94–100%) und vollem Datensatz (60%) zeigt dass optimierte Smoke-Tests überoptimistisch sind — der volle Datensatz ist der ehrlichere Maßstab.

---

## Retrieval Check *(10.06.2026)*

Ein eigens entwickeltes Skript (`retrieval_check.py`) misst ausschließlich das Retrieval — ohne LLM, schnell, reproduzierbar. Es beantwortet die Frage: *"War der richtige Chunk überhaupt in den Top-K?"*

```
Config: bge-m3 | chunk=1000/o50 | k=5 | similarity
Fragen: 40 (aus testfragen.json)
```

**Gesamtergebnis:**

```
Hit Rate: 28/40 = 70%

Hit@1:  21/40 = 52.5%   (richtiger Chunk an erster Stelle)
Hit@2:  24/40 = 60.0%
Hit@3:  26/40 = 65.0%
Hit@4:  28/40 = 70.0%
Hit@5:  28/40 = 70.0%   (kein Gewinn von Position 4 auf 5)
```

**Pro Kategorie:**

| Kategorie | Hit Rate | Diagnose |
|-----------|----------|----------|
| lernen | 10/10 = **100%** | ✅ Perfekt |
| technisch | 8/10 = **80%** | ✅ Gut |
| persoenlich | 7/10 = **70%** | ⚠️ Ausbaufähig |
| projekte | 3/10 = **30%** | ❌ Kritisch |

**Interpretation:** 70% Hit Rate bedeutet dass maximal 70% Korrektheit End-to-End erreichbar sind — die restlichen 30% sind Retrieval-Fehler die kein Prompt reparieren kann. Das System liegt unter dem 85%-Schwellenwert ab dem Retrieval als "solide" gilt.

### Diagnose der 12 Misses

Die Miss-Analyse zeigt drei wiederkehrende Muster:

**Muster 1 — Duplikat-Dateien an verschiedenen Orten:**
```
tech_09: erwartet coding/susi/dgsvo_ki.md
         gefunden: lernen/ai/dsgvo_ki.md (4x wiederholt!)
```
Das Retrieval findet die richtige Datei — aber die falsche Kopie. Ein Duplikat-Problem in der SUSIpedia, kein Retrieval-Problem.

**Muster 2 — GMM-Fragen landen bei CI/CD:**
```
proj_01: erwartet coding/gmm/architektur.md
         gefunden: lernen/devops/cicd_grundlagen.md
proj_02: erwartet coding/gmm/dach_pipeline_13032026.md
         gefunden: lernen/devops/cicd_grundlagen.md (3x!)
proj_10: erwartet coding/gmm/progress_13032026.md
         gefunden: lernen/devops/cicd_grundlagen.md
```
GMM-Dateien haben zu wenig distinctive Keywords. Der Vektor landet bei DevOps-Inhalten weil beide Bereiche Begriffe wie "Pipeline", "Deploy", "Run" teilen. Lösung: Topic-Label Ankersätze in GMM-Dateien stärken.

**Muster 3 — Persönliche Fragen ohne klare Datei-Zuordnung:**
```
pers_01: erwartet martin/ziele_beruf.md
         gefunden: martin/ziele_privat.md, ziele_finanzen.md, tanzen.md
pers_03: erwartet martin/lebenslauf.md
         gefunden: ziele_privat.md, heikle_fragen.md, tanzen.md
```
Persönliche Dateien teilen zu viel Vokabular. Eine Frage zu beruflichen Zielen findet private Ziele weil beide Dateien "Martin", "Ziele", "aktuell" enthalten. Lösung: stärkere Topic-Label Differenzierung zwischen den `martin/`-Dateien.

---

## Entwicklung der Korrektheit im Zeitverlauf

```
24.05. nomic-embed-text  chunk=300  k=5   →  48%  (Lauf 1, Baseline)
25.05. mxbai-embed-large chunk=300  k=5   →  61%  (Lauf 2, n=194)
25.05. bge-m3            chunk=1000 k=5   →  94%  (Lauf 3, n=128)
25.05. bge-m3            chunk=850–1300 k=8   →  91%  (Lauf 4, n=128)
27.05. bge-m3            chunk=1000 k=8   →  100% (Lauf 5, bge-m3+mxbai Vergleich, n=16)
27.05. bge-m3            chunk=1000 k=8   →  97%  (Lauf 6, praezise_alt, n=32)
27.05. bge-m3            chunk=1000 k=3   →  81%  (Lauf 7, gemischt, n=160)
27.05. bge-m3            chunk=1000 k=5   →  60%  (Lauf 8, voller Datensatz, n=239)
10.06. Retrieval Check   chunk=1000 k=5   →  70%  Hit Rate (n=40)
```

Der Sprung von 48% auf 94% ist kein Zufall — er ist das Ergebnis systematischer Parameteroptimierung:
1. Embedding-Modell: nomic → bge-m3 (+17 Prozentpunkte allein durch Modellwechsel)
2. Chunk-Größe: 300 → 1000 (+Kontext, weniger Fragmentierung)
3. Prompt: susi_standard → praezise_alt (präzisere Instruktionen)

Die hohen Smoke-Test-Ergebnisse (94%+) müssen mit dem vollen Datensatz (60%) relativiert werden — beide Messungen sind wichtig, aber der volle Datensatz ist der belastbarere Wert.

---

## Das Finding vom 10.06.2026 — Dokumentqualität schlägt Modellgröße

Am 10.06.2026 wurde der Einfluss der SUSIpedia-Dokumentqualität auf die Retrieval Hit Rate direkt gemessen. Das Ergebnis ist die wichtigste einzelne Erkenntnis des gesamten Projekts:

```
Retrieval Hit Rate Entwicklung (10.06.2026):

Start (unkonfiguriert, 230 Fragen):          36%  Hit Rate
Nach Bereinigung (Encoding-Fixes, Duplikate): 53%  Hit Rate
Nach SUSIpedia-Überarbeitung + chunk=1000:   91%  Hit Rate
                                            ──────
Gesamtverbesserung:                         +55 Prozentpunkte
```

**Was verändert wurde — ausschließlich Dokumentqualität:**
- Alle SUSIpedia-Dateien von Stichpunkt-Listen auf Fließtext umgestellt
- Topic-Label Ankersätze am Anfang jeder Sektion eingefügt
- Encoding-Fehler (UTF-8/Latin-1 Umlaut-Doppelkodierung) bereinigt
- Duplikat-Dateien identifiziert und konsolidiert
- chunk_size von 300 auf 1000 angehoben

**Kein besseres Modell wurde eingesetzt.** Derselbe Stack (bge-m3, qwen2.5-coder:7b, ChromaDB), dieselbe Hardware — nur bessere Quelldokumente und größere Chunks.

Das ist ein direkter empirischer Beweis für die Kernthese des Projekts: **die Wissensbasis ist der wichtigste Faktor in einem RAG-System** — wichtiger als das Embedding-Modell, wichtiger als das LLM, wichtiger als Prompt-Engineering. Ein leistungsfähiges Modell auf schlechten Dokumenten bleibt ein schlechtes System.

Die SUSIpedia-Überarbeitung war zum Zeitpunkt dieser Messung noch nicht abgeschlossen — das Ergebnis von 91% ist ein Zwischenwert.

---

## Geplante Folgeläufe nach SUSIpedia-Überarbeitung

Nach der vollständigen Überarbeitung aller SUSIpedia-Dateien nach den Formatierungsregeln (Fließtext, Topic-Label Ankersätze, Encoding-Fixes) werden drei gezielte Vergleichsläufe durchgeführt — in dieser Reihenfolge:



**Lauf A — Direkter Baseline-Vergleich *(voller Datensatz)*:**
```
bge-m3 | chunk=1000/o50 | k=5 | similarity | qwen2.5-coder:7b | temp=0.0 | prompt=praezise_neu
```
Identische Config wie die beste Einzel-Kombination aus Lauf 8 (praezise_neu, qwen) — eine Config über alle 40 Testfragen = 40 Läufe. Vorher: 60% Korrektheit (praezise_neu in Lauf 8). Wie viel Verbesserung bringt die SUSIpedia-Qualität alleine ohne Parameteränderung?

**Lauf B — Bestes bisheriges Ergebnis auf vollem Datensatz :**
```
bge-m3 | chunk=1000/o50 | k=3 | similarity | qwen2.5-coder:7b | temp=0.0 | prompt=praezise_alt
```
Lauf 7 erreichte 98% — aber nur auf 61 Fragen. Jetzt auf dem vollen Datensatz aller Kategorien wiederholen. War 98% ein Ausreißer oder hält das?

**Erwartung:** Signifikante Verbesserung vor allem in der Kategorie Projekte (von 30% Hit Rate auf 60%+) durch stärkere Topic-Label Ankersätze in GMM- und StockPredict-Dateien.

**Lauf C — Retrieval Check *(zuerst, weil schnellster Lauf)*:**
```
retrieval_check.py | bge-m3 | chunk=1000 | k=5
```
Vorher: 70% Hit Rate gesamt, Projekte nur 30%. Läuft ohne LLM in wenigen Minuten. Zeigt sofort ob die SUSIpedia-Verbesserungen das Retrieval-Problem lösen — besonders ob GMM-Dateien nicht mehr bei CI/CD-Inhalten landen und ob persönliche Dateien besser differenziert werden.

## Lauf C — Der letzte Grid-Lauf *(18.–20.06.2026)*

Lauf C war als Retrieval Check geplant, wurde aber zum vollständigen Grid-Lauf 
ausgebaut: 293 Fragen, 20 Parameterkombinationen, 5.860 Runs.

```
Config: bge-m3 | chunk=1000/o50 | k=3/5/7/9 | similarity + mmr | qwen2.5-coder:7b + llama3.1:8b | temp=0.0 | mit/ohne Reranker
```

**Hinweis zur Skala:** Lauf C bewertet noch auf der archivierten **Quality-Rohskala 0–3** — dem Vorgänger der heutigen 0–2-Quality-Skala, nicht zu verwechseln mit der Diagnostic-Skala 0–5 des Auto-Scorers (Score 3 hier bedeutet "RAG perfekt", nicht Diagnostic-Score 3). Die folgenden Ø-Scores sind daher **nicht** normiert und nicht direkt mit den auf 0–2 umgestellten Läufen D/E/F vergleichbar. Belastbar über den Skalenbruch hinweg ist nur die Korrektheitsquote (`Score ≥ 2`) und die skalenunabhängige Hit Rate.

**Gesamtergebnis (Quality-Rohskala 0–3):**

| Konfiguration | Ø Score | Korrekt |
|---|---|---|
| k=3, ohne Reranker | 2.97 | 98% |
| k=7, mit Reranker | 3.01 | 100% |
| qwen2.5-coder:7b | 3.02 | 100% |
| llama3.1:8b | 2.98 | 99% |
| similarity | 3.01 | — |
| mmr | 2.99 | — |

**Nach Kategorie:**

| Kategorie | Ø Score | Korrekt |
|-----------|---------|---------|
| projekte | 3.02 | 99% |
| persoenlich | 3.00 | 99% |
| lernen | 2.99 | 100% |
| susi | 2.95 | 98% |

**Kernerkenntnis:** Parameter-Unterschiede sind maximal 0.07 Punkte — statistisch 
irrelevant. Der größte Hebel war Dokumentqualität (Hit Rate 36% → 91%), nicht 
Modell-Tuning. Die Phase der Parameter-Optimierung ist abgeschlossen.

Die `susi/`-Kategorie ist mit 98% die schwächste — hier besteht noch Potenzial 
durch bessere Topic-Label Ankersätze in den SUSI-eigenen Dokumentationsdateien.

→ *Details: [susi_08_produktivbetrieb.md](susi_08_produktivbetrieb.md)*

## Lauf D — Breitenlauf mit RAGAS-Validierung *(24.–25.06.2026)*

Nachdem Lauf C gezeigt hat dass Parameter-Unterschiede minimal sind, verschiebt sich der Fokus: die Qualität der Produktiv-Komponenten wird gemessen, nicht mehr die beste Parameter-Kombination gesucht. Lauf D ist ein Breitenlauf mit **800 Runs**, ausgewertet über die neue 0–2-Qualitätsskala.

**Wichtig zur Vergleichbarkeit:** Lauf D verwendet die 0–2-Skala, Lauf C die alte 0–3-Skala. Die beiden Läufe sind deshalb in den Ø-Scores nicht direkt vergleichbar. Manuell vergebene 3er aus der Lauf-C-Ära werden vom aktuellen Analyser als ungültig ignoriert. Der belastbare Vergleichswert über den Skalenbruch hinweg bleibt die Hit Rate (36% → 91%).

**Das Grauzonen-Problem:** Der Auto-Scorer konnte nur 70.1% der 800 Einträge eindeutig bewerten, 29.9% fielen in die Grauzone. Der Grund ist bekannt aus Kapitel-04-Metriken: paraphrasierte, inhaltlich korrekte Antworten erzeugen einen niedrigen ROUGE-L und rutschen dadurch aus dem Auto-Scorer-Fenster. Eine frühe Aussage von 18.8% Fehlerrate in der Kategorie `lernen` basierte nur auf den 214 sicher bewerteten Einträgen und war damit statistisch nicht belastbar.

### RAGAS — die dritte Bewertungsstufe *(25.06.2026)*

Um die Grauzone aufzulösen ohne einen neuen Grid-Lauf zu starten, kam eine dritte Bewertungsstufe dazu: `tools/evaluation/ragas_scorer.py`. RAGAS bewertet Grauzone-Einträge semantisch anhand von zwei Metriken — **Faithfulness** (ist die Antwort aus den Chunks ableitbar?) und **Answer Relevancy** (beantwortet sie die Frage?). Das Script läuft vollständig lokal mit Ollama (`qwen2.5:7b`) und `bge-m3` als Embedding, ohne OpenAI-Key, DSGVO-konform. Schwellenwerte: RAGAS-Score ≥ 0.50 → korrekt, ≤ 0.20 → falsch, dazwischen → Haiku-Judge als vierte Instanz.

**Ergebnis der Grauzonen-Auflösung:** Von 239 Grauzone-Einträgen wurden 220 als korrekt bewertet (92.1%), 1 als falsch, 18 blieben unklar. Die Grauzone bestand also fast vollständig aus korrekten paraphrasierten Antworten, die der Auto-Scorer nur wegen niedrigem ROUGE-L nicht erkannte.

**Gesamtergebnis Lauf D nach RAGAS:**

| Kategorie | Korrektheit | Einträge |
|-----------|-------------|----------|
| technisch | 100% | 199 |
| lernen | 97.4% | 196 |
| persoenlich | 95.9% | 196 |
| projekte | 94.7% | 191 |
| **Gesamt** | **97.1%** | **782** |

**Kernerkenntnis:** Die scheinbare 18.8%-Fehlerrate bei `lernen` war fast vollständig ein Grauzonen-Artefakt — nach RAGAS liegt sie bei 2.6%. Das eigentliche Problem war die Paraphrasierungs-Blindheit des Auto-Scorers, nicht die Dokumentqualität der `lernen`-Kategorie. In diesem Lauf ist `technisch` mit 100% die **stärkste** Kategorie — ein Punkt der in Lauf F mit der Live-Pipeline noch einmal ganz anders aussehen wird.

---

## Lauf E — qwen3 Thinking-Test *(27.06.2026)*

293 Fragen × 2 Konfigurationen: `qwen3:8b` mit `thinking=true` vs. `thinking=false`.

**Ergebnis (alle auf 0–2-Skala):**

| Konfiguration | Korrektheit |
|---|---|
| qwen3:8b thinking=off | 96.9% |
| qwen3:8b thinking=on | 96.9% |
| qwen2.5-coder:7b (Lauf D) | 97.1% |

Unterschied thinking=on vs. off: 0.011 Punkte — statistisch irrelevant. `qwen3:8b` (Lauf E) liegt praktisch gleichauf mit `qwen2.5-coder:7b` aus Lauf D. Das `thinking`-Flag bringt für SUSIs Anwendungsfälle keinen messbaren Vorteil. `qwen2.5-coder:7b` bleibt primäres Produktionsmodell.

**Kernerkenntnis:** Ein größeres Modell mit Reasoning-Modus liefert hier keinen messbaren Qualitätsgewinn gegenüber dem spezialisierten 7B-Coder-Modell — bei höherem Rechenaufwand. Für ein Wissens-RAG mit kurzen Faktenantworten ist das kleinere, token-effiziente Modell die richtige Wahl. Der Thinking-Overhead lohnt sich in dieser Domäne nicht.

---

## Lauf F — Erste End-to-End-Router-Evaluation *(27.06.2026)*

Läufe D und E hatten eine strukturelle Lücke: sie testeten nicht die vollständige Live-Pipeline. Das Router-Profil wurde manuell auf die erwartete Kategorie gesetzt — ob der Router im echten Betrieb auch selbst das richtige Profil wählt, war damit nicht gemessen. Lauf F schließt diese Lücke: mit dem neuen `--live`-Flag läuft die komplette Pipeline (detect_language, rewrite_query, Retrieval, Reranker, `router.py`, Generierung). Neu sind die CSV-Spalten `router_profil` und `router_korrekt`, die protokollieren welches Profil der Router gewählt hat und ob es mit der Gold-Standard-Kategorie übereinstimmt. Getestet wurden 40 Fragen (10 pro Kategorie).

**Der stille Bug — im ersten Live-Lauf entdeckt:** Der erste Durchlauf (F1) deckte einen Bug auf, der erst mit dem `--live`-Pfad aktiv wurde: `ask_susi_eval()` rief intern `ask_susi()` auf, das seinerseits `rewrite_query()` enthält. Jede Testfrage wurde dadurch zweimal umgeschrieben. Nach dem Fix führt `ask_susi_eval()` die Pipeline selbst durch, ohne `ask_susi()` intern aufzurufen.

**Ausmaß — F1 vs. F2:**

| Kategorie | F1 (mit Bug) | F2 (nach Fix) |
|-----------|-------------|---------------|
| lernen | 95.0% | 100% |
| projekte | 75.0% | 100% |
| persoenlich | 55.0% | 80.0% |
| technisch | 80.0% | 60.0% |
| **Gesamt** | **76.2%** | **92.5%** |

Das doppelte Rewriting kostete **16.3 Prozentpunkte** Gesamt-Korrektheit. `persoenlich` war am stärksten betroffen, weil Eigennamen durch doppeltes Umschreiben verfälscht wurden.

**Zwei Erkenntnisse, die manuelle Läufe nicht liefern konnten:**

Erstens: **Router-Accuracy stabil bei ~70%.** Von 40 Fragen wurden 28 korrekt geroutet — konsistent in F1 und F2. Der Live-Router erreicht 92.5% gegenüber 97.1% bei manueller Profil-Zuweisung (Lauf D). Der Verlust von 4.6 Prozentpunkten ist der Preis des automatischen Routings — kein LLM-Qualitätsproblem, sondern falsch geroutete Fragen und Wissenslücken in einzelnen Profilen.

Zweitens: **`technisch` ist mit 60% jetzt die schwächste Kategorie** — das genaue Gegenteil von Lauf D (100%, stärkste). Der Grund ist kein Widerspruch: In Lauf D wurde das Profil manuell gesetzt und RAGAS bewertete gegen den Referenztext; in Lauf F arbeitet RAGAS mit dem echten `kontext_text` der Live-Pipeline und deckt reale Wissenslücken in `docs/technik/` auf. Die niedrigere Zahl in F2 ist die validere. Der inhaltliche Ausbau von `docs/technik/` ist damit der direkte Hebel.

→ *Details zum Rewriting-Bug: [susi_06_grenzerfahrungen.md — Grenzerfahrung 6](susi_06_grenzerfahrungen.md)*

---

## Datumsarithmetik-Sprint *(30.06.–06.07.2026)*

### Befund (30.06.)

10 Kalenderfragen getestet. Der Auto-Scorer vergab allen 10 Einträgen `auto_score=3` — obwohl 7 der 10 Antworten nicht korrekt waren (falsche Werte oder Ausweichantwort). SUSI nannte falsche Wochentage und falsche Tagesdifferenzen. BERTScore und ROUGE-L erkannten die Fehler nicht. Von diesen fängt ValueCheck die wertbasierten Fehler ab; der rein logische Fall (datum_09) bleibt außerhalb seines Scope.

**Ursache:** Similarity-basierte Metriken können prinzipiell nicht erkennen ob eine Zahl richtig ist. "14 Tage" und "21 Tage" sind sich semantisch ähnlich — eine davon ist falsch. Das ist keine Kalibrierungs-Frage, sondern eine fundamentale Grenze der Metrik-Klasse.

→ *Details: [susi_06_grenzerfahrungen.md — Grenzerfahrung 5](susi_06_grenzerfahrungen.md)*

### Lösung — drei Schichten (06.07.)

**Schicht 1 — ValueCheck** (`tools/evaluation/valuecheck.py`): deterministischer Pre-Check, läuft vor BERTScore und ROUGE-L. Extrahiert Zahlen, Daten und Wochentage aus Referenz und Antwort, vergleicht direkt. Findet er einen Widerspruch → **Diagnostic Score 1** (Halluzination / falscher Wert), der über `DIAG_ZU_QUALITAET` auf Quality 0 gemappt wird. Score 0 bleibt der Ausweichantwort vorbehalten, deren Check vor ValueCheck läuft. *(→ Kapitel 06, Grenzerfahrung 5, für die vollständige Herleitung warum Similarity-Metriken hier versagen)*

**Schicht 2 — Referenz-Loader** (`tools/evaluation/referenz_loader.py`): dynamische Platzhalter in Testfragen (`{heute}`, `{heute+21}`, `{tage_seit:YYYY-MM-DD}`) werden beim Laden aus `date.today()` gerendert. Testsets veralten nicht mehr über Nacht.

**Schicht 3 — agent_datum** (`rag/agent_datum.py`): deterministischer Tool-Use-Guard vor dem RAG-Router. Reine Kalender-Fragen werden von Python `datetime` gelöst — ~1ms statt ~8s, keine Halluzination möglich.

### Ergebnis der drei Schichten

```
30.06. alter Auto-Scorer, hartcodierte Refs:  Ø 2.0  (blind grün — Fehler unsichtbar)
06.07. + ValueCheck:                          Ø 0.20 (Fehler jetzt sichtbar)
06.07. + dynamische Refs:                     Ø 0.40
06.07. + agent_datum:                         Ø 2.00 (8/10 korrekt gelöst)
```

---

## Auto-Scorer — Erweiterungen (06.07.)

### DIAG_ZU_QUALITAET als zentrale Konstante

Vorher in `grid_run.py`, `ragas_scorer.py` und `analyse_csv.py` dreifach dupliziert. Jetzt zentral in `auto_scorer.py` definiert und von `grid_run.py` importiert. Die anderen zwei folgen.

### Zwei Skalen — klare Trennung

Die Diagnostic Scale (0–5) erklärt *warum* eine Antwort so ist. Die Quality Scale (0–2) beantwortet *ob* sie korrekt ist für den Nutzer. Das Mapping `DIAG_ZU_QUALITAET`: 0→0, 1→0, 2→1, 3→2, 4→0, 5→0. Der Quality-Wert 1 (teilweise korrekt) entsteht ausschließlich über diese Mapping-Regel aus Diagnostic 2 (Training korrekt) — der Auto-Scorer vergibt ihn also nicht aus einer eigenen Metrik-Schwelle, sondern nur als Abbild des Diagnostic-Werts.

---

## Offene Fragen *(Stand Juli 2026)*

**MMR vs. similarity:** Gelöst in Lauf C — MMR (Ø 2.99) minimal schlechter als similarity (Ø 3.01), statistisch irrelevant. Similarity bleibt Standard.

**Cross-Encoder Reranker:** Gelöst — bge-reranker-v2-m3 (97% Korrektheit) produktiv. Details: Kapitel 08.

**Kategorie-spezifische Optimierung:** Gelöst durch Router mit 5 Profilen. Details: Kapitel 08.

**Hybrid Search:** Weiterhin offen. GMM-Misses deuten auf Keyword-Bedarf hin. Entscheidung zurückgestellt bis Router-Accuracy weiter analysiert ist.

**Router-Accuracy ~70%:** Details und Ursache siehe Lauf F oben.

**agent_datum Zweig 2:** Gelöst (10.07.2026). Fragen mit Entitätsbezug ("Wie alt ist SUSI?") extrahieren das Startdatum aus dem retrievten Chunk, Python berechnet die Differenz und injiziert sie als fertigen Fakt ins Prompt. Das LLM formuliert nur noch, rechnet nicht mehr. Details: Kapitel 08.

**`ragas_scorer.py` Stacked-CSV-Bug:** verliert `auto_score`-Werte bei gestapelten CSVs. Fix ausstehend.

**`--nachbewertung` Skala:** akzeptiert 0–2, System nutzt Diagnostic 0–5. Vereinheitlichung ausstehend.

---

→ *Zurück zur Übersicht: [susi_00_übersicht.md](susi_00_übersicht.md)*  
→ *Weiter: [susi_05_sackgassen.md](susi_05_sackgassen.md)*  
→ *Produktivbetrieb: [susi_08_produktivbetrieb.md](susi_08_produktivbetrieb.md)*    
*Stand: Juli 2026 · Martin Freimuth*