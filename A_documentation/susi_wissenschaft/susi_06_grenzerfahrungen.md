# 06 — Grenzerfahrungen
### SUSI Entwicklungsbericht · Stand Juli 2026

---

## Was dieses Kapitel ist

Dieser Bericht ist kein Portfolio-Stück das nur Erfolge dokumentiert. Grenzerfahrungen gehören dazu — Punkte wo das System gegen eigene Annahmen, technische Grenzen oder konzeptuelle Fehler gelaufen ist. Die ersten vier Grenzerfahrungen kamen im Rahmen eines technischen Reviews durch externe ML-Tutoren ans Licht. Die weiteren entstanden im laufenden Betrieb zwischen Juni und Juli 2026. Sie werden hier nicht als Randnotizen behandelt sondern als vollwertige Erkenntnisse — weil sie das Design zukünftiger Versionen direkt beeinflussen.

---

## Grenzerfahrung 1 — Undokumentierte Score-Skala in der Evaluation

**Was passiert ist:** Die Evaluierungsläufe verwendeten eine Diagnostic-Skala die nie explizit dokumentiert war. Der Auto-Scorer vergibt Scores 0–6 mit präziser Bedeutung pro Stufe — 0 Ausweichantwort, 1 Halluzination, 2 Training korrekt, 3 RAG korrekt, 4 Generation-Problem, 5 falscher Chunk, 6 ValueCheck-Konflikt. Im Bericht stand aber durchgehend "0–2-Skala" und Mittelwerte wie "2.74 / 2.0" — mathematisch unmöglich wenn das Maximum 2 ist.

**Warum das passiert ist:** Die Score-Skala des Auto-Scorers wurde iterativ weiterentwickelt aber nie als explizite Konstante in `config.yaml` oder `evaluator.py` verankert. Verschiedene Läufe liefen mit verschiedenen Versionen des Auto-Scorers — ohne dass die CSVs diese Information als Metadaten trugen. Beim manuellen Auswerten wurde intuitiv bewertet ohne die Skala jedes Mal neu nachzuschauen.

**Was das bedeutet:** Die Korrektheitsprozente waren trotzdem vergleichbar weil `Score ≥ 2` als Schwellenwert über alle Läufe konsistent ist — aber die Durchschnittswerte waren nicht normiert und damit irreführend. Nach externer Prüfung wurden alle historischen Tabellen auf normierte Werte (÷ 3) umgestellt und die Score-Skala vollständig dokumentiert.

**Stand Juli 2026:** `DIAG_ZU_QUALITAET` ist jetzt als zentrale Mapping-Konstante in `auto_scorer.py` verankert. Die Quality Scale (0–2) und die Diagnostic Scale (0–6) sind klar getrennt: die Diagnostic Scale erklärt *warum* eine Antwort so ist, die Quality Scale beantwortet *ob* sie korrekt ist. Score 6 (ValueCheck-Konflikt, seit 15.07.) fängt Fälle ab wo ValueCheck einen Zahlenfehler meldet aber die Similarity-Metriken hohe Übereinstimmung zeigen — diese gehen als Grauzone an RAGAS statt hart auf Quality 0. `grid_run.py` importiert die Konstante zentral — kein dreifaches Duplizieren mehr.

**Die Lektion:** Metriken-Definitionen gehören in den Code als Konstanten — nicht in die Dokumentation als Prosa. `MAX_SCORE = 6` und `KORREKT_THRESHOLD = 2` müssen in `evaluator.py` stehen und in jeder CSV als Metadaten-Spalten erscheinen. Jeder Lauf muss selbsterklärend sein ohne Kontextwissen über die verwendete Scorer-Version.

---

## Grenzerfahrung 2 — Die deutsche Sprachbarriere beim Cross-Encoder

**Was passiert ist:** Im Architekturentwurf für den automatisierten Türsteher (Stufe 2 des 3-stufigen Speichermodells) wurde `cross-encoder/nli-deberta-v3-base` als bevorzugtes Modell geplant. Das Modell ist leichtgewichtig, schnell, läuft auf CPU — scheinbar ideal.

