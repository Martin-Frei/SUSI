# SUSI Session-Log — 06.07.2026 — agent_datum, ValueCheck, dynamische Referenzen

## Überblick

Am 06.07.2026 wurden drei zusammenhängende Bausteine gebaut die SUSIs Umgang mit numerischen Fakten grundlegend ändern. **ValueCheck** deckt in der Eval-Pipeline auf wenn SUSI numerisch falsch antwortet — auch wenn die Antwort textlich fließend klingt. Der **Referenz-Loader** rendert Testfragen-Referenzen zur Laufzeit und verhindert dass zeitabhängige Testsets ab dem Folgetag veraltet sind. **agent_datum** ist SUSIs erstes Werkzeug im Sinne von Tool Use — reine Kalenderfragen werden deterministisch per Python `datetime` beantwortet, ohne LLM und ohne Retrieval.

Ausgangspunkt war der Befund vom 30.06. dass SUSI Kalenderrechnungen systematisch falsch beantwortet (Bug „SUSI seit März, wie alt? → 10 Monate" statt 3) und der Auto-Scorer diese Fehler mit BERT und ROUGE-L nicht erkennt (alle 10 Datumsfragen wurden fälschlich als korrekt bewertet). Am Ende des Tages: 8 von 10 Datumsfragen kalendarisch korrekt gelöst (vs. 0 vorher), Ø Quality-Score 2.00 (vs. 0.20 nach reinem ValueCheck), verbleibende zwei Fehler sind identifiziert und begründet.

---

## Neue Module

### `tools/evaluation/valuecheck.py`

Deterministische Prüf-Schicht die vor dem bisherigen ROUGE/BERT-Entscheidungsbaum im Auto-Scorer läuft. Extrahiert Zahlen, Daten und Wochentage aus Referenz und SUSI-Antwort und vergleicht sie direkt Wert gegen Wert. Drei mögliche Rückgaben: sicherer Fehler (Diagnostic Score 1, hart), sicher korrekt (gibt frei), Grauzone (geht an RAGAS/Haiku).

**Kernregeln:** keine Rundungstoleranz, eine falsche Zahl macht die ganze Antwort falsch, Extra-Zahlen werden ignoriert, unklare Fälle sind Grauzone.

**Erweiterungen:** Wochentage deutsch und englisch als eigene Wertklasse (Enum 1–7), deutsche Zahlwörter zwei bis zwölf (`ein/eine` bewusst ausgenommen wegen Artikel-Kollision), Jahres-Erkennung nur im Bereich 1990–2035 damit `chunk_size=1000` oder Port `11434` nicht als Jahr typisiert werden.

**Rollout-Schalter `VALUECHECK_HART`:** True setzt Wertefehler hart auf Diagnostic 1, False leitet sie als Grauzone an Haiku weiter. Zielzustand True, für gemischte Läufe mit Meta-Text in Referenzen ist False der sichere Fallback.

**Standalone testbar:**
```powershell
python tools\evaluation\valuecheck.py --referenz "Der 31.12.1999 war ein Freitag." --antwort "Das war ein Samstag."
```

### `tools/evaluation/test_valuecheck.py`

Validierungs-Harness der ValueCheck gegen eine bestehende Eval-CSV laufen lässt und pro Zeile das Urteil zeigt. Braucht kein Ollama — reine Logik-Prüfung. Wurde am 06.07. gegen `eval_20260630_1218_full.csv` genutzt zur Verifikation dass 7 von 8 faktisch falschen Antworten nicht mehr als korrekt durchgewunken werden.

### `tools/evaluation/referenz_loader.py`

Rendert dynamische Platzhalter in Testfragen-Referenzen zur Laufzeit. Wird von `grid_run.lade_fragen()` aufgerufen. Testfragen mit `referenz_template` (statt `referenzantwort`) werden vor der Verarbeitung durch den Loader geschickt und die Platzhalter durch aktuelle Werte ersetzt.

**Verfügbare Platzhalter:**

| Platzhalter | Ergebnis am 06.07.2026 |
|---|---|
| `{heute}` | 6. Juli 2026 |
| `{heute_kurz}` | 06.07.2026 |
| `{heute_iso}` | 2026-07-06 |
| `{heute_wt}` | Montag |
| `{heute+21}` | 27. Juli 2026 |
| `{heute+21_kurz}` | 27.07.2026 |
| `{heute+21_wt}` | Montag |
| `{heute-15}` | 21. Juni 2026 |
| `{tage_seit:2026-05-15}` | 52 |
| `{wochen_bis:2026-12-25}` | 24 |
| `{monate_seit:2026-03-20}` | 3 |

Fragen ohne Template bleiben unverändert. Unbekannte Platzhalter werfen keinen Fehler sondern bleiben stehen.

### `rag/agent_datum.py`

**SUSIs erstes Werkzeug im Sinne von Tool Use / Function Calling.** Erkennt reine Kalenderfragen und beantwortet sie deterministisch per Python `datetime`, ohne LLM und ohne Retrieval. Wird in `query.py` ganz früh in der Pipeline aufgerufen, direkt nach `detect_language()`.

**Konservative Drei-Bedingungen-Klassifikation** — alle müssen erfüllt sein:

1. Konkretes Datum oder Datums-Anker in der Frage (Datum, "heute", "Weihnachten JJJJ", "Silvester JJJJ")
2. Klare Kalender-Operation (Wochentag, Tage/Wochen/Monate zwischen, +N Tage/Wochen, übernächste Woche, ab heute)
3. Kein SUSIpedia-Entitätsname (nicht `susi`, `stockpredict`, `gmm`, `houseofstacks`, `hos`, `portfolio`, `martin`, `tanveer`, `adeena`, `mein/e`, `ich`, `projekt`, `firma`, `team`)

Im Zweifel → LLM+RAG. Der Agent macht nur was er sicher kann.

**Unterstützte Muster:** Wochentag eines Datums, Tage/Wochen/Monate zwischen zwei Daten, N Tage/Wochen ab heute, nächste/übernächste Woche, Tage/Wochen/Monate seit einem Datum, Tage/Wochen/Monate bis zu einem Datum.

**Standalone testbar:**
```powershell
python rag\agent_datum.py --demo
python rag\agent_datum.py --frage "Welcher Wochentag ist der 25.12.2026?"
```

---

## Geänderte Module

### `tools/evaluation/auto_scorer.py`

Neue Signatur `berechne_auto_score(..., referenz=None)` — rückwärtskompatibel, ohne Referenz verhält sich die Funktion exakt wie vorher. ValueCheck läuft zwischen Ausweich-Check (Schritt 1) und ROUGE-BERT-Baum (Schritt 3). Standalone-CSV-Analyse liest die Referenz aus der `referenzantwort`-Spalte.

**Zentrale Konstante `DIAG_ZU_QUALITAET`** eingeführt als Single Source of Truth für das Diagnostic-zu-Quality Mapping (0→0, 1→0, 2→1, 3→2, 4→0, 5→0). Vorher lag dieses Dict dreifach dupliziert in `grid_run.py`, `ragas_scorer.py` und `analyse_csv.py`. `grid_run` importiert es jetzt von hier, die anderen zwei behalten vorerst ihre Kopien (Hygiene-Refactoring später).

### `tools/evaluation/grid_run.py`

Drei Änderungen: `referenz=frage_data.get("referenzantwort", "")` als zusätzliches Argument an `berechne_auto_score()`. Import von `DIAG_ZU_QUALITAET` aus `auto_scorer` statt lokal dupliziertem Dict. `lade_fragen()` ruft `referenz_loader.rendere_frage()` auf und schreibt bei aktivem Template einen Konsolen-Hinweis `📅 Dynamische Referenzen gerendert (heute=...)`.

### `rag/query.py`

**`ask_susi()` bekommt `mode`-Parameter mit Default `"auto"`** — behebt den 500-Fehler `TypeError: ask_susi() got an unexpected keyword argument 'mode'` der auftrat weil `views.py` seit dem Frontend-Update den Chat-Modus durchreichte. Docstring beschreibt jetzt alle drei Modi: `auto` (Standard, Router aktiv, agent_datum darf greifen), `manuell` (User kontrolliert Modell/top_k/temp/num_ctx/Prompt selbst, kein Agent), `coding` (Ingest-Vorbereitung: SUSI verarbeitet ein Dokument für ingest.py, kein Agent).

**agent_datum-Aufruf in `ask_susi()`** direkt nach `detect_language()`, vor `rewrite_query()`. Aktiv nur bei `mode=="auto"` UND `lang=="de"` UND `agent_datum.ist_kalenderfrage(question)`. Bei Treffer wird ein vollständiges Antwort-Dict zurückgegeben mit `llm_model="agent_datum"`, `router_profil="agent_datum"`, `quelldateien=["🧮 agent_datum (deterministisch)"]`. Frontend rendert das automatisch als sichtbare Quelle, ohne HTMX-Änderung.

**agent_datum-Aufruf auch in `ask_susi_eval()`** — dort ohne `mode`-Guard, damit `grid_run` den Produktionszustand testet.

### `tools/evaluation/testfragen_datumsarithmetik.json` (Version 2.0)

Sechs Fragen bekommen `referenz_template` statt statischer `referenzantwort` (datum_01, 02, 03, 04, 08, 10). Vier bleiben statisch (datum_05 und 06 sind absolute Kalenderfakten, datum_07 ist ein Schaltjahr-Fakt, datum_09 ein logischer Vergleich ohne Zeitbezug). Metadaten-Version auf 2.0 hochgezogen, Änderungsdatum vermerkt.

---

## Ergebnisse — Vorher-Nachher-Vergleich

Vier Läufe gegen dasselbe Datumsarithmetik-Testset:

| Zeitpunkt | Setup | Ø Quality | Ø BERT | Ø ROUGE-L |
|---|---|---|---|---|
| 30.06. Vormittag | alter Auto-Scorer, hartcodierte Refs | 2.0 (falsch) | 0.70 | 0.16 |
| 06.07. 10:46 | + ValueCheck | 0.20 | 0.77 | 0.31 |
| 06.07. 11:35 | + dynamische Referenzen | 0.40 | 0.77 | 0.31 |
| **06.07. 23:28** | **+ agent_datum** | **2.00 (verdient)** | **0.89** | **0.71** |

Die 2.00 am 30.06. waren blindes Durchwinken — alle 10 Fragen bekamen fälschlich Score 3 weil BERT/ROUGE die Fehler nicht erkannten. Die 2.00 am 23:28 sind verdient: 8 von 10 Fragen kalendarisch korrekt gelöst (`Max BERT = 1.000` und `Max ROUGE-L = 1.000` markieren die bit-identischen Agent-Antworten), 2 Fragen bewusst als Fehler oder außerhalb Scope erkannt.

**Verbleibende Nicht-2er:**

- **datum_01** — LLM-Pfad (Entität `SUSI`), SUSI antwortete „4 Jahre und 3 Monate alt" statt „3 Monate". ValueCheck fing es korrekt als Score 1. Zusätzlicher Beobachtung: der Query Rewriter macht aus „wie alt ist SUSI" die verzerrende Frage „wie viele Jahre ist SUSI in Betrieb" — das primt das LLM in die falsche Einheit.
- **datum_09** — LLM-Pfad, logischer Fehler bei identischen Zahlen (Januar 2026 vs. März 2026). Bewusst außerhalb ValueCheck-Scope, BERT/ROUGE übernehmen.

---

## Was jetzt architektonisch anders läuft

### Werkzeug-Routing vor dem RAG-Routing

Bis heute entschied nur der Router in `router.py` welches LLM-Profil ran soll. Ab jetzt gibt es eine Ebene davor: „soll überhaupt ein LLM ran?" Diese Ebene ist deterministisch und für spätere Werkzeuge erweiterbar. Der Datums-Agent ist das erste Werkzeug, weitere (Britannica-Agent, PDF-Agent) können analog gebaut werden.

**Struktur unter `rag/`:**

```
rag/
├── agent_datum.py       ← NEU: erstes Werkzeug
├── query.py             ← Produktions-Pipeline
├── router.py            ← RAG-Router (Profil-Wahl innerhalb LLM-Pfad)
├── susi_config.yaml
└── ingest.py
```

Namenskonvention `agent_*.py` — künftige Werkzeuge sortieren alphabetisch mit zusammen und sind auf einen Blick als Agent-Familie erkennbar.

### Frontend zeigt Werkzeug-Herkunft

Wenn `agent_datum` greift, sieht der User im Frontend:
- Quelle: `🧮 agent_datum (deterministisch)`
- LLM: `agent_datum`
- Antwortzeit: unter 0.01 Sekunden statt 4–8 Sekunden
- Tokens: 0

Kein HTMX-Update nötig — die bestehenden Anzeigen für `llm_model`, `quelldateien` und `antwortzeit_sek` rendern die Agent-Werte einfach mit.

### Eval-Pipeline testet Produktionszustand

`ask_susi_eval()` ruft den Agenten mit auf — ohne `mode`-Guard, weil grid_run keinen Modus setzt. Damit spiegelt jeder Live-Lauf exakt das Verhalten wider das der Nutzer im Frontend erlebt.

---

## SUSIpedia-Änderungen

**Neu erstellt:** `docs/susi/valuecheck_und_referenz_loader.md` — thematische Doku über ValueCheck, den Referenz-Loader und die Integration im Auto-Scorer. SUSIpedia-konform mit Topic-Label-Ankersätzen pro `##`. Nach `docs/susi/` legen und mit `python rag\ingest.py` einpflegen.

**Gelöscht:** `docs/technik/susi_grenzen_und_roadmap.md` — Stale-Duplikat entdeckt beim Audit vom Vormittag. Enthielt noch die veraltete Aussage „llama3.1:8b als aktuelle Konfiguration". Wurde im Datumsarithmetik-Test tatsächlich retrieved. `docs/technik/` enthält jetzt nur noch `rag_einstellungen.md` — bestätigt gleichzeitig dass die Kategorie technisch inhaltlich ausgebaut werden muss (schwächste Kategorie in Lauf F mit 60%).

**Zusätzlich empfohlen:** neue thematische Doku `docs/susi/agent_datum.md` mit Konzept, Klassifikationsregeln und Ausblick auf Zweig 2. Aktuell nur der Docstring im Modul selbst.

---

## Neu aufgetauchte Bugs und Beobachtungen

**Rewriter macht aus „wie alt ist SUSI" die Frage „wie viele Jahre ist SUSI in Betrieb"** — reproduziert bei datum_01 im Lauf um 23:28. Der Rewriter primt das LLM damit in die Einheit Jahre obwohl es nur um Monate geht. Das erklärt vermutlich einen Teil der bisherigen Fehleinheiten-Probleme („10 Monate" statt „3 Monate" konnte auch daran gelegen haben). Fix im Rewriter-Prompt nötig: keine Einheit annehmen die nicht in der Ursprungsfrage steht.

**Rewriter-Bug „übernächste Woche" wird zu „nächste Woche"** — unverändert offen aus dem Handoff vom 23.06. Betrifft aber ab jetzt nur noch datum_08 im LLM-Pfad — im Agent-Pfad läuft die Frage komplett am Rewriter vorbei.

**`--nachbewertung`-Skala inkonsistent** — akzeptiert 0–2 während das System mit der Diagnostic-Skala 0–5 arbeitet. Steht seit 23.06. offen, mit der zentralen Mapping-Konstante `DIAG_ZU_QUALITAET` gibt es jetzt eine sinnvolle Anlaufstelle für die Vereinheitlichung.

**`ragas_scorer.py` verliert `auto_score`-Werte** bei gestapelten CSVs — Fix steht aus, in Lauf E fehlten dadurch 50 von 586 Scores.

---

## Nächste Schritte, priorisiert

**Sofort** — Rewriter-Nachbesserung: keine Einheit annehmen die in der Ursprungsfrage nicht vorkommt. Das würde datum_01 mit hoher Wahrscheinlichkeit auf Score 2 heben.

**Kurzfristig** — Agent-Zweig 2 bauen: für Fragen mit Entitätsbezug (wie datum_01 „SUSI seit März") das relevante Datum aus dem retrievten Chunk extrahieren, Differenz in Python vorberechnen und als fertigen Fakt ins Prompt injizieren. Das LLM muss dann nur noch formulieren, nicht mehr rechnen.

**Kurzfristig** — Konsolen-Marker `📅 Dynamische Referenzen gerendert` läuft aktuell in `lade_fragen()` vor dem Reranker-Loading und scrollt oben raus. Bei Bedarf ans Ende der Konsolen-Zusammenfassung verschieben damit sichtbar bleibt dass der Loader gegriffen hat.

**Kurzfristig** — `ragas_scorer` Stacked-CSV-Bug fixen, `--nachbewertung`-Skala vereinheitlichen.

**Mittelfristig** — Voting-Schwellen im Router optimieren (Router-Accuracy weiter bei rund 70%, teils sehr niedrige Voting-Scores 0.04 bis 0.21). Britannica-API mit neuem Profil `wissen` und Ordner `docs/wissen/`. PDF-RAG mit temporärem Index.

**Zweiter Agent** — bewusst noch nicht spezifiziert. Wenn Britannica dran ist wäre das der logische Kandidat: `agent_britannica.py` mit derselben `ist_zustaendig()` / `beantworte()`-Schnittstelle wie agent_datum. Vorher aber datum-Zweig 2 fertigmachen.

---

## Wichtige Dateipfade — Stand 06.07.2026

**Neu unter `tools/evaluation/`:** `valuecheck.py`, `test_valuecheck.py`, `referenz_loader.py`.

**Neu unter `rag/`:** `agent_datum.py`.

**Geändert:** `tools/evaluation/auto_scorer.py`, `tools/evaluation/grid_run.py`, `rag/query.py`, `tools/evaluation/testfragen_datumsarithmetik.json`.

**Neu unter `docs/susi/`:** `valuecheck_und_referenz_loader.md`.

**Gelöscht unter `docs/technik/`:** `susi_grenzen_und_roadmap.md` (Stale-Duplikat).

**Ergebnis-CSVs des Tages:**
- `tools/evaluation/results/eval_20260706_1046_full.csv` — mit ValueCheck, hartcodierte Refs
- `tools/evaluation/results/eval_20260706_1135_full.csv` — mit ValueCheck + dynamischen Refs
- `tools/evaluation/results/eval_20260706_2328_full.csv` — mit ValueCheck + dynamischen Refs + agent_datum (Referenzstand)

**Live-Eval starten:**
```powershell
python tools\evaluation\grid_run.py --config tools\evaluation\eval_config_lauf_f.yaml --live --fragen tools\evaluation\testfragen_datumsarithmetik.json --mode full
```

**Django starten:**
```powershell
python manage.py runserver
```

---

Stand: 06.07.2026 · Martin Freimuth
