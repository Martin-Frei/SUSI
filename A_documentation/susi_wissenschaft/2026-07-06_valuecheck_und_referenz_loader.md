# ValueCheck und Referenz-Loader
Datum: 2026-07-06
Status: aktiv
Kategorie: susi

## ValueCheck — was er ist und warum er existiert

ValueCheck ist eine deterministische Prüf-Schicht im SUSI Auto-Scorer die Zahlen, Daten und Wochentage aus Referenzantwort und SUSI-Antwort extrahiert und direkt Wert gegen Wert vergleicht. Er wurde am 06.07.2026 gebaut weil BERT-Score und ROUGE-L als reine Textähnlichkeits-Metriken numerisch falsche aber fließend formulierte Antworten nicht erkennen können. Konkret: im Testlauf eval_20260630_1218 mit 10 Datumsarithmetik-Fragen vergab der alte Auto-Scorer allen 10 Zeilen auto_score=3 obwohl fünf Antworten faktisch falsch waren.

## ValueCheck — wie er arbeitet

ValueCheck läuft in berechne_auto_score direkt nach dem Ausweich-Phrasen-Check und vor dem bisherigen ROUGE-BERT-Entscheidungsbaum. Er extrahiert per Regex alle prüfbaren Werte aus Referenz und Antwort, vergleicht die Referenzwerte einzeln gegen die Antwort und liefert drei mögliche Ergebnisse. Bei sicherem Fehler setzt er den Diagnostic Score hart auf 1 mit Konfidenz hoch. Bei sicher korrekten Werten gibt er frei und der bestehende Baum entscheidet weiter. Bei unklaren Fällen markiert er die Zeile als Grauzone und der bestehende RAGAS-Haiku-Weg übernimmt.

## ValueCheck — Kernregeln aus dem Konzeptpapier

Die harten Regeln des ValueCheck stehen fest und sind im Modul valuecheck.py implementiert. Es gibt keine Rundungstoleranz, der Vergleich ist exakt. Eine einzige falsche Zahl macht die ganze Antwort falsch weil eine Antwort mit falscher Aussage nicht mehr vertrauenswürdig ist. Zusätzliche korrekte Zahlen in der Antwort werden ignoriert weil eine ausführlichere Antwort keine Falschaussage ist. Fehlt ein Referenzwert in der Antwort und die Antwort enthält abweichende Extra-Werte gleichen Typs, wird das als Substitution behandelt und ist ein harter Fehler. Fehlt ein Referenzwert ohne abweichende Extras, geht die Zeile in die Grauzone.

## ValueCheck — Erweiterungen und Sonderfälle

ValueCheck erkennt deutsche und englische Wochentage als eigene Wertklasse mit Enum-Werten von 1 bis 7. Deutsche Zahlwörter von zwei bis zwölf werden als Zahlen geparst, die Wörter ein und eine sind bewusst ausgeschlossen weil sie im Deutschen fast immer Artikel sind und massenhaft False Positives erzeugen würden. Alleinstehende Jahreszahlen werden nur im Bereich 1990 bis 2035 als Jahr typisiert, damit Konfigurationswerte wie chunk_size 1000 oder Port 11434 nicht fälschlich als Jahr eingeordnet werden. Datums-Granularitäten werden erkannt und nur gleiche Granularitäten direkt verglichen, unterschiedliche Granularität führt zur Grauzone.

## ValueCheck — bewusste Grenzen

ValueCheck kann und soll bestimmte Fehlertypen nicht erkennen. Falsche Quellen mit korrekter Zahl aus falschem Chunk sind außerhalb des Scope. Falsche Namen wie bge-m3 versus nomic-embed-text werden nicht geprüft. Logische Fehler bei identischen Zahlen bleiben unentdeckt, der bekannte Fall ist datum_09 wo beide Antworten dieselben Monatsdaten enthalten und der Fehler rein im logischen Schluss steckt. Einheiten-Fehler wie 10 Tage versus 10 Monate sind nicht abgedeckt weil ValueCheck nur nackte Werte vergleicht, der semantische Unterschied wird von BERT-Score erfasst.