**Das Problem:** DeBERTa-NLI-Modelle aus der Standardbibliothek sind auf englischen MNLI-Korpora trainiert. Bei deutschen Eingaben — deutschen SUSIpedia-Chunks und deutschen LLM-Zusammenfassungen — fällt die Precision drastisch. Das Modell erkennt semantische Abweichungen zwischen deutschem Quelltext und deutschem Entwurf nicht zuverlässig. In der Praxis bedeutet das: halluzinierter deutscher Text wird als "korrekt abgeleitet" eingestuft. Der Hauptzweck des Türstehers — Schutz vor Self-Poisoning — funktioniert nicht.

**Warum das übersehen wurde:** Der erste Entwurf war konzeptuell — er hat die Existenz geeigneter Modelle bestätigt aber nicht die Sprachkompatibilität gecheckt. "Cross-Encoder für NLI" klingt generisch; dass die Trainingsdaten entscheidend sind wurde nicht früh genug als Risiko erkannt.

**Stand Juni 2026:** amberoad wurde getestet und mit 59% Korrektheit disqualifiziert — der Reranker warf aktiv gute Chunks weg. Die produktive Lösung ist `BAAI/bge-reranker-v2-m3` (97% Korrektheit), vom selben Team wie das Embedding-Modell bge-m3. Die vollständige Reranker-Evolution (ms-marco → amberoad → bge) ist in Kapitel 08 dokumentiert.

→ *Reranker-Evolution: [susi_08_produktivbetrieb.md](susi_08_produktivbetrieb.md)*

**Die Lektion:** Sprachkompatibilität ist eine funktionale Anforderung. Bei jedem NLP-Modell das in SUSI eingesetzt wird muss explizit geprüft werden: auf welcher Sprache wurde trainiert, und welche Sprache verarbeitet SUSI?

---

## Grenzerfahrung 3 — Der VRAM-Modellwechsel-Deadlock

**Was passiert ist:** Das 3-stufige Speichermodell sieht vor dass auf `!save` das Chat-Modell (qwen2.5-coder:7b) kurz durch ein Zusammenfassungs-Modell (llama3.1:8b) ersetzt wird. In der Theorie klingt das nach einem eleganten spezialisierten Workflow. In der Praxis entsteht ein potenzieller Deadlock.

Ollama lädt ein Modell vollständig in den VRAM und entlädt es nur auf expliziten Befehl oder bei Timeout. Der Wechsel von qwen2.5-coder auf llama3.1 — und zurück — dauert auf der RTX 3090 zwischen 5 und 15 Sekunden. Wenn dieser Wechsel synchron im Request-Response-Zyklus passiert friert das HTMX-Frontend ein. Der Nutzer sieht kein Feedback, Requests hängen in der Queue.

**Warum das lösbar ist:** `!save` wird selten ausgelöst — realistisch zwei bis drei Mal pro Tag, nicht nach jedem Chat. Das rechtfertigt keinen dauerhaft laufenden Worker, aber es macht einen einfachen asynchronen Background-Task sinnvoll. Der `!save`-Befehl gibt sofort eine Statusmeldung zurück, der Task läuft im Hintergrund, `OLLAMA_MAX_LOADED_MODELS=1` verhindert dass beide Modelle gleichzeitig VRAM belegen.

**Stand Juli 2026:** Der HitL-Queue-Button ist implementiert — jede SUSI-Antwort kann per Klick in die Queue geschickt werden. SQLite-Persistenz läuft produktiv (`Chat`, `Message`, `QueueItem` in Django seit 25.06.2026). Der asynchrone Worker und der `!save`-Befehl als Kommando sind der verbleibende offene Teil der Stufe 2. Das Fundament steht, der Aufsatz folgt in Q3 2026.

