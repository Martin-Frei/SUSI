# 03 — SUSIpedia — Die Wissensbasis
### SUSI Entwicklungsbericht · Stand Juni 2026

---

## Was ist SUSIpedia?

SUSIpedia ist das Langzeitgedächtnis von SUSI. Es ist eine strukturierte Sammlung von Markdown-Dateien, die als einzige Wissensquelle für das RAG-System dient. Das Sprachmodell selbst weiß nichts über Martin, seine Projekte, seine Ziele oder seine Lernfortschritte — alles was SUSI darüber weiß kommt aus SUSIpedia.

Der entscheidende Designgedanke dahinter:

> *Das Sprachmodell ist austauschbar. SUSIpedia ist das eigentliche Asset.*

Wer SUSIpedia besitzt ist unabhängig davon welches Modell morgen besser ist. Das Wissen gehört dem Nutzer, nicht dem Anbieter.

**Wichtig zur Dokumentstruktur:** Die Formatierungsregeln optimieren primär für maschinelles Retrieval — Chunk-Grenzen, Vektordistanz, semantische Eindeutigkeit. Das bedeutet nicht dass Lesbarkeit geopfert wird. Guter Fließtext ist gleichzeitig gut retrievbar und gut lesbar. Retrieval-Optimierung und menschliche Lesbarkeit sind kein Widerspruch — sie werden durch dieselben Regeln erreicht.

---

## Die Ordnerstruktur

SUSIpedia ist in Lebensbereiche gegliedert. Die Struktur folgt nicht technischen Konventionen sondern inhaltlicher Logik — jeder Ordner entspricht einem klar abgegrenzten Lebens- oder Arbeitsbereich.

```
docs/
├── susipedia_formatierungsregeln.md   ← Formatregeln für alle Dateien
├── susi_vision.md                     ← Langfristige Vision
├── tree.md                            ← Strukturübersicht
│
├── coding/                            ← Technische Projekte
│   ├── gmm/                           ← Global Market Mood
│   ├── houseofstocks/                 ← HouseOfStocks Projekt
│   ├── portfolio/                     ← Portfolio Website
│   ├── stockpredict/                  ← StockPredict V2
│   └── susi/                          ← SUSI selbst
│
├── projekte/                          ← Projektübersichten
│   ├── gmm/                           ← GMM Detaildoku
│   ├── spv2/                          ← StockPredict V2 Detaildoku
│   └── pc_umbau/                      ← Hardware-Planung
│
├── technik/                           ← Technische Konfiguration
│   ├── rag_einstellungen.md
│   └── susi_grenzen_und_roadmap.md
│
├── lernen/                            ← Lernmaterial [nicht öffentlich]
├── martin/                            ← Persönliche Daten [nicht öffentlich]
├── job/                               ← Bewerbungen [nicht öffentlich]
├── familie/                           ← Familiäres [nicht öffentlich]
├── hobbys/                            ← Hobbys [nicht öffentlich]
├── tagebuch/                          ← Persönliches [nicht öffentlich]
└── persoenlich/                       ← Reflexionen [nicht öffentlich]
```

**Stand 10.06.2026:** Die Wissensbasis umfasst 124 indexierte Markdown-Dateien über alle Bereiche. Die vollständige Überarbeitung aller Dateien nach den aktuellen Formatierungsregeln wurde am 10.06.2026 abgeschlossen — ein mehrstündiger manueller Prozess der die Retrieval Hit Rate von 36% auf 91% angehoben hat. Davon sind `coding/`, `projekte/` und `technik/` öffentlich auf GitHub einsehbar. Alle anderen Bereiche sind bewusst ausgeschlossen.

→ *GitHub-Strategie und Datensicherheit: siehe Abschnitt unten*

---

## Formatierungsregeln — das Fundament der Retrieval-Qualität

Die Formatierungsregeln sind nicht optional. Sie sind der Grund warum SUSIpedia funktioniert.

Die vollständigen Regeln sind in `docs/susipedia_formatierungsregeln.md` dokumentiert und öffentlich einsehbar. Hier die wichtigsten Prinzipien im Überblick:

