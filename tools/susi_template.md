# SUSI SUSIpedia Template
<!-- 
    Dieses Template definiert wie eine SUSIpedia Markdown-Datei aufgebaut
    sein muss damit SUSI sie zuverlässig abrufen kann.
    
    WICHTIG: Dieses File selbst gehört NICHT in docs/ sondern in A_documentation/ oder tools/.
-->

---

## Aufbau einer SUSIpedia Datei

Eine SUSIpedia Datei besteht aus einem klaren Thema pro Datei,
maximal drei Ebenen tief (Lebensbereich → Projekt → Aspekt) und
ausschließlich vollständigen Sätzen statt kompakter Listen.

---

## Datei-Header

Jede Datei beginnt mit einem `#` Titel der das Thema klar benennt,
gefolgt von Datum und Status damit SUSI den zeitlichen Kontext kennt.

```
# Thema – Untertitel
**Datum:** TT.MM.JJJJ
**Status:** aktiv / abgeschlossen / in Arbeit
```

---

## Abschnitt-Struktur

Jeder `##` Abschnitt beschreibt genau einen Aspekt des Themas.
Der Abschnitt beginnt immer mit einem erklärenden Satz der das Thema
einleitet bevor Details folgen. Mindestens 80 Zeichen Prosa pro Abschnitt.

```
## Abschnittstitel

Einleitender Satz der erklärt worum es in diesem Abschnitt geht.
Dann folgen weitere Sätze mit den Details. Immer vollständige Sätze,
niemals nur Stichpunkte oder kompakte Ausdrücke.
```

---

## Prosa statt Listen — die wichtigste Regel

Das Embedding-Modell nomic-embed-text kann Listen schlecht als Vektoren
abbilden. Vollständige Sätze werden dagegen zuverlässig gefunden.

**Falsch — wird nicht gefunden:**
```
## Tanzstile
- Walzer
- Salsa
- Bachata
```

**Richtig — wird zuverlässig gefunden:**
```
## Tanzstile

Martin tanzt folgende Tanzstile: Walzer, Salsa und Bachata.
Der Walzer gehört zu den Standard-Tänzen und wird im Tanzsport
auf internationalem Niveau getanzt. Salsa und Bachata sind
lateinamerikanische Tänze die Martin in der Freizeit tanzt.
```

---

## Tabellen vermeiden

Tabellen sind für RAG-Retrieval ungeeignet weil das Embedding-Modell
die Spalten-Struktur nicht als zusammenhängenden Text versteht.
Stattdessen den Inhalt als Fließtext formulieren.

**Falsch — Tabelle:**
```
| Modell | VRAM | Qualität |
|--------|------|----------|
| 7B     | 4GB  | mittel   |
| 70B    | 24GB | hoch     |
```

**Richtig — Fließtext:**
```
Das 7B Modell benötigt 4GB VRAM und liefert mittlere Qualität.
Das 70B Modell benötigt 24GB VRAM und liefert hohe Qualität.
```

Falls eine Tabelle unvermeidbar ist muss davor ein erklärender
Satz stehen der den Inhalt der Tabelle zusammenfasst.

---

## Codeblöcke

Codeblöcke sind für Embeddings bedeutungslos ohne Kontext.
Vor jedem Codeblock muss ein erklärender Satz stehen der
erklärt was der Code macht und warum er relevant ist.

**Falsch:**
```
def ask_susi(question):
    ...
```

**Richtig:**
```
Die Funktion ask_susi() nimmt eine Frage entgegen, sucht die
relevanten Chunks in ChromaDB und gibt die Antwort des LLM zurück.

def ask_susi(question):
    ...
```

---

## Kommentar-Blöcke

Abschnitte die nicht in ChromaDB indexiert werden sollen werden
mit `##**` und `**##` gewrappt. Typische Anwendungsfälle sind
offene Punkte, temporäre Notizen oder persönliche Kommentare
die für SUSI nicht relevant sind.