## Referenz-Loader — Zweck und Anwendungsfall

Der Referenz-Loader in referenz_loader.py rendert dynamische Platzhalter in Referenzantworten zur Laufzeit damit zeitabhängige Testfragen nicht ab dem Folgetag veralten. Testfragen wie Wie viele Tage seit dem 15. Mai enthalten in der Referenz das Wort heute, dieses heute muss zur Laufzeit dem tatsächlichen Datum entsprechen. Ohne den Loader produzierte das Datumsarithmetik-Testset ab dem 01.07.2026 systematisch falsche Bewertungen weil die hartcodierten Referenzen noch vom 30.06.2026 stammten. Der Loader arbeitet ausschließlich beim Laden der Fragen in grid_run und ändert nichts an ValueCheck selbst.

## Referenz-Loader — verfügbare Platzhalter

Der Loader ersetzt Platzhalter für das heutige Datum und relative Datumsangaben. Die Marker heute, heute_kurz, heute_iso und heute_wt liefern verschiedene Formatierungen des aktuellen Tages. Die Marker heute+N und heute-N addieren oder subtrahieren N Tage, mit den Varianten _kurz und _wt für Kurzform und Wochentag des Ergebnisses. Für Zeitspannen gibt es tage_seit, wochen_bis und monate_seit jeweils mit einem ISO-Datum als Parameter. Unbekannte Platzhalter bleiben unverändert stehen und werfen keinen Fehler damit ein Tippfehler nicht den ganzen Lauf abbricht.

## Referenz-Loader — Nutzung im Testfragen-JSON

Testfragen mit zeitabhängiger Referenz bekommen im JSON das Feld referenz_template statt referenzantwort. Beim Laden erkennt grid_run das Feld, rendert es über referenz_loader.rendere_frage und schreibt das Ergebnis in referenz und referenzantwort. Fragen ohne Template bleiben unverändert. Beispielhaft nutzt die Frage datum_03 das Template Heute ist der geschweifte Klammern heute geschweifte Klammern Punkt In exakt 3 Wochen und rendert am 06.07.2026 zu Heute ist der 6. Juli 2026, in 3 Wochen ist der 27. Juli 2026. So bleiben die 10 Datumsarithmetik-Fragen zeitlich unbegrenzt gültig.

## Integration in den Auto-Scorer — Reihenfolge

Die Aufrufkette in berechne_auto_score wurde am 06.07.2026 um einen Schritt erweitert. Zuerst prüft der Auto-Scorer die Ausweichantworten-Phrasen und die Ausweich-Flag, dann läuft ValueCheck sofern eine Referenzantwort übergeben wurde, danach greift der bisherige ROUGE-BERT-Entscheidungsbaum wie bisher, unklare Zeilen gehen weiter an RAGAS und Haiku. Die Signatur von berechne_auto_score wurde um den optionalen Parameter referenz erweitert. Ohne Referenz verhält sich die Funktion exakt wie vorher rückwärtskompatibel. Die Übergabe erfolgt in grid_run über frage_data.get referenzantwort.

## Zentrales Diagnostic-zu-Quality Mapping

Das Mapping der Diagnostic-Skala 0 bis 5 auf die Quality-Skala 0 bis 2 lag vorher dreifach dupliziert in grid_run.py, ragas_scorer.py und analyse_csv.py. Beim ValueCheck-Einbau wurde es als zentrale Konstante DIAG_ZU_QUALITAET in auto_scorer.py definiert und grid_run importiert sie von dort. Das Mapping selbst blieb inhaltlich unverändert: 0 zu 0, 1 zu 0, 2 zu 1, 3 zu 2, 4 zu 0, 5 zu 0. Damit ist auto_scorer die Single Source of Truth für dieses Mapping und künftige Änderungen müssen nur an einer Stelle passieren. Ragas_scorer und analyse_csv behalten vorerst ihre lokalen Duplikate, das Refactoring dort ist ein späterer Hygiene-Schritt.