**Die Lektion:** Jede Operation die Ollama-Modelle wechselt ist eine potenzielle Blockade. Das Muster "seltener Trigger → async Task → Statusfeedback ans Frontend" ist die richtige Antwort — nicht ein komplexer permanenter Worker.

*→ Implementierungsplan: [susi_07_roadmap.md — Phase 2](susi_07_roadmap.md)*

---

## Grenzerfahrung 4 — Das Tabellen-Verbot war zu radikal

**Was passiert ist:** Die SUSIpedia-Formatierungsregeln verbieten Tabellen vollständig. Die Begründung war korrekt: Tabellen-Zellen sind kurze, kontextfreie Fragmente die schlecht chunken und noch schlechter retrieven. Ein Chunk der nur `| 0.671 | 0.126 |` enthält liefert keinen semantischen Vektor.

**Das übersehene Problem:** Strukturierte Daten — Konfigurationsparameter, API-Antwortformate, Enum-Definitionen, Score-Tabellen — lassen sich in Fließtext zwingen, aber dabei verlieren sie Präzision und Lesbarkeit. Ein LLM das auf einen Chunk mit "Die Konfiguration besteht aus chunk_size mit dem Wert 1000 und overlap mit dem Wert 50 und top_k mit dem Wert 5..." trifft ist schlechter bedient als eines das einen validen YAML-Block findet.

**Die Lösung:** Das Verbot wird präzisiert. Markdown-Tabellen bleiben verboten. Erlaubt sind JSON- und YAML-Codeblöcke für echte strukturierte Daten. Bedingung: jeder Codeblock muss von einem H2-Ankersatz umgeben sein der den Inhalt in Prosa beschreibt. Das Embedding-Modell greift die Prosa für Retrieval, das LLM greift den Codeblock für Generierung. Beide bekommen was sie brauchen.

**Die Lektion:** Formatierungsregeln brauchen eine explizite Begründung warum eine Struktur verboten ist — nicht nur das Verbot selbst. Wenn die Begründung klar ist ergibt sich die Ausnahme logisch daraus.

---

## Grenzerfahrung 5 — BERTScore und ROUGE-L sind blind für numerische Fehler

**Was passiert ist:** Im Lauf der Datumsarithmetik-Tests (30.06.2026) wurden 10 Kalenderfragen gestellt. Der Auto-Scorer vergab allen 10 Einträgen `auto_score=3` (RAG korrekt) — obwohl 5 der Antworten faktisch falsch waren. SUSI nannte falsche Wochentage, falsche Tagesdifferenzen, falsche Datumsberechnungen. Die Metriken zeigten grün.

**Warum das passiert ist:** BERTScore misst semantische Ähnlichkeit. "Montag" und "Dienstag" sind im Vektorraum benachbart — beide sind Wochentage, beide sind kurze deutsche Wörter. ROUGE-L misst lexikalischen Overlap der längsten gemeinsamen Teilfolge. Eine Antwort die "7 Tage" statt "6 Tage" sagt hat einen hohen ROUGE-L-Score weil fast alle Tokens übereinstimmen. Beide Metriken sind auf Ähnlichkeit optimiert — nicht auf Korrektheit von Zahlen, Daten und Wochentagen.

**Das strukturelle Problem:** Similarity-basierte Metriken können prinzipiell nicht erkennen ob eine Zahl richtig ist. "14 Tage" und "21 Tage" sind sich semantisch sehr ähnlich — aber eine davon ist falsch. Das ist kein Kalibrierungs-Problem des Auto-Scorers, sondern eine fundamentale Grenze der verwendeten Metrik-Klasse.

**Die Lösung — drei Schichten:**

Schicht 1: `valuecheck.py` — ein deterministischer Pre-Check der Zahlen, Daten und Wochentage aus Referenz und Antwort extrahiert und direkt vergleicht. Läuft vor BERTScore und ROUGE-L. Findet einen numerischen Widerspruch → Score sofort 0, kein LLM-Aufruf nötig.

