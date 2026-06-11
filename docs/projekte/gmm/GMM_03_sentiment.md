# Global Market Mood – sentiment.py

**Kategorie:** Projekt  
**Projekt:** Global Market Mood (GMM)  
**Stand:** 22.05.2026  
**Status:** Aktiv  

## Zweck von sentiment.py in Global Market Mood

sentiment.py liegt unter `marketmood/pipeline/sentiment.py` und übernimmt als Schritt 3 von 5 die Stimmungsmessung für jeden Artikel. sentiment.py berechnet für jeden Artikel einen numerischen Stimmungswert zwischen -1.0 (extrem bearish) und +1.0 (extrem bullish). Dieser vader_compound-Score ist der Kerndatenpunkt der gesamten Global Market Mood Pipeline.

## VADER Ansatz in sentiment.py

VADER läuft in Millisekunden pro Artikel ohne GPU und ohne API-Kosten — bei 4.000 Artikeln pro Stunde ist das entscheidend. Es ist stabil und deterministisch. Das Problem mit Standard-VADER ist fehlender Finanzwortschatz weshalb das Custom Finance Lexicon nötig ist.

## Finance Lexicon in sentiment.py

Das Finance Lexicon in sentiment.py injiziert domänenspezifische Werte in VADER. Die VADER-Skala geht von -4.0 bis +4.0. bankruptcy und insolvency erhalten -3.0, rate_hike -1.5, ipo +1.5 und market_rally +2.0. Unterstriche statt Leerzeichen ermöglichen Compound-Keywords die als Einheit bewertet werden.

## enhance_analyzer Funktion in sentiment.py

Die Funktion `enhance_analyzer()` in sentiment.py injiziert alle Finance-Lexikon-Einträge direkt in das interne Wörterbuch des VADER-Analyzers — die offizielle dokumentierte Methode um VADER zu erweitern. Sie wird in analyze_all() aufgerufen statt global damit der Analyzer immer das aktuelle Lexikon hat.

## get_label Funktion in sentiment.py

Die Funktion `get_label()` in sentiment.py konvertiert den numerischen Score in bullish, bearish oder neutral. Der Schwellenwert von 0.05 stammt aus der VADER-Originalpublikation. bullish und bearish statt positive und negative werden verwendet weil die Plattform für Finanznutzer ist.

## analyze_article Funktion in sentiment.py

Die Funktion `analyze_article()` in sentiment.py analysiert einen einzelnen Artikel und gibt das ursprüngliche Dict erweitert um vader_compound und vader_label zurück. Das Immutable Pattern mit {**article} verhindert Seiteneffekte. round(compound, 4) liefert ausreichende Präzision.

## analyze_all Funktion in sentiment.py

Die Funktion `analyze_all()` in sentiment.py ruft enhance_analyzer() einmal auf dann analyze_article() für jeden Artikel. VADER braucht kein Batch-Processing weil es lokal und in Mikrosekunden läuft. Das Logging der Verteilung am Ende ist ein wichtiges Qualitätssignal für die Pipeline.

## get_top_articles Funktion in sentiment.py

Die Funktion `get_top_articles()` in sentiment.py sortiert nach dem absoluten Compound-Score und gibt die N stärksten zurück. In V1 nicht produktiv verwendet — für V2 vorbereitet wo FinBERT nur auf den Top-3-Headlines pro Region angewendet werden soll.

## Abgelehnte Alternativen für sentiment.py

FinBERT ist zu langsam ohne GPU für 4.000 Artikel pro Stunde. TextBlob ist weniger präzise. OpenAI Embeddings sind teuer und API-abhängig.

## Bekannte Limitierungen von sentiment.py

VADER ist nur für englische Texte trainiert. Ironie und Sarkasmus werden nicht erkannt. Compound-Keywords mit Underscore tauchen in normalen RSS-Feeds mit Leerzeichen auf — das Lexikon wirkt nur bei exakter Underscore-Schreibweise. Das ist ein bekannter Bug in V1.

## **Stand 10.06.2026**