**Eine Datei — ein Thema:** Jede Datei behandelt genau ein klar abgegrenztes Thema. Ein Dokument das drei Projekte beschreibt wird in drei Dateien aufgeteilt. Das ist keine Konvention — es ist eine RAG-Anforderung.

**Maximal drei Heading-Ebenen:** H1 = Dateititel (einmal pro Datei). H2 = ein Konzept = ein Chunk in ChromaDB. H3 = Detail zum darüberliegenden Abschnitt, nur wenn nötig. H4 und tiefer werden nie verwendet.

**Topic-Label Ankersatz:** Jeder H2-Abschnitt muss im ersten Satz seinen vollständigen Kontext nennen. Da ChromaDB jeden Chunk ohne das restliche Dokument speichert muss der Chunk alleine verständlich sein. Falsch: "Es besteht aus drei Layern." Richtig: "Die StockPredict V2 Architektur besteht aus drei Layern: DataHandler, MasterEngineer und Enrichment Pipeline."

**Fließtext statt Listen:** Alle Informationen werden in vollständigen Sätzen geschrieben. Kompakte Listen retrieven schlecht weil Embedding-Modelle auf natürliche Sprache optimiert sind. Technische Kurznotationen erzeugen Vektoren die semantisch wenig Überlappung mit natürlichsprachlichen Suchanfragen haben.

**Keine Markdown-Tabellen:** Tabellen werden beim Chunking zerrissen und retrieven schlecht — Tabellenzellen sind zu kurze, kontextfreie Fragmente. Markdown-Tabellen werden in Fließtext umgewandelt. Erlaubt sind jedoch JSON- und YAML-Codeblöcke für echte strukturierte Daten (Konfigurationsparameter, API-Formate, Enum-Definitionen). Bedingung: jeder Codeblock muss von einem H2-Ankersatz und erklärender Prosa umgeben sein. Das Embedding-Modell greift die Prosa für Retrieval, das LLM greift den Codeblock für Generierung.

**Abkürzungen konsistent:** Beim ersten Vorkommen ausschreiben, danach einheitlich. "Global Market Mood (GMM)" beim ersten Mal, danach immer "GMM". Mischen führt zu schlechter Verknüpfung in ChromaDB.

→ *Vollständige Regeln: `docs/susipedia_formatierungsregeln.md`*

---

## Der Qualitätssicherungsprozess

SUSIpedia wächst kontinuierlich. Ohne Qualitätssicherung würde die Retrieval-Qualität mit jeder neuen Datei schlechter statt besser. Deshalb wurde früh ein systematischer Prüfprozess eingeführt.

**check_docs_quality.py** ist ein automatisierter Checker der jede Markdown-Datei gegen die Formatierungsregeln prüft:

- Gibt es einen H1-Titel?
- Sind Metadaten (Datum, Status) vorhanden?
- Gibt es Topic-Label Ankersätze in jedem H2-Abschnitt?
- Gibt es Bullet-Listen die in Fließtext umgewandelt werden müssen?
- Gibt es Tabellen?
- Gibt es H4 oder tiefere Headings?
- Sind Encoding-Fehler vorhanden?

**Was der Checker nicht erkennt:** Inhaltliche Fehler. Veraltete Informationen. Ob der Dateiinhalt zum Dateinamen passt. Ob Inhalte zwischen Dateien vertauscht wurden. Das sind Lücken die nur manuelles Review aufdeckt.

---

## Die 5 größten Qualitätsprobleme — Ursache und Lösung

### Problem 1: Encoding-Fehler (UTF-8 / Windows)

**Was passiert:** Umlaute (ä, ö, ü, ß) erscheinen als unleserliche Zeichenketten wie `ï¿½` oder `\ufffd`. Ursache ist eine doppelte Enkodierung — eine Datei wird als Latin-1 gelesen aber als UTF-8 gespeichert oder umgekehrt. Das passiert besonders leicht wenn Dateien zwischen Windows-Programmen (Notepad, Word) und dem Python-Stack hin- und herkopiert werden.

