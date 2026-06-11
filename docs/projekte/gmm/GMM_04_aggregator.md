# Global Market Mood – aggregator.py

**Kategorie:** Projekt  
**Projekt:** Global Market Mood (GMM)  
**Stand:** 22.05.2026  
**Status:** Aktiv  

## Zweck von aggregator.py in Global Market Mood

aggregator.py liegt unter `marketmood/pipeline/aggregator.py` und übernimmt als Schritt 4 von 5 die Berechnung des regionalen Scores. aggregator.py nimmt alle analysierten Artikel und destilliert daraus einen einzigen numerischen Score pro Region — den Global Market Mood Score. Dieser Score ist das Herzstück der Weltkarte und des Dashboards.

## Die zentrale Design-Entscheidung Option B in aggregator.py

Option A in aggregator.py ist ein naiver Artikel-Durchschnitt mit einem Dominanz-Problem: wenn zu einem Thema 40 Artikel erscheinen und zu Finanzmärkten nur 5 dominiert Geopolitics den Score zu 88%. Option B berechnet zuerst den Durchschnitt pro Topic dann den Durchschnitt der Topic-Scores. Jedes Topic zählt genau einmal. Die Analogie: statt den Durchschnitt aller Schulnoten zu berechnen wo ein Fach mit 10 Tests dominiert berechnet man zuerst die Note pro Fach dann den Schnitt der Fachnoten. Option B ist implementiert, Option A wurde abgelehnt.

## _score_to_label Funktion in aggregator.py

Die Funktion `_score_to_label()` in aggregator.py konvertiert den Score in bullish, bearish oder neutral. Sie ist identisch zu get_label() in sentiment.py aber bewusst dupliziert damit aggregator.py keine Import-Abhängigkeit zu sentiment.py hat.

## _topic_scores Funktion in aggregator.py

Die Funktion `_topic_scores()` in aggregator.py gruppiert Artikel nach Topic und berechnet den Durchschnitts-Compound-Score pro Gruppe. Topics mit weniger als 3 Artikeln erhalten None und fließen nicht in den finalen Score ein. Alle 8 Topics werden explizit aufgelistet damit die Ausgabe-Struktur immer gleich ist auch wenn ein Topic an einem Tag gar nicht vorkommt.

## _final_score Funktion in aggregator.py

Die Funktion `_final_score()` in aggregator.py berechnet den Durchschnitt aller Topic-Scores die mindestens 3 Artikel haben. Der Fallback ist 0.0 wenn kein Topic genug Artikel hat.

## _top_headlines Funktion in aggregator.py

Die Funktion `_top_headlines()` in aggregator.py wählt die 3 Headlines mit dem stärksten absoluten Sentiment bevorzugt aus marktrelevanten Topics: finance, geopolitics, energy und politics. Sportmeldungen und Lokalnachrichten sollen nicht als Top-Headline einer Finanzplattform erscheinen.

## build_snapshot Funktion in aggregator.py

Die Funktion `build_snapshot()` in aggregator.py baut das vollständige Snapshot-Dict für eine Region. Jedes Topic hat eine eigene Spalte statt eines JSON-Blobs für direkte SQL-Abfragen. article_count und Sentiment-Zähler sind Transparenz-Metriken.

## save_snapshot Funktion in aggregator.py

Die Funktion `save_snapshot()` in aggregator.py schreibt einen Snapshot via INSERT statt UPSERT — jeder stündliche Lauf soll einen neuen historischen Eintrag erzeugen nicht den vorherigen überschreiben.

## run_aggregator Funktion in aggregator.py

Die Funktion `run_aggregator()` in aggregator.py orchestriert den Aggregator für alle Regionen. Wenn regions nicht angegeben wird werden alle Regionen automatisch aus den Artikeln abgeleitet. sorted() stellt deterministische alphabetische Reihenfolge sicher.

## Abgelehnte Alternativen für aggregator.py

Option A mit Artikel-Durchschnitt hat das Dominanz-Problem und wurde abgelehnt. Der Median ignoriert Extremwerte komplett. Gewichtung nach Source-Reputation ist zu subjektiv. Echtzeit-Berechnung ohne Snapshots wäre zu langsam. JSONB für Topic-Scores hat schlechtere SQL-Abfragbarkeit.

## **Stand 10.06.2026**