## Rollout-Schalter VALUECHECK_HART

In auto_scorer.py gibt es die Konstante VALUECHECK_HART als Rollout-Schalter. Bei True werden Wertefehler hart als Diagnostic Score 1 gesetzt, das ist der Zielzustand. Bei False gehen Wertefehler stattdessen als Grauzone an RAGAS und Haiku, das ist der Sicherheitsmodus solange manche Testset-Referenzen noch Meta-Text mit Störwerten enthalten. Ein Beispiel für Störwerte sind Sätze wie Diese Frage testet ob mit Hardware-Nummern wie RTX 4070, die zwar in der Referenzantwort stehen aber nicht zur eigentlichen erwarteten Antwort gehören. Für das Datumsarithmetik-Testset kann VALUECHECK_HART auf True stehen, für das Rewriter-Testset erstmal auf False.

## Validierung — Vorher-Nachher-Ergebnisse

Am 06.07.2026 wurde die vollständige Kette gegen das Datumsarithmetik-Testset validiert. Der alte Auto-Scorer vergab am 30.06.2026 allen 10 Fragen den Diagnostic Score 3, was Ø score_manuell 2.0 bedeutet. Mit ValueCheck und dynamischen Referenzen ergab derselbe Testlauf am 06.07.2026 acht mal Score 1 und zwei mal Score 3, was Ø score_manuell 0.4 bedeutet. Die zwei Score-3-Zeilen sind legitim: datum_04 mit korrekter Antwort und datum_09 als bekannter logischer Fehler außerhalb des Scope. BERT-Score Ø stieg von 0.70 auf 0.77 und ROUGE-L Ø von 0.16 auf 0.31, die Antworten wurden also textlich sogar ähnlicher zur Referenz, aber die Bewertung ist trotzdem korrekt hart weil sie nicht mehr auf Textähnlichkeit basiert.

## Ausblick — geplanter Datums-Pre-Check

ValueCheck bewertet nachträglich ob SUSIs Antwort stimmt, macht SUSI selbst aber nicht besser im Rechnen. Der nächste Schritt ist der geplante Datums-Pre-Check in rag/query.py mit zwei Zweigen. Zweig 1 fängt reine Kalenderfragen ohne Entitätsbezug ab und berechnet sie direkt in Python datetime ohne Retrieval und ohne LLM. Zweig 2 behandelt Fragen mit Projektbezug wie Wie alt ist SUSI, das relevante Datum kommt aus dem retrievten Chunk, die Differenz wird in Python vorberechnet und als fertiger Fakt ins Prompt injiziert. Damit hört SUSI auf im Kopf zu rechnen und formuliert nur noch aus. Umsetzung nach der ersten produktiven Erfahrung mit ValueCheck.

## Wichtige Dateipfade

Die drei neuen und veränderten Dateien liegen alle in tools/evaluation/. Neu sind valuecheck.py mit der Werte-Extraktion und dem Vergleich, referenz_loader.py mit den Platzhaltern für dynamische Referenzen und test_valuecheck.py als Validierungs-Harness ohne Ollama-Abhängigkeit. Geändert sind auto_scorer.py mit ValueCheck-Aufruf und zentralem Mapping-Dict, grid_run.py mit Referenz an berechne_auto_score und Loader-Aufruf in lade_fragen und testfragen_datumsarithmetik.json in Version 2.0 mit sechs dynamischen und vier statischen Referenzen. Ergebnis-CSVs des Validierungslaufs liegen unter tools/evaluation/results/eval_20260706_1046_full.csv und eval_20260706_1135_full.csv.

Stand: 06.07.2026 · Martin Freimuth