**Konsequenz:** Betroffene Chunks sind für das Embedding-Modell semantisch wertlos. Das Retrieval findet den Chunk nicht oder liefert einen falschen.

**Lösung:** `UMLAUT_FIXES` — eine Replacement-Liste die bekannte falsch-enkodierte Sequenzen durch die korrekte Schreibweise ersetzt. Wird bei der Ingestion automatisch angewendet. Zusätzlich: alle neuen Dateien werden explizit mit `encoding="utf-8"` geschrieben und gelesen.

### Problem 2: Bullet-Listen statt Fließtext

**Was passiert:** Informationen werden als kompakte Liste geschrieben weil das intuitiv platzsparend und übersichtlich wirkt. Für das RAG-System ist es kontraproduktiv.

**Konsequenz:** Jeder Listenpunkt ist zu kurz um semantischen Kontext zu tragen. bge-m3 findet den Chunk nicht wenn die Suchanfrage anders formuliert ist als der Listenpunkt. Das ist kein Modellproblem — es ist ein Dokumentationsproblem.

**Lösung:** Konsequente Umschreibung aller Listen in Fließtext. Der Checker markiert alle Bullet-Listen zur manuellen Überarbeitung.

### Problem 3: Fehlende Topic-Label Ankersätze

**Was passiert:** Ein H2-Abschnitt beginnt direkt mit dem Inhalt ohne den Kontext zu nennen. Beispiel: Abschnitt "Deployment" beginnt mit "Es läuft auf Railway mit PostgreSQL." — unklar ist welches Projekt gemeint ist.

**Konsequenz:** ChromaDB speichert den Chunk ohne Kontext. Bei einer Suchanfrage zu StockPredict Deployment kann der Chunk dem falschen Projekt zugeordnet werden — besonders wenn mehrere Projekte ähnliche Keywords teilen.

**Lösung:** Jeder H2-Abschnitt muss im ersten Satz Projektname oder Thema explizit nennen. Der Checker prüft ob der erste Satz des Abschnitts einen der bekannten Projektnamen enthält.

### Problem 4: Veraltete technische Angaben

**Was passiert:** Modellnamen, Hardware-Angaben und Konfigurationswerte werden in Dateien eingetragen und dann nicht aktualisiert wenn sich das System weiterentwickelt.

**Konsequenz:** SUSI liefert veraltete Informationen als Fakten. Wenn in drei Dateien noch `nomic-embed-text` steht obwohl das System auf `bge-m3` umgestellt wurde gibt SUSI die falsche Antwort — mit voller Überzeugung.

**Lösung:** Bei jeder Architekturänderung werden alle betroffenen Dateien systematisch geprüft und aktualisiert. Der Retrieval Check hilft dabei Inkonsistenzen zu erkennen weil falsche Angaben zu Miss-Ergebnissen führen.

### Problem 5: H3-Überschriften und Code-Blöcke in Nicht-Code-Docs

**Was passiert:** Technische Dokumente verwenden zu viele Heading-Ebenen und eingebetteten Code der sich nicht selbst erklärt.

**Konsequenz:** H3 erzeugt zu kleine Chunks ohne ausreichend semantischen Kontext. Code-Blöcke retrieven schlecht weil sie syntaktisch aber nicht semantisch formuliert sind.

**Lösung:** Code-Blöcke sind nicht verboten — aber jeder Code-Block muss von einem H2-Ankersatz und erklärender Prosa begleitet sein. Steht ein Code-Block ohne Kontext ist das ein Signal dass die Erklärung fehlt, nicht dass der Code entfernt werden muss. Der Code kommt ins Repository — die Erklärung kommt in die SUSIpedia.

---

## Erkannte und behobene Inhaltsfehler *(Juni 2026)*

Zwei Fehler wurden durch manuelles Review entdeckt die der automatische Checker nicht erkennen kann:

