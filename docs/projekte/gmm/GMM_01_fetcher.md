# Global Market Mood – fetcher.py

**Kategorie:** Projekt  
**Projekt:** Global Market Mood (GMM)  
**Stand:** 22.05.2026  
**Status:** Aktiv  

## Zweck von fetcher.py in Global Market Mood

fetcher.py liegt unter `marketmood/pipeline/fetcher.py` und übernimmt als Schritt 1 von 5 das Holen der Rohdaten. Die Abhängigkeiten sind feedparser und api_sources.py mit FEED_SOURCES. fetcher.py ist der Einstiegspunkt der Global Market Mood Pipeline. Er ruft RSS-Feeds aus aller Welt ab, bereinigt die Rohdaten und gibt eine normalisierte Liste von Artikel-Dicts zurück — jeder Artikel im gleichen Format egal von welcher Quelle er kommt. Ohne diese Normalisierung könnten die nachfolgenden Stufen DeepSeek, VADER und Aggregator nicht einheitlich arbeiten.

## Globale Konfiguration in fetcher.py

Ein globaler Timeout von 15 Sekunden wird für alle HTTP-Verbindungen gesetzt da feedparser intern urllib verwendet und keinen direkten Timeout-Parameter akzeptiert. RSS-Feeds hängen manchmal — ein blockierender Feed würde ohne Timeout die gesamte stündliche Pipeline aufhalten.

```python
socket.setdefaulttimeout(15)
```

## clean_text Funktion in fetcher.py

Die Funktion `clean_text()` in fetcher.py entfernt HTML-Tags und normalisiert Whitespace auf einzelne Leerzeichen. RSS-Feeds liefern in der Praxis unreine Daten mit HTML-Fragmenten die VADER verfälschen würden. Regex statt BeautifulSoup wird verwendet weil zwei re.sub() Aufrufe vollständig ausreichen ohne unnötige Abhängigkeit.

```python
def clean_text(text: str) -> str:
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text
```

## fetch_feed Funktion in fetcher.py

Die Funktion `fetch_feed()` in fetcher.py ruft einen einzelnen RSS-Feed ab, iteriert über alle Einträge und gibt eine normalisierte Liste von Artikel-Dicts zurück. Das text-Feld kombiniert Titel und Beschreibung weil der Titel allein oft zu kurz für eine zuverlässige Stimmungsanalyse ist. Bei fehlendem published-Datum wird datetime.now(utc) als Fallback verwendet. Der gesamte Abruf ist in try/except gewrapped — ein fehlerhafter Feed bricht die Pipeline nicht ab.

## fetch_all_sources Funktion in fetcher.py

Die Funktion `fetch_all_sources()` in fetcher.py koordiniert alle Feeds, filtert optional nach Region und dedupliziert nach Titel. Deduplizierung per Titel statt URL wird verwendet weil derselbe Artikel häufig auf mehreren Feeds mit unterschiedlichen URLs erscheint. Ohne Deduplizierung würde ein einzelnes Ereignis den Score einer Region künstlich dominieren.

## Abgelehnte Alternativen für fetcher.py

Mehrere Alternativen wurden für fetcher.py evaluiert. NewsAPI ist ab gewissem Volumen kostenpflichtig. Scrapy ist für vollständiges Web-Scraping ausgelegt und zu komplex für RSS. requests mit lxml funktioniert aber feedparser löst RSS-Format-Chaos automatisch. BeautifulSoup für clean_text ist eine unnötige Abhängigkeit für zwei einfache Regex-Patterns. Async Fetching wurde in V1 bewusst synchron gehalten — einfacher zu debuggen und Feeds sind nicht der Bottleneck, DeepSeek ist es.

## Bekannte Limitierungen und V2 Pläne für fetcher.py

Aktuell unterstützt fetcher.py nur RSS-Feeds — V2 soll NewsAPI als optionalen Adapter hinzufügen. Nur englische Feeds sind aktiv da VADER und DeepSeek primär auf Englisch ausgerichtet sind — Mehrsprachigkeit kommt mit FinBERT-Multilingual in V2. Es gibt keinen Retry bei Timeout — V2 plant exponentielles Backoff für wichtige Feeds. Deduplizierung ist nur in-memory — die zweite Sicherheitsstufe ist upsert mit on_conflict=url im supabase_client.

## **Stand 10.06.2026**