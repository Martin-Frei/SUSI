# SUSI — Projekttagebuch
**Datum:** 10.06.2026
**Status:** aktiv
**Kategorie:** projekte

## Entstehung — SUSI Projekt

SUSI wurde am 20. März 2026 von Martin Freimuth ins Leben gerufen. Der Name steht für Selbständige Und Schlaue Intelligenzbestie. SUSI läuft vollständig lokal auf Martins Windows PC mit einem Ryzen 9 5900X, 32GB RAM und einer RTX 4070 mit 12 GB VRAM, später RTX 3090 mit 24GB VRAM.

## Tech Stack — SUSI Projekt

SUSI basiert auf Ollama mit llama3.1:8b als Sprachmodell und bge-m3 für Embeddings. ChromaDB dient als Vektordatenbank, LangChain als Orchestrator und Django als Web-Framework. Whisper für Spracherkennung und ein Raspberry Pi als physisches Interface sind für spätere Stufen geplant.

## Meilensteine — SUSI Projekt

Am 20. März 2026 wurde die Grundlage von SUSI gelegt. Ollama wurde installiert und das Sprachmodell geladen. Das Django-Projekt wurde angelegt und ChromaDB sowie LangChain wurden eingerichtet. Die Dokumentationsstruktur der SUSIpedia wurde aufgebaut und erste Docs erstellt. RAG funktionierte beim ersten Versuch — SUSI gab ihre erste Antwort aus eigenen Dokumenten und kannte von Beginn an ihre Vision, Martins Profil und ihr eigenes Projekttagebuch.

## Geplante Features — SUSI Projekt

Die geplanten Features umfassen RAG über die eigene Codebase, Gesichtserkennung via Raspberry Pi, Sprachsteuerung via Whisper sowie eine Home Assistant Integration. Langfristig ist ein persönliches Tagebuch mit Spracheingabe und Verschlüsselung der persönlichen Ordner via VeraCrypt geplant.

## Entwicklungsstufen — SUSI Projekt

SUSI entwickelt sich in drei Stufen. Stufe 1 ist der Coding Assistent der aktuell aktiv ist. Stufe 2 ist der physische Assistent mit Raspberry Pi der als nächstes folgt. Stufe 3 ist die Vision des persönlichen Lebensassistenten der vollständig autonom agiert.

## Aktueller Stand Juni 2026 — SUSI Projekt

Seit März 2026 hat sich SUSI deutlich weiterentwickelt. Das Embedding-Modell wurde von nomic-embed-text auf bge-m3 gewechselt, das auf dem SUSI-Korpus 18x bessere Retrieval-Ergebnisse liefert. Das LLM ist llama3.1:8b mit Temperature 0.0. Die SUSIpedia umfasst inzwischen über 115 Dateien mit 1687 Chunks in ChromaDB. Das Django Web-Frontend mit HTMX läuft lokal auf Port 8008 mit Drag-and-Drop Upload. Die RAG-Evaluierung mit 40 Testfragen ergab 71% Korrektheit mit der Gewinner-Konfiguration: Chunk-Size 1000, Overlap 50, top-k 5 und praezise_neu Prompt.

## **Stand 10.06.2026**