Schicht 2: `referenz_loader.py` — dynamische Platzhalter in Testfragen (`{heute}`, `{heute+21}`, `{tage_seit:2026-07-01}`) werden beim Laden aus `date.today()` gerendert. Testsets veralten nicht mehr über Nacht.

Schicht 3: `agent_datum.py` — ein deterministischer Tool-Use-Guard der vor dem RAG-Router prüft ob eine Frage eine reine Kalender-Operation ist. Wenn ja: Python `datetime` löst die Frage in ~1ms, kein LLM, keine Halluzination möglich.

**Ergebnis:** Die Datumsfragen verbesserten sich von Ø 0.20 (nach ValueCheck sichtbar) auf Ø 2.00 (nach agent_datum). 8 von 10 Fragen korrekt gelöst, 2 verbleibende Grenzfälle mit Entitätsbezug (z.B. "Wie alt ist SUSI?") brauchen einen zweiten agent_datum-Zweig.

**Die Lektion:** Similarity-Metriken messen ob eine Antwort *klingt wie* die Referenz — nicht ob sie *stimmt*. Für numerisch präzise Domänen (Datum, Alter, Berechnung) braucht jedes Evaluierungsframework einen deterministischen Pre-Check der die Metrik-Ebene nicht erreicht kennt.

---

## Grenzerfahrung 6 — Doppeltes Query Rewriting (der stille Bug)

**Was passiert ist:** In Lauf F (27.06.2026) wurde ein Bug entdeckt der seit der Implementierung des Query Rewriters unbemerkt aktiv war: `ask_susi_eval()` rief intern `ask_susi()` auf. `ask_susi()` enthält selbst einen Rewriter-Aufruf. Das Ergebnis: jede Testfrage wurde zweimal umgeschrieben — einmal durch `ask_susi_eval()`, einmal durch den internen Aufruf in `ask_susi()`.

**Warum das so lange unbemerkt blieb:** Die Funktion `ask_susi_eval()` war als dünner Wrapper um `ask_susi()` konzipiert. Das klingt sauber — DRY-Prinzip, ein Code-Pfad. Das Problem: der Wrapper hat seine eigene Rewriting-Logik und `ask_susi()` hat ihre eigene. Zwei Aufrufe, zwei Rewriting-Pässe, kein Fehler im Code, kein Stack-Trace, keine Warnung. Die Queries sahen nach dem zweiten Pass noch wie Queries aus — nur leicht anders formuliert. Nicht falsch genug um aufzufallen, falsch genug um die Metriken zu verschieben.

**Das Ausmaß:** Der Effekt kostete ~16 Prozentpunkte Korrektheit. Das entspricht dem Unterschied zwischen "solide" und "kritisch" in der Kategorienbewertung. Eine Komponente die konzeptuell richtig war (Query Rewriting) hat durch doppelte Anwendung aktiv geschadet.

**Die Lektion:** Wrapper-Funktionen die interne Aufrufe kapseln müssen explizit dokumentieren welche Pipeline-Schritte sie selbst ausführen und welche sie an den internen Aufruf delegieren. "DRY" und "ein Aufruf macht alles" sind nicht dasselbe. Jede Pipeline-Stufe sollte genau einmal ausgeführt werden — und das muss testbar sein.

→ *Details: [susi_04_evaluation.md — Lauf F](susi_04_evaluation.md)*

---

## Grenzerfahrung 7 — Language ≠ Computation

**Was passiert ist:** SUSI sollte Datumsberechnungen beantworten: "Wie viele Tage bis Weihnachten?", "Welcher Wochentag ist der 15.08.2026?", "Wie lange läuft SUSI schon?" Das LLM versuchte diese Fragen aus seinem Training zu beantworten — und scheiterte systematisch. Nicht weil das Modell dumm ist, sondern weil Sprachmodelle keine Rechenmaschinen sind.

