# Global Market Mood – topic_filter.py

**Kategorie:** Projekt  
**Projekt:** Global Market Mood (GMM)  
**Stand:** 22.05.2026  
**Status:** Aktiv  

## Zweck von topic_filter.py in Global Market Mood

topic_filter.py liegt unter `marketmood/pipeline/topic_filter.py` und übernimmt als Schritt 2 von 5 die Themenbestimmung für jeden Artikel. topic_filter.py weist jedem Artikel genau eine von acht Kategorien zu: finance, geopolitics, energy, technology, health, crime, politics oder general. Diese Klassifikation ist entscheidend weil der Aggregator pro Topic einen eigenen Score berechnet — falsche Topics verfälschen das Stimmungsbild.

## Warum DeepSeek statt spaCy in topic_filter.py

V0 von topic_filter.py verwendete spaCy mit Keyword-Matching. Das produzierte systematische Fehler weil Keywords ohne Kontext zu grob sind — "Solaranlagen gestohlen" wurde als energy statt crime klassifiziert. DeepSeek liest den gesamten Satz und klassifiziert semantisch — nach dem Wechsel wurden alle diese Fälle korrekt klassifiziert.

## Konfiguration von topic_filter.py

Die topic_filter.py Konfiguration definiert drei Parameter. BATCH_SIZE=50 sendet 50 Headlines pro API-Call statt 50 Einzelaufrufe. MAX_CONCURRENT=10 verhindert dass 80 simultane Batches Rate-Limiting auslösen. CATEGORIES definiert die 8 erlaubten Kategorien: finance, geopolitics, energy, technology, health, crime, politics und general.

## _classify_batch_async Funktion in topic_filter.py

Die Funktion `_classify_batch_async()` in topic_filter.py sendet einen nummerierten Batch an DeepSeek mit temperature=0.0 für deterministische Ergebnisse. "Respond ONLY with a JSON array" ist entscheidend weil LLMs sonst Erklärungen hinzufügen die das Parsing brechen. Die dreistufige Validierung prüft Backtick-Strip, erlaubte Kategorien und exakten Längencheck. Wichtige Klassifikationsregeln im Prompt sind "Solar panels stolen" gleich crime statt energy und "Gas pipeline halted by Russia" gleich geopolitics statt energy.

## _classify_all_async Funktion in topic_filter.py

Die Funktion `_classify_all_async()` in topic_filter.py teilt Headlines in Batches und startet sie als asyncio.gather-Tasks mit Semaphore(10) Begrenzung. httpx.AsyncClient wird einmal erstellt für Connection-Pooling über alle Batches.

## enrich_articles Funktion in topic_filter.py

Die öffentliche Hauptfunktion `enrich_articles()` in topic_filter.py löst das Async-in-Sync-Problem: APScheduler und Django sind synchron aber _classify_all_async ist eine Coroutine. asyncio.run() schlägt in Gunicorn fehl weil bereits ein Event-Loop läuft. Die Lösung startet asyncio.run() in einem separaten Thread der immer einen frischen Event-Loop hat.

## Kostenrechnung für topic_filter.py

Bei 96.000 Headlines pro Tag entstehen 1.920 Batches mit etwa 2,98 Millionen Tokens. Mit DeepSeek-V3 Preisen ergibt das circa 19 Dollar pro Monat.

## Abgelehnte Alternativen für topic_filter.py

spaCy Keyword-Matching war V0 mit zu vielen Fehlklassifikationen. FinBERT ist nur für Finance trainiert und braucht GPU. OpenAI GPT-4 ist etwa 10x teurer. Hugging Face zero-shot ist langsam ohne GPU. Einzelaufrufe statt Batches würden 50x mehr API-Overhead bedeuten.

## Bekannte Probleme und V2 Pläne für topic_filter.py

Debug-Prints mit API-Key-Informationen müssen vor Production entfernt werden. V2 plant Embeddings in Supabase via pgvector zu speichern als Basis für ein eigenes Klassifikationsmodell. V3 plant ein eigenes Modell auf 3 Millionen gelabelten Headlines was laufende Klassifikationskosten auf null reduziert.

## **Stand 10.06.2026**