```
##** Offene Punkte
- Task A der noch erledigt werden muss
- Task B der noch aussteht
**##
```

Alles zwischen `##**` und `**##` wird von ingest.py übersprungen
und landet nicht in ChromaDB. Der Inhalt bleibt in der Datei erhalten
und ist weiterhin als persönliche Notiz lesbar.

---

## Chunk-Größen und Abschnittslänge

ingest.py verwendet unterschiedliche Chunk-Größen je nach Ordner.
Technische Ordner (coding/, technik/, lernen/) verwenden 500 Zeichen
pro Chunk mit 100 Zeichen Overlap. Persönliche Ordner verwenden
300 Zeichen pro Chunk mit 50 Zeichen Overlap.

Ein `##` Abschnitt sollte mindestens 80 Zeichen Prosa enthalten
damit ein sinnvoller Chunk entsteht. Nach oben gibt es keine harte
Grenze, aber pro Abschnitt maximal 300 Wörter (persönlich) bzw.
500 Wörter (technisch) für optimale Chunk-Qualität.

---

## Vollständiges Beispiel

Das folgende Beispiel zeigt eine korrekt aufgebaute SUSIpedia Datei
für ein Coding-Projekt. Alle Regeln sind eingehalten.

```markdown
# StockPredict V2 – Überblick
**Datum:** 08.03.2026
**Status:** aktiv

## Was ist StockPredict V2

StockPredict V2 ist ein lokales Machine-Learning-System das
Aktienkurse mit LSTM und XGBoost vorhersagt. Das System läuft
vollständig lokal auf Martins Rechner ohne Cloud-Abhängigkeiten.

## Architektur

Die Pipeline besteht aus drei Hauptkomponenten. Der Fetcher lädt
täglich neue Kursdaten von Yahoo Finance. Der Enricher berechnet
technische Indikatoren wie RSI, MACD und Bollinger Bands. Das
LSTM-Modell trainiert auf den angereicherten Daten und gibt
eine Vorhersage für den nächsten Handelstag aus.

## Aktuelle Performance

Das Modell erreicht auf dem Testset eine Accuracy von 67% bei
der Richtungsvorhersage. Die durchschnittliche Abweichung vom
tatsächlichen Kurs beträgt 2.3%.

##** Offene Punkte
- XGBoost Refiner noch nicht integriert
- Backtesting fehlt noch
**##

## Nächste Schritte

Als nächstes wird der XGBoost Refiner integriert der die
LSTM-Vorhersagen nachkorrigiert. Danach folgt ein vollständiger
Backtest über die letzten 12 Monate.
```

---

## Checkliste vor dem Speichern

Vor dem Speichern einer neuen SUSIpedia Datei alle Punkte prüfen.
Vollständige Sätze statt Listen — jeder Abschnitt besteht aus
ausgeschriebenen Sätzen. Tabellen wurden vermieden oder haben
eine erklärende Einleitung davor. Codeblöcke haben einen
Kontext-Satz davor der erklärt was der Code macht.
Kommentar-Blöcke sind mit `##**` und `**##` gewrappt.
Jeder Abschnitt hat mindestens 80 Zeichen Prosa.
Die Datei liegt im richtigen Ordner gemäß der Struktur
Lebensbereich → Projekt → Aspekt.

Nach dem Speichern `python rag/ingest.py` ausführen damit
die neue Datei in ChromaDB indexiert wird. Optional danach
`python tools/check_docs_quality.py` zur Qualitätskontrolle.


## Qualitätsregeln

- Keine Abkürzungen ohne Ausschreibung beim ersten Vorkommen
  ✅ RAG (Retrieval-Augmented Generation)
  ✅ Global Market Mood (nicht GMM)
  ❌ RAG alleine
  ❌ GMM

- Vollständige Sätze statt Listen (Retrieval-Qualität)
- Aktives Datum und Status am Anfang