**Das strukturelle Missverständnis:** Ein LLM hat kein Konzept von "heute". Es hat Wahrscheinlichkeitsverteilungen über Token-Sequenzen. Wenn es "Montag" antwortet tut es das weil "Montag" in ähnlichen Kontexten im Trainingskorpus häufig vorkam — nicht weil es den Kalender berechnet hat. Die Antwort klingt überzeugend. Sie ist trotzdem zufällig.

**Die Lösung:** `agent_datum.py` implementiert einen deterministischen Guard vor dem RAG-Router. Drei Bedingungen müssen erfüllt sein damit eine Frage als reine Kalenderfrage klassifiziert wird: ein konkreter Datumsanker (heute, Weihnachten, Silvester), eine klare Kalender-Operation (Wochentag, Differenz, +N Tage), und kein SUSIpedia-Entitätsname in der Frage. Im Zweifel → LLM+RAG. Nur wenn alle drei Bedingungen erfüllt sind übernimmt Python `datetime`.

Das Ergebnis: "Wie viele Tage seit dem 01.07.2026?" → Antwort in 0.001s, deterministisch korrekt, kein VRAM-Aufruf, kein Halluzinations-Risiko. Im Frontend erscheint `🧮 agent_datum` als Quellenmarker statt einer Chunk-Datei.

**Das Prinzip dahinter:** Sprachmodelle sollen routen, verstehen und generieren. Deterministische Tools sollen berechnen. Die Kombination ist stärker als jedes einzelne System: das LLM erkennt die Intention, das Tool berechnet das Ergebnis, das LLM formuliert die Antwort. Kein Modell der Welt haluziniert wenn Python `datetime.date.today()` aufgerufen wird.

**Die Lektion:** Bevor ein LLM für eine Aufgabe eingesetzt wird sollte explizit geprüft werden: ist das eine Sprach-Aufgabe oder eine Berechnungs-Aufgabe? Für Berechnungen — Datum, Alter, Differenzen, Umrechnungen — ist ein deterministisches Tool immer überlegen. Das ist keine Einschränkung des LLMs; es ist die richtige Arbeitsteilung.

---

## Was alle Grenzerfahrungen gemeinsam haben

Die ersten vier Punkte kamen durch externes Review ans Licht. Die letzten drei entstanden im laufenden Betrieb durch systematische Messung. Das ist kein Zufall — es ist das Ergebnis eines Evaluierungsframeworks das früh genug aufgebaut wurde um Fehler sichtbar zu machen bevor sie im Produktivbetrieb unsichtbar bleiben.

Alle sieben Grenzerfahrungen teilen ein Muster: eine Entscheidung die auf einem gültigen Prinzip basierte hat einen blinden Fleck in der Umsetzung. Skalen-Konsistenz war kein Gedanke wert weil die Evaluation "ja funktioniert". BERTScore war kein Gedanke wert weil die Scores grün waren. Doppeltes Rewriting war kein Gedanke wert weil der Code syntaktisch korrekt war.

Das externe Review hat die ersten blinden Flecken sichtbar gemacht. Das Evaluierungsframework hat die späteren sichtbar gemacht. Das ist der Wert beider Werkzeuge — nicht weil die eigene Analyse falsch war, sondern weil Implizites explizit wird.

**Status der Auto-Save-Pipeline (Stand Juli 2026):** Der Code ist noch in `query.py` enthalten, aber die Pipeline wurde im Mai 2026 deaktiviert. Der Code bleibt nach dem Prinzip "kein Abriss ohne Ersatz" erhalten. Der HitL-Queue-Button ist seit 25.06.2026 produktiv. Die vollständige 3-Stufen-Architektur (async Worker, `!save`-Kommando, SusiInbox) befindet sich in Implementierung (Q3 2026).

---

→ *Zurück zur Übersicht: [susi_00_übersicht.md](susi_00_übersicht.md)*  
→ *Weiter: [susi_07_roadmap.md](susi_07_roadmap.md)*  
→ *Produktivbetrieb: [susi_08_produktivbetrieb.md](susi_08_produktivbetrieb.md)*  
*Stand: Juli 2026 · Martin Freimuth*