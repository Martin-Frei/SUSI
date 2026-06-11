# 01 — Motivation und Problemstellung
### SUSI Entwicklungsbericht · Stand Juni 2026

---

## Warum ein eigener KI-Assistent?

Die Frage klingt auf den ersten Blick nach einem Hobby-Projekt. Sie ist es nicht.

Kommerzielle KI-Assistenten wie Microsoft Copilot, ChatGPT oder Google Gemini sind beeindruckend — aber sie haben drei strukturelle Schwächen die für den ernsthaften persönlichen und beruflichen Einsatz problematisch sind. Diese drei Schwächen sind gleichzeitig die drei Gründe warum SUSI gebaut wurde.

---

## Grund 1: Datenschutz — Daten gehören nicht nach draußen

Die offensichtlichste Motivation. Jede Eingabe in einen Cloud-basierten KI-Assistenten verlässt das eigene System. Für Unternehmen bedeutet das konkret:

- Interne Strategiedokumente landen auf fremden Servern
- Kundendaten werden zu Trainingszwecken potenziell weiterverarbeitet
- Geschäftsgeheimnisse sind rechtlich nur schwer schützbar sobald sie das Unternehmensnetzwerk verlassen haben

Die relevanten Rechtsgrundlagen sind eindeutig: DSGVO, AI Act und das Geschäftsgeheimnisgesetz (GeschGehG) schaffen einen Rahmen der lokale Verarbeitung für viele Anwendungsfälle nicht nur sinnvoll, sondern notwendig macht. Kein AVV, keine DSFA, keine Abhängigkeit von Cloud-Verfügbarkeit oder Preisänderungen des Anbieters.

SUSI ist vollständig lokal. Kein einziger Byte verlässt das System.

---

## Grund 2: Private Daten nutzbar machen — nicht nur schützen

Datenschutz ist die eine Seite. Die andere Seite ist mindestens genauso wichtig und wird in der Diskussion um lokale KI oft vergessen:

**Private Daten sind ein enormes ungenutztes Potenzial.**

Lebenslauf, Bewerbungsunterlagen, Projektdokumentationen, persönliche Ziele, Gesprächsnotizen, Lernmaterialien — all das existiert irgendwo auf der eigenen Festplatte, in Notiz-Apps, in verstreuten Markdown-Dateien. Ein externer KI-Assistent hat keinen Zugriff darauf und kann damit nicht arbeiten.

SUSI dreht dieses Verhältnis um. Die SUSIpedia ist eine strukturierte Wissensbasis aus genau diesen privaten Daten — und SUSI kann darüber abgefragt werden wie über eine persönliche Datenbank. Fragen wie *"Was sind meine aktuellen beruflichen Ziele?"*, *"Welche Technologien stehen in meinem Lebenslauf?"* oder *"Was habe ich beim letzten StockPredict-Training gelernt?"* beantwortet SUSI aus dem eigenen Wissensbestand — präzise, lokal, ohne Datenweitergabe.

Das ist kein Chatbot. Das ist ein externes Gedächtnis.

---

## Grund 3: Lernen durch Bauen — SUSI als tägliches Lernwerkzeug

SUSI ist nicht nur ein fertiges Produkt. Es ist ein laufendes Lernprojekt.

Jeder Tag an dem an SUSI gearbeitet wird ist ein Tag an dem konkrete Fähigkeiten entstehen: RAG-Architekturen verstehen, Embedding-Modelle evaluieren, Django-Backends bauen, Evaluierungsframeworks entwickeln, Prompt Engineering betreiben, ChromaDB konfigurieren. Nicht in der Theorie — in einem echten, produktiv laufenden System.

Dieser Aspekt ist bewusst Teil der Motivation. Ein KI-Assistent der täglich genutzt wird zwingt dazu, ihn täglich zu verbessern. Und jede Verbesserung erfordert ein tieferes Verständnis der zugrundeliegenden Technologien. Das ist ein positiver Kreislauf der sich von einem reinen Lernprojekt fundamental unterscheidet — weil ein echtes System echte Konsequenzen hat wenn etwas nicht funktioniert.

Die SUSIpedia selbst ist ein Nebenprodukt dieses Lernprozesses. Jedes neue Konzept das verstanden wird landet als strukturiertes Markdown-Dokument in der Wissensbasis — und steht SUSI beim nächsten Mal direkt zur Verfügung.

---

## Grund 4: Planung als Grundlage für Reproduzierbarkeit

Viele Entwicklungsprojekte scheitern nicht an fehlender Technik, sondern an fehlender Struktur. Code der heute funktioniert aber morgen nicht mehr nachvollzogen werden kann ist wertlos. Ein System das nur der Entwickler selbst versteht ist nicht skalierbar.

Von Anfang an war deshalb ein Prinzip leitend: **Erst planen, dann umsetzen.**

Das bedeutet konkret:
- Jede Architekturentscheidung wird begründet dokumentiert bevor sie implementiert wird
- Jeder Evaluierungslauf geht mit klaren Hypothesen rein statt blind Parameter zu testen
- Jede Änderung an der Wissensbasis folgt definierten Formatregeln die RAG-Retrieval optimieren
- Jede verworfene Idee wird mit ihrer Begründung festgehalten — nicht nur was funktioniert, sondern warum bestimmte Ansätze nicht verfolgt wurden

Diese Disziplin macht SUSI reproduzierbar. Ein neuer Entwickler — oder Martin selbst in sechs Monaten — kann nachvollziehen warum das System so aussieht wie es aussieht. Das ist der Unterschied zwischen einem Experiment und einem Projekt.

---

## Die zentrale Frage

Alle vier Motivationen münden in eine einzige Ausgangsfrage:

> *"Wie baue ich einen KI-Assistenten der alles lokal verarbeitet, private Daten aktiv nutzbar macht, beim Aufbau täglich Wissen vermittelt — und so strukturiert entwickelt wird dass er in einem Jahr noch genauso funktioniert und verstanden wird?"*

SUSI ist der Versuch einer Antwort darauf. Kein abgeschlossener — sondern ein laufender.

---

*→ Zurück zur Übersicht: [00_SUSI_Uebersicht.md](susi_00_übersicht.md)*  
*→ Weiter: [02_Architektur.md](susi_02_architektur.md)*  
*Stand: Juni 2026 · Martin Freimuth*