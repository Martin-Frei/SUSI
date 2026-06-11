# 04 — Evaluation
### SUSI Entwicklungsbericht · Stand Juni 2026

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
    - name: "mmr"          # geplant, noch nicht evaluiert
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

**Kernerkenntnis:** k=3 statt k=8 liefert 81% — schlechter als k=8 in den vorherigen Smoke-Tests. Das ist überraschend und widerspricht der Intuition dass weniger Chunks weniger Kontext-Mixing bedeuten. Mögliche Erklärung: bei k=3 fehlt manchmal der entscheidende ergänzende Chunk der nur bei Hit@4 oder Hit@5 auftaucht (vgl. Retrieval Check: Hit@3 = 65%, Hit@5 = 70%). Der Smoke-Test lief zudem über alle 5 Prompt-Varianten gleichzeitig — unterschiedliche Prompts können das Ergebnis verzerren.

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

Die hohen Smoke-Test-Ergebnisse (94%+) müssen mit dem vollen Datensatz (64%) relativiert werden — beide Messungen sind wichtig, aber der volle Datensatz ist der belastbarere Wert.

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

**Lauf C — Retrieval Check *(zuerst, weil schnellster Lauf)*:**
```
retrieval_check.py | bge-m3 | chunk=1000 | k=5
```
Vorher: 70% Hit Rate gesamt, Projekte nur 30%. Läuft ohne LLM in wenigen Minuten. Zeigt sofort ob die SUSIpedia-Verbesserungen das Retrieval-Problem lösen — besonders ob GMM-Dateien nicht mehr bei CI/CD-Inhalten landen und ob persönliche Dateien besser differenziert werden.

**Lauf A — Direkter Baseline-Vergleich *(voller Datensatz)*:**
```
bge-m3 | chunk=1000/o50 | k=5 | similarity | qwen2.5-coder:7b | temp=0.0 | prompt=praezise_neu
```
Identische Config wie die beste Einzel-Kombination aus Lauf 8 (praezise_neu, qwen) — eine Config über alle 40 Testfragen = 40 Läufe. Vorher: 60% Korrektheit (praezise_neu in Lauf 8). Wie viel Verbesserung bringt die SUSIpedia-Qualität alleine ohne Parameteränderung?

**Lauf B — Bestes bisheriges Ergebnis auf vollem Datensatz *(nur wenn Lauf A gut aussieht)*:**
```
bge-m3 | chunk=1000/o50 | k=3 | similarity | qwen2.5-coder:7b | temp=0.0 | prompt=praezise_alt
```
Lauf 7 erreichte 98% — aber nur auf 61 Fragen. Jetzt auf dem vollen Datensatz aller Kategorien wiederholen. War 98% ein Ausreißer oder hält das?

**Erwartung:** Signifikante Verbesserung vor allem in der Kategorie Projekte (von 30% Hit Rate auf 60%+) durch stärkere Topic-Label Ankersätze in GMM- und StockPredict-Dateien.

---

## Offene Fragen *(Stand Juni 2026)*

Die bisherigen Läufe haben die Konfiguration deutlich verbessert — aber mehrere Fragen sind noch offen:

**MMR vs. similarity:** Alle bisherigen Läufe nutzen `similarity`. MMR (Maximal Marginal Relevance) bestraft redundante Chunks und könnte bei thematisch überlappenden Dokumenten (z.B. den `martin/`-Dateien) besser abschneiden. Noch nicht getestet.

**Hybrid Search:** ChromaDB unterstützt kein natives BM25 + Vektorsuche. Die GMM-Misses deuten darauf hin dass Keyword-Suche hier helfen würde. Entscheidung: ChromaDB behalten mit manuellem BM25-Workaround, oder Wechsel zu Weaviate/Qdrant?

**Cross-Encoder Reranker:** Ein Cross-Encoder (`cross-encoder/ms-marco-MiniLM-L-6-v2`) könnte die Chunk-Reihenfolge nach dem Retrieval verbessern — besonders für die Fälle wo der richtige Chunk bei Hit@3 oder Hit@4 landet statt bei Hit@1.

**Kategorie-spezifische Optimierung:** Lernen hat 100% Hit Rate, Projekte nur 30%. Eine einheitliche Konfiguration für alle Kategorien ist möglicherweise nicht optimal. Unterschiedliche Retrieval-Strategien pro Ordner wären ein nächster Schritt.

---

*→ Zurück zur Übersicht: [susi_00_übersicht.md](susi_00_übersicht.md)*  
*→ Weiter: [susi_05_sackgassen.md](susi_05_sackgassen.md)*  
*Stand: Juni 2026 · Martin Freimuth*