**Vertauschte Dateiinhalte:** `enricher.md` und `enricher_lokal.md` hatten ihren Inhalt gegenseitig vertauscht — wahrscheinlich beim manuellen Kopieren passiert. Das Risiko war hoch: SUSI hätte bei einer Frage zu `enricher.py` die Antwort aus `enricher_lokal.py` geliefert — inhaltlich falsch aber syntaktisch plausibel, also ohne Gegenwissen schwer zu erkennen. **Behoben.**

**Duplikat-Datei:** `simulate_top_n_hg.md` war ein exaktes Duplikat von `supabase_service.md` mit falschem Dateinamen. Doppelte Chunks für denselben Inhalt verzerren die Similarity Scores — der richtige Chunk gewinnt öfter als er sollte, der falsche wird verdrängt. **Behoben.**

Diese Fälle zeigen eine strukturelle Lücke im Qualitätsprozess: der Checker prüft Format, nicht Inhalt. Ein Content-Hash-Vergleich zwischen Dateiname und H1-Titel wäre eine sinnvolle Erweiterung.

---

## Datensicherheit und GitHub-Strategie

SUSIpedia enthält sensible persönliche Daten — Lebenslauf, Familiendaten, Bewerbungsunterlagen, persönliche Reflexionen. Diese Daten dürfen nicht in ein öffentliches Repository.

### Was öffentlich ist

```
docs/projekte/          ✅ öffentlich
docs/coding/            ✅ öffentlich
docs/technik/           ✅ öffentlich
docs/susipedia_formatierungsregeln.md  ✅ öffentlich
docs/susi_vision.md     ✅ öffentlich
docs/tree.md            ✅ öffentlich — zeigt die Struktur ohne sensible Inhalte
```

### Was nicht öffentlich ist

```
docs/martin/            ❌ Lebenslauf, Ziele, Profil
docs/familie/           ❌ Familiäre Daten
docs/job/               ❌ Bewerbungen, Jobsuche
docs/lernen/            ❌ Interview-Vorbereitung, persönliche Lernmaterialien
docs/hobbys/            ❌ Persönliche Interessen
docs/tagebuch/          ❌ Persönliche Reflexionen
docs/persoenlich/       ❌ Private Gedanken
docs/skills/            ❌ Bewerbungs-Skills
docs/finanzen/          ❌ Finanzielle Daten
docs/wohnen/            ❌ Wohnsituation
docs/freunde/           ❌ Kontakte
```

### Die .gitignore Whitelist-Strategie

Statt einzelne sensible Ordner auszuschließen wird eine Whitelist-Strategie verwendet — alles in `docs/` wird ignoriert außer den explizit erlaubten Pfaden:

```gitignore
# Gesamten docs/ Ordner ignorieren
docs/*

# Nur diese Pfade explizit erlauben
!docs/projekte/
!docs/projekte/**
!docs/coding/
!docs/coding/**
!docs/technik/
!docs/technik/**
!docs/susipedia_formatierungsregeln.md
!docs/susi_vision.md
!docs/tree.md
```

Der Vorteil: Neue Ordner in `docs/` werden automatisch ignoriert ohne dass `.gitignore` angepasst werden muss. Das Sicherheitsprinzip gilt also auch für zukünftige Inhalte.

### History-Bereinigung *(durchgeführt Juni 2026)*

Da sensible Dateien bereits in der Git-History existierten reichte ein `.gitignore`-Eintrag nicht aus — die Dateien wären weiterhin in der History abrufbar gewesen. Die Bereinigung erfolgte mit `git filter-repo`:

```powershell
git filter-repo --path docs/projekte/ --path docs/coding/ --path docs/technik/ --path docs/susipedia_formatierungsregeln.md --path docs/susi_vision.md --path docs/tree.md --force
```

Danach wurde die Remote-Verbindung neu gesetzt und die bereinigte History mit `--force` auf GitHub gepusht. Alle sensiblen Dateien sind damit aus der kompletten Git-History entfernt — als wären sie nie committed worden.

---

*→ Zurück zur Übersicht: [susi_00_übersicht.md](susi_00_übersicht.md)*  
*→ Weiter: [susi_04_evaluation.md](susi_04_evaluation.md)*  
*Stand: Juni 2026 · Martin Freimuth*