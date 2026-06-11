Das mathematische Paradoxon in Lauf 2 (Embedding-Wechsel)Das Problem: Schau dir die Werte von Lauf 2 ganz genau an:Gesamtergebnis: Korrektheit (Score≥2) = 65%Kategorie "technisch": 49/49 Korrekt $\rightarrow$ das sind 100% für diese Kategorie.In der Kategorie-Tabelle schreibst du aber für "technisch": Ø Score (normiert) = 0.99.Der mathematische Fehler: Wenn jede einzelne der 49 Fragen korrekt (also mit Score 2 oder 3) beantwortet wurde, ist es statistisch unmöglich, dass der Gesamtdurchschnitt der Korrektheit des gesamten Laufs bei 65% liegt, während gleichzeitig die drei anderen Kategorien (persönlich, lernen, projekte) aufaddiert im normierten Score bei 0.42, 0.37 und 0.28 herumdümpeln.Rechenbeispiel: Wenn 49 von 194 Fragen perfekt sind (100%), und der Rest so schlecht abschneidet, bricht deine Gesamtkorrektheit ein. Aber schau dir die Zähler an: $49 + 33 + 33 + 12 = 127$ korrekte Fragen. $127 \div 194 = \mathbf{65,46\%}$. Das stimmt!Was nicht stimmt, sind die normierten Ø-Scores pro Kategorie: Wenn "technisch" 49/49 korrekte Antworten hat, und die Skala bis 3 geht, bedeutet ein normierter Wert von 0.99, dass fast jede Frage eine glatte 3 war ($0.99 \times 3 = 2.97$). Wenn aber "persönlich" 33/49 Korrekte hat (67%), kann der normierte Durchschnittsscore nicht bei 0.42 liegen ($0.42 \times 3 = 1.26$). Ein Durchschnittsscore von 1.26 bedeutet laut deiner Skala "Ausreichend / Teilweise". Wenn 67% der Fragen aber mindestens eine 2 oder 3 bekommen haben, müsste der Durchschnitt der Kategorie deutlich über 1.5 (also normiert > 0.5) liegen.Die Lösung: Überprüfe die Aggregations-Logik in deinem Auswertungsskript für die kategoriespezifischen Ø Score (normiert)-Spalten. Da ist beim Normalisierungs-Faktor (Teilen durch 3 oder Teilen durch die Gesamtanzahl) in den Unterkategorien irgendwo ein Dreher drin.



Der "Django-Pause"-Widerspruch beim Modell-Wechsel (Stufe 2)
Das Problem: Im einleitenden Satz zu Stufe 2 schreibst du völlig richtig: „Auf !save läuft die Validierung im Hintergrund — der Chat wird nicht unterbrochen“.

Zwei Absätze weiter unten unter Spezialisiertes Zusammenfassungs-Modell steht aber immer noch: „Django pausiert kurz den Live-Coder (qwen2.5-coder:7b) und lädt über Ollama ein logisch stärkeres Modell...“

Die harte Konsequenz: Das Wort „pausiert“ bricht das Versprechen, dass der Chat im Hintergrund weiterläuft. Wenn Django (das als synchrones WSGI- oder asynchrones ASGI-Framework auf Anfragen wartet) aktiv den Thread pausiert oder Ollama blockiert, während das 8B-Modell in den VRAM schaufelt, merkt das der Nutzer im Frontend eben doch.

Die Lösung: Ersetze das Wort „pausiert“ durch eine Formulierung, die die asynchrone Entkopplung unmissverständlich klarstellt.

!!!! meien Gedank wenn ich das lese warum kann die cpu das nicht übernehemn weil es muß ja nicht sofort geschehen das die das in die susipedia geht !!!


Formulierungsvorschlag: > Spezialisiertes Zusammenfassungs-Modell: Ein asynchroner Django-Hintergrund-Worker (z. B. via Task-Queue) übernimmt den !save-Befehl. Er weist Ollama an, das logisch stärkere Modell (z.B. llama3.1:8b) zu laden, während der Haupt-Thread ungerührt für den Live-Coder (qwen2.5-coder:7b) offen bleibt und der Chat nahtlos weiterläuft.

Die verbleibende Schwachstelle (Kritischer Blick)
Obwohl das Kapitel inhaltlich extrem stark ist, gibt es einen konzeptionellen Punkt in Grenzerfahrung 3, der technisch noch nicht ganz zu Ende gedacht ist und zu einem Folge-Problem auf deiner Hardware führen wird:

🔴 Das unausgesprochene "Ollama VRAM-Verschwendungs-Problem" (Grenzerfahrung 3)
Das Problem: Du schreibst völlig richtig, dass Celery/Django-Q den !save-Task asynchron im Hintergrund abarbeiten, damit das Frontend nicht einfriert. Du erwähnst auch: „Ollama lädt ein Modell vollständig in den VRAM und entlädt es nur auf expliziten Befehl oder bei Timeout.“

Die harte Konsequenz: Wenn der asynchrone Hintergrund-Worker an Ollama den Befehl schickt, llama3.1:8b zu laden, und der Haupt-Thread gleichzeitig qwen2.5-coder:7b für den aktiven Chat bereithält, versucht Ollama standardmäßig beide Modelle gleichzeitig im VRAM zu halten.

Die Rechnung: 7B Coder (ca. 5–6 GB im RAM/VRAM) + 8B Llama (ca. 6–7 GB) + dein bge-m3 Embedding-Modell + der VRAM-Bedarf deines Betriebssystems/Monitors.

Das passt zwar rechnerisch noch in die 24 GB deiner RTX 3090, aber Ollama neigt bei parallelen Anfragen dazu, Chunks zu splitten oder Modelle aggressiv auf die CPU auszulagern, wenn der VRAM-Druck steigt. Wenn das passiert, bricht die Inferenz-Geschwindigkeit deines Live-Chats (Tokens pro Sekunde) massiv ein, während der Hintergrund-Worker läuft.

Die Lösung: Du musst in der Dokumentation festhalten, wie du Ollama konfigurierst, um dieses Verhalten zu kontrollieren. Ollama besitzt die Umgebungsvariablen OLLAMA_NUM_PARALLEL (wie viele Anfragen parallel verarbeitet werden) und OLLAMA_MAX_LOADED_MODELS.

Ergänzungsvorschlag für die Lösung in Grenzerfahrung 3:

„...Der Worker übernimmt den Modellwechsel im Hintergrund. Um zu verhindern, dass Ollama beide Modelle gleichzeitig im VRAM hält und dadurch die Inferenz-Geschwindigkeit des aktiven Chats einbricht, wird Ollama über Umgebungsvariablen (OLLAMA_MAX_LOADED_MODELS=1) so restriktiert, dass das Hintergrundmodell das Live-Modell im VRAM hart ersetzt und nach getaner Arbeit sofort wieder freigibt.“

Die verbleibende Schwachstelle (Kritischer Blick)
Für die absolute 99%-Perfektion hat sich in Phase 1 ein winziger Zahlendreher eingeschlichen, und in Phase 4 fehlt ein wichtiges Detail, um das Hardware-Szenario realistisch zu halten:

🔴 Der Datensatz-Zahlendreher in Phase 1
Das Problem: Unter SUSIpedia-Qualität vollständig abschließen schreibst du: „Nach Abschluss folgt ein vollständiger Grid-Lauf über alle 237 Testfragen.“

Ein paar Zeilen weiter unten bei Lauf A und auch im vorherigen Kapitel 4 schreibst du jedoch durchgehend von 240 Testfragen.

Die Lösung: Vereinheitliche die Zahl auf die exakten 240, damit beim Querlesen keine Zweifel an der Konsistenz deiner Testumgebung aufkommen.

🟡 Die Performance-Illusion des Raspberry Pi 5 (Phase 4)
Das Problem: Du schreibst: „Kleine Modelle (1B–3B Parameter), quantisiert und fine-tuned [...] könnten auf einem Raspberry Pi 5 (8GB) als MCP-Server laufen.“ Das stimmt für die reine Ausführung der Modelle. Du ergänzt als Anwendungsfall aber: „Sprachsteuerung über Whisper (lokale Speech-to-Text-Inferenz)“.

Die harte Konsequenz: Wenn auf dem Pi 5 bereits ein 3B-Modell läuft und parallel dazu ein lokales Whisper-Modell (selbst im tiny- oder base-Format über whisper.cpp) aufgerufen wird, bricht die CPU des Pi 5 unter der doppelten Inferenz-Last gnadenlos ein. Die Latenz bei der Sprachsteuerung würde unerträglich lang werden.

Die Lösung: Ergänze hier eine kleine technische Einschränkung, um zu zeigen, dass du die Edge-Hardware-Limits kennst.

Formulierungsvorschlag: > „...Sprachsteuerung über Whisper (lokale Speech-to-Text-Inferenz via whisper.cpp, wobei die Inferenz-Tasks sequenziell geschaltet werden müssen, um die CPU des Pi 5 nicht zu überlasten).“

Positives
1. Extrem klare Positionierung und Alleinstellung
Die zentrale Designentscheidung („Die Wissensbasis ist das eigentliche Asset“) zieht sich konsequent durch den gesamten Text. Das ist nicht nur ein Slogan, sondern wird in der Architektur, der Evaluierung und der Roadmap eingelöst. Dadurch entsteht ein roter Faden, den man selten in Entwicklungsberichten sieht.

2. Ehrlichkeit und Glaubwürdigkeit
Der Abschnitt „Was nicht funktioniert hat“ und die ehrliche Rollenverteilungstabelle sind erfrischend. Du nennst klare Grenzen („kein GPT-4-Ersatz“) und dokumentierst Sackgassen mit nachvollziehbaren Begründungen. Das schafft Vertrauen und unterscheidet den Text wohltuend von Marketing-Dokumenten.

3. Architektur wird nachvollziehbar erklärt
Das RAG-Diagramm (Frage → Embedding → ChromaDB → Kontext → LLM) ist simpel und verständlich. Die 3-stufige Architektur mit Human-in-the-Loop ist technisch sauber begründet, und die Reihenfolge der Argumentation (erst Problem, dann verworfene Lösungen, dann finale Architektur) ist didaktisch stark.

4. Messbarkeit als Prinzip
Dass du ein formales Evaluierungsframework beschreibst – mit Retrieval-Ebene und End-to-End-Ebene, inkl. konkreter Metriken (BERTScore, ROUGE-L) – hebt den Bericht über ein reines „Ich hab was gebaut“-Niveau hinaus. Der Satz „Was das Retrieval nicht findet, kann kein Prompt der Welt reparieren“ ist zitierfähig prägnant.

5. Praktische Erkenntnisse mit direkter Konsequenz
Die Beobachtung zu „ausformulierte Sätze vs. kompakte Listen“ ist konkret, überraschend und direkt handlungsleitend – genau das, was einen Entwicklungsbericht wertvoll macht. Dass diese Erkenntnis die Dokumentationspraxis verändert hat, zeigt echte Iteration.

6. Sprachlich meist klar und selbstbewusst
Der Ton ist selbstbewusst, aber nicht arrogant. Formulierungen wie „Ehrliche Rollenverteilung“ oder „Ein Entwicklungsbericht ohne Fehler ist Marketing, keine Dokumentation“ treffen den richtigen Ton zwischen Stolz und Offenheit.

Negatives / Widersprüchliches / Verbesserungswürdiges
1. Widerspruch: „Dokumentformat auf Retrieval optimiert – nicht auf menschliche Lesbarkeit“
Das ist eine der wenigen Stellen, die ernsthaft hakt. Du schreibst, das Format sei nicht auf menschliche Lesbarkeit ausgelegt – aber die Dokumentation selbst (inklusive dieses Berichts) ist für Menschen offensichtlich sehr gut lesbar. Gemeint ist vermutlich: „nicht primär auf menschliche Lesbarkeit optimiert“ oder „nicht auf schnelle Überfliegbarkeit getrimmt“. So wie es da steht, wirkt es wie ein Widerspruch zur gelebten Praxis – was du zeigst, ist ja gerade, dass Retrieval-Optimierung und gute Lesbarkeit kein Gegensatz sein müssen. Eine kleine Klarstellung würde den Punkt stärken.

2. Begriff „Intelligenzbestie“ – passt das zur Zielgruppe?
Der Name SUSI ist charmant, aber das Wort „Intelligenzbestie“ changiert gefährlich zwischen Augenzwinkern und mangelnder Ernsthaftigkeit. Wenn die anvisierte Zielgruppe mittelständische Unternehmen und DSGVO-Verantwortliche sind, könnte das abschreckend wirken. Für ein persönliches Projekt oder die Entwickler-Community ist es sympathisch, für den im Abschnitt „Geschäftspotenzial“ genannten Markt eher unglücklich. Ein kurzer Hinweis, dass der Name bewusst provokant-ironisch gewählt ist, würde helfen.

3. „DSGVO-konform“ wird behauptet, aber nicht belegt
DSGVO-Konformität ist ein starkes Versprechen. Du argumentierst überzeugend mit „kein Byte verlässt das System“, aber DSGVO umfasst mehr: Auskunftsrecht, Recht auf Löschung, Datenminimierung, Zweckbindung etc. Dass ein lokales System diese Anforderungen ermöglicht, ist richtig – aber der Bericht müsste an mindestens einer Stelle differenzieren zwischen „technisch lokal = gute DSGVO-Voraussetzung“ und „nachweislich DSGVO-konform“. So wie es jetzt da steht, könnte ein Jurist nachfragen – und du hast die technische Substanz, um da präziser zu sein.

4. Die 5 Kernerkenntnisse überschneiden sich thematisch
Punkt 1 („Wissensbasis ist das Asset“) und Punkt 2 („Dokumentqualität schlägt Modellgröße“) zielen auf dasselbe Prinzip, nur auf unterschiedlichen Ebenen. Punkt 4 und 5 (Human-in-the-Loop, Einfachheit als Architekturentscheidung) sind ebenfalls nah beieinander. Das ist kein logischer Fehler, aber die Liste wirkt dadurch weniger prägnant, als sie sein könnte. Eine Konsolidierung auf 3 wirklich distinkte Prinzipien würde die Wirkung erhöhen.

5. Abkürzung MCP nicht erklärt
Im Abschnitt Phase 2 taucht „MCP-Server“ auf. Wer den Stack bis hierhin verstanden hat (Django, HTMX, Ollama etc.), kann mit MCP (Model Context Protocol) möglicherweise etwas anfangen – aber du adressierst im Geschäftspotenzial auch Entscheider außerhalb der Entwickler-Community. Eine Klammererklärung in einem Wort würde die Verständlichkeit erhöhen.

6. Kleine sprachliche Inkonsistenzen

Im Abschnitt zu SUSIpedia: „eine strukturierte Sammlung von Markdown-Dateien die als Langzeitgedächtnis des Systems dient“ – Komma fehlt vor „die“.

In der Rollenverteilung: „Komplexes Debugging“ ist mehrdeutig – meinst du Debugging komplexer Systeme oder komplexes Debugging als Tätigkeit? Kleine semantische Unschärfe.

Der Satz zur Evaluierung („Das ist der Unterschied zwischen systematischer Optimierung und Raten“) ist stilistisch stark, aber das Wort „Raten“ ist etwas flapsig im Vergleich zum restlichen Duktus. „Trial-and-Error“ oder „Herumprobieren“ wären Alternativen, aber Geschmackssache.

Gesamteindruck
Das ist ein inhaltlich sehr starker Entwicklungsbericht mit einer klaren, ehrlichen und architektonisch fundierten Argumentation. Die wenigen kritischen Punkte sind überwiegend Nuancen in der Präsentation und Zielgruppenansprache – kein strukturelles Problem.

Der größte tatsächliche Widerspruch ist die Aussage zur „nicht auf Lesbarkeit optimierten“ Dokumentation, die nicht zur offensichtlich guten Lesbarkeit des Berichts selbst passt. Alles andere sind Optimierungshinweise, die den bereits hohen Standard weiter anheben können.



Positives
1. Die vier Motivationen sind klar getrennt und gut begründet
Datenschutz, Datennutzbarmachung, Lernen und Planung – jede Motivation steht für sich, ist nachvollziehbar argumentiert und baut nicht aufeinander auf (kein Pseudo-Kausalitätsgekette). Besonders stark: Du trennst „Schutz“ und „Nutzbarmachung“ als zwei unabhängige, gleichwertige Motivationen. Das ist ein Denkfehler, den viele machen („lokal = nur sicher“) und den du hier explizit korrigierst.

2. Grund 2 ist der konzeptionell stärkste Abschnitt im gesamten bisherigen Material
„Das ist kein Chatbot. Das ist ein externes Gedächtnis.“ – dieser Satz trifft den Kern deiner Architektur präziser als alles, was in der Übersicht steht. Die konkreten Beispiel-Fragen („Was habe ich beim letzten StockPredict-Training gelernt?“) machen sofort verständlich, was der Unterschied zu einem generischen KI-Assistenten ist. Das ist überzeugend und hebt SUSI von anderen lokalen RAG-Systemen ab.

3. Grund 3 ist ehrlich und strategisch klug platziert
Dass das Projekt auch ein Lernvehikel ist, sagst du offen – aber du verkaufst es nicht als „Hobby“, sondern drehst es produktiv: Das System zwingt zur Verbesserung, weil es produktiv genutzt wird. Der positive Kreislauf aus Nutzung → Lernen → Verbesserung → bessere Nutzung ist didaktisch stark argumentiert.

4. Die Planungs-Disziplin ist konkret, nicht abstrakt
Viele Entwicklungsberichte behaupten „strukturiertes Vorgehen“, aber du listest auf: Architekturentscheidungen vor Implementierung, Hypothesen vor Evaluierung, Formatregeln für die Wissensbasis, Dokumentation verworfener Ideen. Das ist überprüfbar – und wer das Repository ansieht, kann das verifizieren oder widerlegen. Das schafft Substanz.

5. Der Stil bleibt konsistent selbstbewusst und klar
Formulierungen wie „Kein AVV, keine DSFA, keine Abhängigkeit von Cloud-Verfügbarkeit“ sind juristisch informiert, ohne sperrig zu klingen. „Code der heute funktioniert aber morgen nicht mehr nachvollzogen werden kann ist wertlos“ – solche Sätze haben Rhythmus und Gewicht.

Negatives / Widersprüchliches / Verbesserungswürdiges
1. Die zentrale Frage ist überladen
Die Ausgangsfrage am Ende versucht, alle vier Motivationen in einen Satz zu packen. Das Ergebnis ist ein syntaktisches Ungetüm:

„Wie baue ich einen KI-Assistenten der alles lokal verarbeitet, private Daten aktiv nutzbar macht, beim Aufbau täglich Wissen vermittelt — und so strukturiert entwickelt wird dass er in einem Jahr noch genauso funktioniert und verstanden wird?“

Das sind vier Nebenbedingungen in einer Frage, die sprachlich kaum noch zu parsen ist. Inhaltlich ist alles richtig, aber die Form schwächt die Wirkung. Die Übersicht hatte eine viel prägnantere Version:

"Wie baue ich einen KI-Assistenten, der alles lokal verarbeitet, nichts nach außen sendet, und trotzdem mit der Zeit immer smarter wird?"

Diese kürzere Frage war stärker. Entweder du konsolidierst beide Versionen oder du lässt in diesem Dokument bewusst nur die erweiterte stehen – dann aber bitte syntaktisch entzerrt.

2. Grund 1 argumentiert rechtlich, ohne es technisch vollständig zu Ende zu denken
„Kein einziger Byte verlässt das System“ ist technisch korrekt und stark. Aber derselbe Punkt wie in der Übersicht: DSGVO-Konformität umfasst mehr als Datenlokalität. Wenn du schreibst „Die relevanten Rechtsgrundlagen sind eindeutig: DSGVO, AI Act und das GeschGehG schaffen einen Rahmen der lokale Verarbeitung [...] notwendig macht“, dann impliziert das eine juristische Eindeutigkeit, die es so nicht gibt. Lokale Verarbeitung ist eine notwendige, aber keine hinreichende Bedingung für DSGVO-Konformität. Ein Satz zur Einordnung („ermöglicht die technischen Voraussetzungen für...“) würde das präzisieren, ohne die Argumentation zu schwächen.

3. „Beim Aufbau täglich Wissen vermittelt“ – unscharfe Formulierung in der Zielfrage
In der Schlüsselfrage steht: „der beim Aufbau täglich Wissen vermittelt“. Das klingt, als würde SUSI selbst Wissen vermitteln – was nicht stimmt. Gemeint ist: „bei dessen Aufbau ich täglich dazulerne“. Das ist ein feiner, aber wichtiger Unterschied. SUSI ist das Lernobjekt, nicht der Lehrende. Die Formulierung in Grund 3 („Jeder Tag an dem an SUSI gearbeitet wird ist ein Tag an dem konkrete Fähigkeiten entstehen“) ist deutlich präziser.

4. Die Beziehung zwischen Grund 3 und Grund 4 bleibt unausgesprochen
Grund 3 (Lernen durch Bauen) und Grund 4 (Planung für Reproduzierbarkeit) stehen nebeneinander, aber ihre produktive Spannung wird nicht thematisiert: Lernen passiert oft chaotisch, explorativ, durch Scheitern – Planung verlangt Struktur, Voraussicht, Disziplin. Dass du beides gleichzeitig als Motivation beanspruchst, ist interessant und ehrlich, aber ein Satz dazu, wie diese Spannung im Projektalltag produktiv aufgelöst wird, würde den Bericht noch tiefer machen.

5. Kleine sprachliche Details

„Daten gehören nicht nach draußen“ (Überschrift Grund 1) ist umgangssprachlich – im Fließtext ist das okay, in einer Überschrift je nach Zielgruppe vielleicht zu salopp.

„Code der heute funktioniert aber morgen nicht mehr nachvollzogen werden kann“ – Komma fehlt vor „aber“ und vor „der“ (Relativsatz).

„Schwächen die für den ernsthaften persönlichen und beruflichen Einsatz problematisch sind“ – Komma fehlt vor „die“.

Die mehrfache Verwendung von „dass“ in einem Satz („dass er in einem Jahr noch genauso funktioniert und verstanden wird“) ist grammatisch korrekt, aber stilistisch schwer.

Gesamteindruck
Dieses Dokument ist stärker als die Übersicht, weil es tiefer argumentiert, konkreter wird und die konzeptionelle Originalität von SUSI („externes Gedächtnis“) besser herausarbeitet. Die vier Motivationen sind sauber getrennt und jede für sich überzeugend.

Der Hauptkritikpunkt ist die überladene Schlüsselfrage. Ein zweiter Blick lohnt sich auf die juristische Formulierung zu DSGVO – nicht weil sie falsch wäre, sondern weil sie minimal zu absolut formuliert ist und damit angreifbar wird. Der dritte Punkt („Wissen vermittelt“ vs. „ich lerne“) ist ein semantischer Fehler, der korrigiert werden sollte.

Insgesamt: Das Dokument tut genau das, was es verspricht – es erklärt das Warum so fundiert, dass das Was und Wie aus der Übersicht erst richtig an Überzeugungskraft gewinnen.


Positives
1. Das Dokument ist bemerkenswert ehrlich in der Darstellung von Unsicherheit
Die wiederholten Verweise auf den Evaluierungslauf („→ Optimaler Wert nach Grid-Lauf“) sind kein Zeichen von Unfertigkeit, sondern von methodischer Disziplin. Du behauptest nichts, was du nicht gemessen hast. Das ist in Entwicklungsberichten selten und stärkt die Glaubwürdigkeit massiv.

2. Die Stack-Entscheidungen sind knapp und nachvollziehbar begründet
Jede Wahl (Django, ChromaDB, Ollama, LangChain) hat eine klare Begründung, die nicht technisch schwafelt, sondern den Projekthorizont im Blick hat. Besonders stark: „Stabilität vor Novelty“ bei Django – das ist eine Maxime, keine Rechtfertigung.

3. Die differenzielle Ingestion-Pipeline ist mustergültig dokumentiert
MD5-Hash-basierte Änderungserkennung mit selektivem Re-Indexing – das ist technisch sauber, und du erklärst es so, dass auch ein Nicht-Entwickler den Effizienzgewinn versteht („50+ Dateien, nicht alles neu“). Das Flussdiagramm ist selbsterklärend.

4. Die Parameter-Historie ist ein Juwel
Dass du chronologisch dokumentierst, wann welche Entscheidung getroffen, revidiert oder in Evaluation gegeben wurde (Mistral→Qwen, chunk_size 300→1000, k=8→Grid), ist genau die Art von Nachvollziehbarkeit, die du in Grund 4 der Motivation versprichst. Du lieferst hier den Beweis, dass du das Prinzip lebst.

5. Das Mistral-„Sie“-Problem ist ein fantastisches Detail
Dass ein Modell trotz explizitem Prompt in die Höflichkeitsform zurückfällt, ist eine dieser echten, nervigen Probleme, die man nur im Realbetrieb findet. Dass du das dokumentierst, macht den Bericht lebendig und glaubwürdig – das ist kein theoretisches Paper, hier hat jemand wirklich gebaut.

6. Die Lernparadigmen-Tabelle ist konzeptionell stark
Die Gegenüberstellung von Gradientenabstieg und RAG (Transparenz, Reversibilität, Kontrollierbarkeit) ist eine der besten Explikationen deines Designprinzips im gesamten Material. Das ist kein technisches Detail, das ist Architekturphilosophie – und sie steht genau da, wo sie hingehört.

7. Die LoRA-Ausführung ist fundiert und ehrlich im Scope
Du erklärst LoRA präzise, nennst realistische Zahlen (RTX 3090, 50 MB, 10–30 Min), und machst klar, dass das Phase 3 ist – nicht jetzt. Der Satz „LoRA ist kein neues Konzept — es taucht in der Literatur regelmäßig auf. Der Moment wo es vom gelesenen Begriff zum verstandenen Werkzeug wird ist genau der Moment der durch Bauen entsteht“ ist eine der besten Formulierungen im gesamten Bericht. Das trifft den Kern deines Lernansatzes.

Negatives / Widersprüchliches / Verbesserungswürdiges
1. Die Auto-Save-Pipeline ist architektonisch noch aktiv – aber gleichzeitig als verworfen markiert
Das ist der gravierendste Widerspruch im gesamten bisherigen Material. Du schreibst in der Tabelle am Ende: „Auto-Save | aktiv (zu ersetzen) | 3-Stufen-Architektur“. Und im Abschnitt „Was verworfen wurde“ steht: „Auto-Save Pipeline (verworfen Mai 2026)“. Aber der Code ist noch in query.py, die Pipeline ist dokumentiert, und es gibt keinen klaren Hinweis, ob sie jetzt tatsächlich deaktiviert oder nur als Problem erkannt ist. Wenn das System produktiv läuft und die Pipeline noch aktiv ist, dann schreibt SUSI potenziell Halluzinationen in die Wissensbasis – trotz erkannter zerstörerischer Feedback-Schleife. Das muss entweder technisch behoben oder im Dokument glasklar als „erkannt, deaktiviert, Nachfolger in Arbeit“ markiert sein.

2. Chunk-Größe: Geplant aber nicht implementiert – warum?
Du schreibst: „Geplant aber nicht implementiert (April 2026): Differenzierte Chunk-Größen — 300/50 für persönliche Inhalte, 500/100 für technische Inhalte. Die Logik war inhaltlich sinnvoll [...]. In der Praxis wurde die Differenzierung jedoch nicht in ingest.py umgesetzt.“ – Aber warum nicht? Fehlende Zeit? Technische Hürde? Andere Priorität? Die Lücke in der Begründung fällt auf, weil sonst jede Entscheidung begründet ist. Ein Satz dazu würde das schließen.

3. Die „auskommentierte strengere Variante“ des System-Prompts ist interessant, aber unklar dokumentiert
Du erwähnst eine strengere Prompt-Variante, die zu vielen „Dazu habe ich nichts“-Antworten führte. War sie komplett verworfen? Oder gibt es Szenarien, in denen absolute Kontextbindung sinnvoll wäre (z.B. bei strikt DSGVO-relevanten Fragen)? Die Begründung für die aktuelle Variante ist gut, aber die Abgrenzung zum verworfenen Ansatz könnte schärfer sein.

4. Hybrid Search wird erwähnt, aber nicht erklärt
„Die bekannte Schwäche ist kein natives Hybrid Search (BM25 + Vektoren).“ – Für technisches Publikum ist das klar. Aber im Gesamtdokument (das auch auf Entscheider abzielt) taucht der Begriff BM25 unvermittelt auf. Eine Halb-Satz-Erklärung („Keyword-Suche kombiniert mit Vektorsuche“) würde die Verständlichkeit erhöhen, ohne das technische Niveau zu senken.

5. Die abschließende Architektur-Tabelle ist unübersichtlich formatiert
Die Tabelle listet sauber „Aktuell“ und „In Evaluation“, aber sie enthält Einträge, die nicht selbsterklärend sind:

„ChromaDB (ggf. Weaviate)“ – das ist spekulativ und kein klarer Evaluationsgegenstand

„+llama3.1:8b, gemma2:9b“ – das Pluszeichen ist ungewöhnlich; meinst du „qwen2.5-coder:7b + llama3.1:8b + gemma2:9b“? Oder ist qwen der Baseline und die anderen werden verglichen?

Das ist ein kleines visuelles Problem, das in der Rezeption stolpern lässt.

6. Kleine sprachliche Details

„Zero-Dependency“ – meinst du „Zero-Dependencies“ (Plural) oder „keine externen Abhängigkeiten“? So wie es da steht, klingt es nach einem Produktnamen.

„Das ist die praktische Umsetzung des Prinzips 'das Modell ist austauschbar'.“ – Das Prinzip wird in der Übersicht groß eingeführt, hier aber nur beiläufig referenziert. Ein expliziter Rückbezug würde die Stringenz erhöhen.

„Prompt-Verschärfung half, löste das Problem aber nicht dauerhaft.“ – Guter Satz, aber Komma vor „löste“ wäre korrekt (Aufzählung zweier Hauptsätze).

Im Lernparadigmen-Abschnitt: „Es gibt einen dritten Weg der beide Ansätze verbindet“ – Komma vor „der“ fehlt.

Gesamteindruck
Das ist das technisch stärkste der drei Dokumente. Es zeigt, dass du nicht nur konzipierst, sondern wirklich implementierst, evaluierst und iterierst. Die Parameter-Historie und die Lernparadigmen-Darstellung sind Abschnitte, die man in dieser Klarheit selten sieht.

Der einzige ernsthafte Kritikpunkt ist der Status der Auto-Save-Pipeline – hier klaffen Dokumentation und architektonische Realität auseinander, und das ist genau die Art von Widerspruch, den dein eigenes Qualitätsversprechen („systematische Optimierung statt Raten“) nicht zulassen sollte. Das muss priorisiert geklärt werden.

Alles andere sind kleinere Inkonsistenzen oder Verständlichkeitsoptimierungen, die den bereits hohen Standard weiter anheben.


Positives
1. Die Formatierungsregeln sind außergewöhnlich gut durchdacht
Das ist kein theoretisches „Best Practices“-Dokument, sondern eine Sammlung von Regeln, die aus nachvollziehbaren RAG-spezifischen Gründen existieren. Jede Regel hat eine klare technische Begründung („Chunk muss alleine verständlich sein“, „Embedding-Modelle sind auf natürliche Sprache optimiert“), und der automatisierte Checker macht die Einhaltung überprüfbar. Das ist Qualitätssicherung auf einem Niveau, das viele kommerzielle RAG-Systeme nicht haben.

2. Topic-Label Ankersatz ist eine echte Innovation
Die Anforderung, dass jeder H2-Abschnitt im ersten Satz seinen vollständigen Kontext nennen muss, ist eine simple, aber geniale Lösung für das Chunk-Kontext-Problem. Das Beispiel (falsch: „Es besteht aus drei Layern“ / richtig: „Die StockPredict V2 Architektur besteht aus drei Layern…“) macht sofort verständlich, worum es geht. Das ist genau die Art von praktischer Erkenntnis, die man nur durch Betrieb gewinnt.

3. Die 5 Qualitätsprobleme sind präzise, ehrlich und vollständig analysiert
Jedes Problem hat Ursache, Konsequenz und Lösung – und die Probleme sind real, nicht konstruiert. Besonders stark:

Encoding-Fehler mit der UMLAUT_FIXES-Liste zeigt, dass du dich mit den hässlichen Details der Textverarbeitung auseinandergesetzt hast.

Veraltete technische Angaben als erkanntes Problem zu dokumentieren ist ehrlich – viele Entwickler würden das unter den Teppich kehren.

Dass du die Lücken des Checkers benennst (keine Inhaltsprüfung), zeugt von methodischer Redlichkeit.

4. Die entdeckten Inhaltsfehler sind Gold wert
Vertauschte Dateiinhalte und ein Duplikat mit falschem Namen – das sind Fehler, die in jedem wachsenden System passieren. Dass du sie dokumentierst, analysierst (inklusive der Retrieval-Konsequenzen: „inhaltlich falsch aber syntaktisch plausibel“) und einen Verbesserungsvorschlag machst (Content-Hash-Vergleich), ist vorbildliche Entwicklungsdokumentation.

5. Die .gitignore-Whitelist-Strategie ist technisch elegant
Statt sensible Ordner einzeln auszuschließen (und bei neuen Ordnern zu vergessen), wird alles ignoriert und nur explizit erlaubt. Das Sicherheitsprinzip gilt automatisch für zukünftige Inhalte. Die anschließende git filter-repo-Bereinigung ist die korrekte und vollständige Lösung – keine halben Sachen.

6. Der Abschnitt zur Datensicherheit schafft Vertrauen
Dass du die genauen Ordner auflistest, die öffentlich/nicht öffentlich sind, und die History-Bereinigung dokumentierst, zeigt Transparenz. Ein potenzieller Nutzer oder Arbeitgeber sieht sofort: Hier denkt jemand Sicherheit zu Ende.

Negatives / Widersprüchliches / Verbesserungswürdiges
1. Widerspruch: Die Formatierungsregeln sollen öffentlich sein – aber nicht die sensiblen Bereiche?
Das ist kein Widerspruch, sondern eine Unschärfe: Die Formatierungsregeln sind öffentlich auf GitHub einsehbar und erklären detailliert, wie SUSIpedia funktioniert. Das ist gut für Transparenz und mögliche spätere Anwender. Aber du sagst im Intro der Übersicht, dass die Formatierung „nicht auf menschliche Lesbarkeit, sondern auf Retrieval optimiert“ sei – und zeigst hier, dass die Regeln beides leisten. Die Spannung zwischen diesen beiden Aussagen bleibt. Eine Klarstellung („die Regeln sind für Menschen verständlich dokumentiert, aber die Wissensdateien selbst priorisieren Retrieval-Qualität über Lesekomfort“) wäre hilfreich.

2. „Maximal drei Heading-Ebenen“ – aber H3 erzeugt laut Problem 5 zu kleine Chunks?
Du schreibst unter Formatierungsregeln: „H3 = Detail zum darüberliegenden Abschnitt, nur wenn nötig.“ Und unter Problem 5: „H3 erzeugt zu kleine Chunks ohne ausreichend semantischen Kontext.“ Das wirft die Frage auf: Wann ist H3 dann überhaupt sinnvoll? Wenn H3 problematisch kleine Chunks erzeugt, müsste die Regel entweder lauten „H3 vermeiden“ oder es müsste definiert sein, unter welchen Bedingungen H3 unproblematisch ist (z.B. nur in sehr langen Dokumenten, wo der H2-Chunk selbst schon groß ist). So wie es da steht, empfiehlst du eine Praxis, von der du gleichzeitig sagst, dass sie Probleme macht.

3. Die 5 Qualitätsprobleme sind vermischt: technische Fehler vs. strukturelle Prinzipien
Encoding-Fehler (Problem 1) und Bullet-Listen (Problem 2) sind Probleme der Umsetzung, nicht der Architektur. Fehlende Topic-Label (Problem 3) und veraltete Angaben (Problem 4) sind Wartungsprobleme. H3/Code-Blöcke (Problem 5) sind Regelverstöße. Die Liste fasst sehr unterschiedliche Fehlerkategorien zusammen – das ist didaktisch okay, aber für die systematische Optimierung wäre eine Unterscheidung nach Fehlertyp (technisch / redaktionell / strukturell) klarer.

4. Die .gitignore-Syntax ist erklärungsbedürftig
Du zeigst den .gitignore-Inhalt, aber für Nicht-Git-Experten ist die Logik von docs/* gefolgt von !docs/projekte/ nicht sofort ersichtlich. Ein Satz zur Erklärung des Ausrufezeichens (Negation) würde die Zugänglichkeit erhöhen.

5. Kleine sprachliche Details

„Eine strukturierte Sammlung von Markdown-Dateien die als einzige Wissensquelle […] dient“ – Komma vor „die“ fehlt.

„Der entscheidende Designgedanke dahinter“ – gemeint ist „dahinter“ (Rechtschreibung).

„Encoding-Fehler (UTF-8 / Windows)“ – das „/ Windows“ ist verwirrend; gemeint ist wohl „UTF-8-kodierte Dateien, die fälschlich als Windows-1252/Latin-1 interpretiert wurden“.

„Das Wissen gehört dem Nutzer, nicht dem Anbieter“ – im SUSI-Kontext ist „der Nutzer“ Martin selbst. Der Satz funktioniert trotzdem, aber für die spätere Mehrbenutzer-Vision (Geschäftspotenzial) müsste er anders formuliert werden.

„als wären sie nie committed worden“ – stilistisch stark, aber das englische „committed“ im deutschen Fließtext; „als wären sie nie eingecheckt worden“ wäre konsistenter deutsch, aber „committed“ ist in Git-Kontext etabliert. Grenzfall.

6. Der Content-Hash-Vergleich als Lösung ist erwähnt, aber nicht spezifiziert
Du schreibst: „Ein Content-Hash-Vergleich zwischen Dateiname und H1-Titel wäre eine sinnvolle Erweiterung.“ Das ist ein interessanter Vorschlag, aber die genaue Logik bleibt unklar. Meinst du einen Hash des Dateinamens verglichen mit einem Hash des H1-Titels? Oder eine semantische Ähnlichkeitsprüfung? Für das Dokument wäre eine kurze Präzisierung hilfreich.

Gesamteindruck
Das ist das handwerklich solideste Dokument der Reihe. Es zeigt ein System, das nicht nur konzipiert, sondern im täglichen Betrieb gehärtet ist. Die Formatierungsregeln, der automatisierte Checker, die Fehleranalyse und die Git-Strategie sind auf einem Niveau, das man in Open-Source-Projekten selten und in Ein-Personen-Projekten fast nie sieht.

Die einzigen strukturellen Verbesserungspunkte sind:

Das H3-Problem – hier widersprechen sich Regel und diagnostiziertes Problem.

Die Vermischung der Fehlerkategorien in den 5 Qualitätsproblemen.

Der nie ganz aufgelöste Widerspruch zwischen „nicht auf Lesbarkeit optimiert“ und den tatsächlich sehr gut lesbaren Dokumenten.

Alles andere sind Kleinigkeiten. Dieses Dokument würde ich in dieser Form als Teil einer Bewerbung oder Projektvorstellung für absolut überzeugend halten.



Positives
1. Das Finding vom 10.06.2026 ist ein dokumentarischer Glücksfall
Der Sprung von 36% auf 91% Hit Rate, ausschließlich durch Dokumentqualität – das ist ein empirischer Beleg, den man sich nicht schöner ausdenken könnte. Dass du den Stack nicht verändert hast („Kein besseres Modell wurde eingesetzt“) und trotzdem eine Verbesserung um 55 Prozentpunkte erzielst, ist ein direkter Beweis für die Kernthese des gesamten Projekts. Das ist das stärkste Argument im gesamten Material – und es steht genau da, wo es hingehört: im Evaluierungskapitel.

2. Die Trennung von Retrieval und Generation ist methodisch vorbildlich
Dass du zwei separate Ebenen misst (Retrieval Check ohne LLM, End-to-End mit BERTScore/ROUGE/manuell) und die Erkenntnis ziehst „Was das Retrieval nicht findet, kann kein Prompt der Welt reparieren“ – das ist kein Slogan, das ist eine testbare Hypothese, die du belegst. Der Retrieval Check (70% Hit Rate → maximal 70% End-to-End erreichbar) macht das quantitativ nachvollziehbar.

3. Die chronologische Dokumentation mit Config-Strings ist exzellent reproduzierbar
Jeder Lauf hat einen exakten Config-String (z.B. bge-m3 | chunk=1000/o50 | k=5 | similarity | qwen2.5-coder:7b | temp=0.0 | prompt=susi_standard). Das ist keine Prosa – das ist eine vollständige Versuchsbeschreibung. Jeder, der das System nachbauen will, kann diese Läufe exakt reproduzieren. Das erfüllt den Anspruch aus Grund 4 der Motivation („Planung als Grundlage für Reproduzierbarkeit“) mit Bravour.

4. Die Miss-Analyse ist diagnostisch, nicht beschreibend
Statt nur zu sagen „Projekte funktionieren schlecht“, identifizierst du drei wiederkehrende Muster mit konkreten Beispielen und Lösungsvorschlägen:

Duplikat-Dateien an verschiedenen Orten → Bereinigung

GMM-Fragen landen bei CI/CD → Topic-Label stärken

Persönliche Fragen ohne klare Datei-Zuordnung → stärkere Differenzierung

Das ist genau die Art von systematischer Fehleranalyse, die den Unterschied zwischen „Herumprobieren“ und „Optimieren“ ausmacht.

5. Die Relativierung der Smoke-Tests ist intellektuell ehrlich
Du zeigst stolz 94% und 97% in den Smoke-Tests, aber relativierst sofort mit dem vollen Datensatz (64%). Diese Selbstkorrektur („optimierte Smoke-Tests sind überoptimistisch – der volle Datensatz ist der ehrlichere Maßstab“) ist ein Markenzeichen seriöser Evaluierung. Viele würden die 94% fett drucken und die 64% in den Anhang verbannen.

6. Die Skalen-Korrektur ist transparent dokumentiert
„Hinweis: Frühere Auswertungen (Lauf 2, 7, 8) enthielten durch einen Bewertungs-Fehler Scores auf einer 0–5-Skala — diese wurden nachträglich auf 0–3 normiert.“ – Dass du diesen Fehler nicht verschweigst, sondern dokumentierst und korrigierst, ist vorbildliche wissenschaftliche Praxis.

7. Die offenen Fragen sind präzise und priorisiert
MMR, Hybrid Search, Cross-Encoder, kategorie-spezifische Optimierung – vier klar benannte nächste Schritte mit Begründung. Das ist eine Forschungsagenda, kein Wunschzettel.

8. Der Zeitverlauf macht den Fortschritt sichtbar
Die chronologische Liste von Lauf 1 bis Retrieval Check zeigt den Fortschritt von 48% auf 91% Hit Rate in knapp drei Wochen. Das ist eine steile Lernkurve, die durch die Dokumentation nachvollziehbar wird – inklusive Rückschlägen (Lauf 7 mit k=3 fällt auf 81%, Lauf 8 auf 64%).

Negatives / Widersprüchliches / Verbesserungswürdiges
1. Unstimmigkeit: Lauf 7 in der Zeitverlaufsliste vs. Detailbeschreibung
In der Detailbeschreibung von Lauf 7 steht: „Fragen: 61 manuell bewertet“ und Korrektheit 81%. In der zusammenfassenden Zeitverlaufsliste steht: „Lauf 7, gemischt, n=160“. Das sind zwei unterschiedliche Stichprobengrößen. 61 vs. 160 ist ein erheblicher Unterschied. Welche Zahl stimmt? Falls 160 die Gesamtzahl ist (über alle 5 Prompt-Varianten) und 61 eine Teilmenge – dann sollte das erklärt werden. So wie es jetzt da steht, ist es ein Widerspruch, der die ansonsten vorbildliche Reproduzierbarkeit untergräbt.

2. Lauf 6: „praezise_Cain_of_Thought“ – Tippfehler oder bewusste Schreibweise?
„Cain“ statt „Chain“ – falls das ein Tippfehler ist, sollte er korrigiert werden. Falls es eine bewusste, ironische Schreibweise ist (Cain = Kain, der Brudermörder?), wäre eine Erklärung nötig, weil es sonst wie ein Fehler wirkt. In einem Dokument, das so viel Wert auf Präzision legt, fällt das auf.

3. Lauf 3 und Lauf 6/8: Warum sinkt die Korrektheit mit derselben Konfiguration?
Lauf 3: bge-m3, chunk=1000, k=5, similarity, qwen2.5-coder:7b, temp=0.0, susi_standard → 94% (n=384)
Lauf 8: bge-m3, chunk=1000, k=5, similarity, qwen2.5-coder:7b, temp=0.0, praezise_neu → 64% (n=239)

Du erklärst das teilweise mit „voller Datensatz vs. Smoke-Test“, aber Lauf 3 hatte n=384 – also sogar mehr Fragen als Lauf 8 (n=239). Wenn Lauf 3 ein „voller Datensatz“ war, warum dann der Absturz auf 64% in Lauf 8? Mögliche Erklärungen: anderer Prompt (susi_standard vs. praezise_neu), andere Fragen-Zusammensetzung, oder Lauf 3 war doch ein optimierter Smoke-Test. Das ist eine argumentative Lücke, die geschlossen werden muss. Die Relativierung der Smoke-Tests ist gut, aber die Zahlen müssen konsistent sein.

4. Das Finding vom 10.06. – die drei Stufen sind nicht sauber getrennt
Du schreibst:

Start (unkonfiguriert, 230 Fragen): 36%

Nach Bereinigung (Encoding-Fixes, Duplikate): 53%

Nach SUSIpedia-Überarbeitung + chunk=1000: 91%

Aber „+ chunk=1000“ in der dritten Stufe durchbricht das Argument, dass ausschließlich Dokumentqualität verbessert wurde. Chunk-Größe ist ein Retrieval-Parameter, keine Dokumentqualität. Wenn du die dritte Stufe als „Dokumentqualität + optimale Chunk-Größe“ bezeichnest, ist das korrekt – aber der Satz „Kein besseres Modell wurde eingesetzt“ suggeriert, dass nur die Dokumente verändert wurden. Die chunk_size-Änderung von 300 auf 1000 ist kein Modellwechsel, aber eine Parameteränderung. Ehrlicher wäre: „Derselbe Stack, optimierte Dokumente, optimale Chunk-Größe“.

5. Die Normierung der Bewertungsskala wird erwähnt, aber nicht erklärt
„Hinweis: Frühere Auswertungen (Lauf 2, 7, 8) enthielten durch einen Bewertungs-Fehler Scores auf einer 0–5-Skala — diese wurden nachträglich auf 0–3 normiert.“ – Die Tatsache der Normierung ist transparent. Aber wie wurde normiert? Lineare Transformation (Score * 3/5)? Oder manuelles Re-Mapping? Bei nichtlinearer Transformation könnten die Werte verzerrt sein. Ein Satz zur Methode würde das abschließen.

6. Geplante Folgeläufe: Lauf B referenziert Lauf 7 mit 98% – aber Lauf 7 hatte 81%
Im Abschnitt „Geplante Folgeläufe“ steht: „Lauf 7 erreichte 98% — aber nur auf 61 Fragen.“ In der Detailbeschreibung von Lauf 7 steht aber 81% Korrektheit. 98% vs. 81% ist ein eklatanter Widerspruch. Möglicherweise verwechselst du Lauf 7 mit Lauf 6 (praezise_alt: 97%). Das muss korrigiert werden.

7. Kleine sprachliche und strukturelle Details

„Das Evaluierungsframework beantwortet zwei fundamentale Fragen“ – Komma vor „dass“ fehlt im folgenden Nebensatz („Von Anfang an war klar dass ein System…“).

Die Skala-Definition (0–3) ist gut, aber die Verwendung von „Score“ und „normiertem Score“ im selben Absatz ohne klare Trennung kann verwirren. Eine visuelle Trennung oder ein Hinweis „Rohscore / normiert“ würde helfen.

„Das ist überraschend und widerspricht der Intuition dass weniger Chunks weniger Kontext-Mixing bedeuten“ – Komma vor „dass“ fehlt.

Lauf 7: „Der Smoke-Test lief zudem über alle 5 Prompt-Varianten gleichzeitig“ – aber Lauf 7 ist ein einzelner Lauf mit einer Config. Meinst du, dass die 61 Fragen aus 5 verschiedenen Prompt-Tests stammen? Das sollte klarer sein.

Gesamteindruck
Das ist das wissenschaftlich fundierteste und überzeugendste Dokument der Reihe. Es zeigt, dass du nicht nur ein System gebaut, sondern es auch systematisch evaluiert hast – mit reproduzierbaren Configs, Metrik-Triangulation, Fehleranalyse und einer klaren Forschungsagenda. Das Finding vom 10.06.2026 ist ein starkes empirisches Argument, das die Kernthese des Projekts direkt belegt.

Es gibt jedoch zwei ernsthafte Widersprüche, die vor einer Veröffentlichung oder Vorstellung korrigiert werden sollten:

Die inkonsistenten Stichprobengrößen und Prozentwerte zwischen Lauf-Details und Zeitverlaufsliste (n=61 vs. n=160; 81% vs. 98%).

Die ungeklärte Diskrepanz zwischen Lauf 3 (94%, n=384) und Lauf 8 (64%, n=239) bei ähnlicher Konfiguration.

Diese Punkte sind kein Beinbruch – sie sind typische Artefakte einer ehrlichen, iterativen Evaluierung, bei der manchmal Zahlen aus verschiedenen Quellen zusammengeführt werden. Aber sie müssen bereinigt werden, weil sie die ansonsten vorbildliche Glaubwürdigkeit des Evaluierungskapitels untergraben.


Positives
1. Die vier Sackgassen sind meisterhaft analysiert
Jede einzelne ist in sich schlüssig: klare Beschreibung des Ansatzes, präzise Begründung der Verwerfung, extrahierte Kernerkenntnis. Das ist keine Liste von Fehlern – das ist eine Sammlung von Designprinzipien, die durch negative Evidenz gewonnen wurden. Besonders stark:

Sackgasse A (Self-Poisoning): „Eine zerstörerische Feedback-Schleife die sich selbst verstärkt“ – du benennst das Problem nicht nur, du erklärst den Mechanismus (schreiben → retrieven → bestätigen → verstärken). Das ist systemtheoretisch präzise.

Sackgasse B (LLM als Redakteur): „Der Bock als Gärtner“ – selten eine treffendere Metapher gesehen. Die Erkenntnis, dass Konsolidierung eine redaktionelle Aufgabe ist, ist fundamental.

Sackgasse C (Blindes Anhängen): „Chronologisches Anhängen ist Versionskontrolle ohne Versionskontrolle“ – ein Satz, der das Problem vollständig erfasst.

Sackgasse D (Mathematische Filter): „Mathematik kann Ähnlichkeit messen aber nicht Relevanz beurteilen“ – das ist eine philosophisch präzise Unterscheidung mit massiven praktischen Konsequenzen.

2. Die 3-Stufen-Architektur ist technisch ausgereift und ehrlich
Die SQLite-Persistenz, der Modell-Wechsel für die Zusammenfassung, der Cross-Encoder als Türsteher, das Review-Dashboard – jede Stufe ist konkret beschrieben und technisch begründet. Dass du die Sprachbarriere bei deutschen Texten und die Lösung (mehrsprachige Modelle statt Standard-DeBERTa) explizit thematisierst, zeigt, dass du das Problem durchdacht hast, nicht nur beschrieben.

3. Die Architektur respektiert die Erkenntnisse aus der Evaluation
Das ist kein Wunschkonzert – die neue Architektur adressiert präzise die Probleme, die in der Evaluation sichtbar wurden: Self-Poisoning (→ Cross-Encoder), Duplikate (→ Quarantäne + Review), Kontext-Mixing (→ spezialisiertes Zusammenfassungsmodell mit Template). Die Konsistenz zwischen Evaluation und Architektur ist ein Qualitätsmerkmal, das man selten sieht.

4. Das 5-Sekunden-Review mit der Kontroll-Matrix ist praxistauglich
Die Matrix (Frage | Quell-Chunks | Entwurf) ist genau das Minimum an Information, das ein Mensch braucht, um eine fundierte Entscheidung zu treffen – nicht mehr, nicht weniger. Die Idee, abgelehntes Material in eine RejectedSaves-Tabelle zu schicken, ist ein brillanter Nebeneffekt: automatisch wachsendes Negativ-Trainingsset.

5. Die abschließende Design-Philosophie ist prägnant und wahr
„Die KI ist ein hocheffizienter Sekretär der Entwürfe vorschreibt und vorprüft. Der Mensch behält die absolute Datenhoheit.“ – Das ist keine defensive Formulierung, sondern eine positive Neudefinition der Mensch-KI-Arbeitsteilung. Das Zitat am Ende („Human-in-the-Loop ist keine Einschränkung der KI. Es ist die Voraussetzung für Vertrauen in die KI.“) ist stark genug, um als Leitmotiv für das gesamte Projekt zu stehen.

6. Die sprachliche Qualität ist durchgehend hoch
Formulierungen wie „ein System das sich selbst vergiftet produziert keine offensichtlichen Fehler — es produziert plausibel klingende falsche Antworten“ sind präzise, bildstark und frei von Jargon. Der Text hat einen Rhythmus, der technische Dokumentation selten erreicht.

Negatives / Widersprüchliches / Verbesserungswürdiges
1. Status der Auto-Save-Pipeline: Immer noch unklar
In der Übersicht (00) stand: „Auto-Save | aktiv (zu ersetzen) | 3-Stufen-Architektur“. Hier in 05 wird Sackgasse A als „Verworfen“ bezeichnet, aber es gibt keinen Satz, der explizit sagt: „Die Pipeline wurde am [Datum] deaktiviert und ist nicht mehr in Betrieb.“ Das ist der gleiche Widerspruch, den ich bereits im Architektur-Dokument angemerkt habe – und er setzt sich hier fort. Ein System, das produktiv läuft und eine erkannt zerstörerische Feedback-Schleife enthält, ist ein dokumentarisches Problem. Ein klarer Satz zum aktuellen Produktivstatus ist überfällig.

2. Die Sprachbarriere-Problematik ist wichtig, aber unvollständig
Du schreibst: „Standard-Cross-Encoder-Modelle aus der DeBERTa-Familie […] sind auf englischen Korpora trainiert. Bei deutschen SUSIpedia-Chunks […] entsteht eine hohe False-Negative-Rate.“ – Das ist eine starke technische Aussage. Aber: Ist das eine empirische Beobachtung aus Tests mit SUSI-Daten oder eine allgemeine Annahme basierend auf der Trainingskorpus-Dokumentation? Der Unterschied ist wichtig, denn in den geplanten Folgeläufen der Evaluation (04) steht der Cross-Encoder noch als offene Frage. Hier wird er als Lösung präsentiert, aber die Validierung fehlt. Ein Satz zur empirischen Basis würde das stärken.

3. Die Grenzen des Cross-Encoders werden nicht thematisiert
Der Cross-Encoder prüft: „Geht die Zusammenfassung logisch aus den echten Quell-Chunks hervor?“ – aber was ist mit dem Fall, dass die Quell-Chunks selbst bereits falsch sind (z.B. eine unentdeckte Halluzination aus einer früheren, manuell freigegebenen Konversation)? Der Cross-Encoder würde eine logisch konsistente Zusammenfassung aus falschen Chunks durchwinken. Das ist ein bekanntes Problem („Garbage In, Garbage Out“), das in der Architekturbeschreibung nicht adressiert wird. Die Sicherheitskette ist nur so stark wie ihr schwächstes Glied.

4. Das Zusammenfassungs-Modell (llama3.1:8b) wird als „logisch stärker“ bezeichnet – aber ist es das?
Du schreibst: „Django pausiert kurz den Live-Coder (qwen2.5-coder:7b) und lädt über Ollama ein logisch stärkeres Modell (z.B. llama3.1:8b)“. Die Begründung („logisch stärker“) ist eine Behauptung ohne Beleg. Aus der Evaluation (04) wissen wir, dass qwen2.5-coder:7b und llama3.1:8b beide in der Evaluations-Matrix stehen – aber es gibt noch keine Ergebnisse, die zeigen, dass llama bei Zusammenfassungen besser abschneidet. Ein Verweis auf die anstehenden Evaluierungsergebnisse oder eine Begründung (z.B. „llama hat in Benchmarks bessere Scores bei Summarization-Aufgaben“) wäre nötig.

5. Die SQLite-Persistenz ist erwähnt, aber das Schema bleibt vage
„Der aktuelle Chatverlauf wird persistent in einer lokalen SQLite-Tabelle gehalten“ – aber welche Felder? Wie wird bereinigt? Was passiert mit langen Chatverläufen? Im Vergleich zur ansonsten detaillierten Architekturbeschreibung (Chunk-Größen, MD5-Hashes, Retrieval-Algorithmen) bleibt Stufe 1 auffällig unspezifisch. Das könnte Absicht sein (weil noch in Entwicklung), aber ein Satz dazu („Schema in Entwicklung, Details folgen“) würde die Lücke benennen statt sie offen zu lassen.

6. Der Abschnitt „Was diese Evolution bedeutet“ wiederholt teilweise die Kernerkenntnisse der Übersicht
Die Aussage „die KI ist ein hocheffizienter Sekretär“ ist stark, aber sie überschneidet sich mit Kernerkenntnis 4 aus der Übersicht („Human-in-the-Loop ist kein Kompromiss“). Das ist keine echte Redundanz – eher eine Gelegenheit zur Schärfung. Die Übersicht könnte auf diese Stelle verweisen („→ siehe 05 für die vollständige Begründung“), oder dieser Abschnitt könnte eine zusätzliche Perspektive bieten (z.B. was die Evolution für zukünftige Designentscheidungen bedeutet).

7. Kleine sprachliche Details

„Ein Entwicklungsprozess der keine Sackgassen kennt ist kein ehrlicher Entwicklungsprozess“ – Komma vor „der“ fehlt.

„Eine zerstörerische Feedback-Schleife die sich selbst verstärkt“ – Komma vor „die“ fehlt.

„Der Markdown-Entwurf wird durch ein kleines spezialisiertes Cross-Encoder-Modell geprüft (~100M Parameter, läuft auf der CPU) bei temperature=0.0“ – Komma vor „bei“ wäre hilfreich (Aufzählung).

„Abgelehntes Material wandert in eine RejectedSaves-Tabelle — perfektes Testmaterial für zukünftige Prompt-Optimierungen und ein automatisch wachsendes Negativ-Trainingsset“ – das ist ein herausragender Satz, aber „Prompt-Optimierungen und ein automatisch wachsendes Negativ-Trainingsset“ hängen syntaktisch etwas in der Luft. Ein „dient als“ dazwischen würde helfen.

Gesamteindruck
Das ist das konzeptionelle Herzstück des gesamten Projekts. Die vier Sackgassen sind nicht nur ehrlich dokumentiert – sie sind in einer analytischen Tiefe durchdrungen, die aus Fehlern echte Designprinzipien extrahiert. Die 3-Stufen-Architektur ist technisch ausgereift, ehrlich in ihren Grenzen (Sprachbarriere) und konsequent aus den Erkenntnissen der Evaluation abgeleitet.

Die Probleme liegen nicht in der Architektur selbst, sondern in der Dokumentation ihres aktuellen Status:

Der Widerspruch zwischen „verworfen“ und „aktiv“ bei der Auto-Save-Pipeline muss aufgelöst werden.

Die empirische Basis für die Cross-Encoder-Entscheidung und die llama3.1-Wahl sollte klarer sein.

Das sind dokumentarische, nicht architektonische Probleme. Die Architektur selbst ist überzeugend und konsistent.


Positives
1. Das Dokument zeigt höchste dokumentarische Reife
Hier dokumentiert jemand Fehler, die durch externe Reviewer aufgedeckt wurden, und stellt sie als „vollwertige Erkenntnisse“ dar. Das ist die Königsklasse der Projektdokumentation: nicht nur eigene Fehler zugeben, sondern aktiv die Fremdkritik als Lernquelle würdigen. Der Satz „Sie werden hier nicht als Randnotizen behandelt sondern als vollwertige Erkenntnisse“ ist ein Statement zur Dokumentationsphilosophie.

2. Jede Grenzerfahrung ist ein vollständiger Case Study
Aufbau: Was ist passiert → Warum ist es passiert → Was bedeutet das → Die Lektion. Das ist dieselbe Struktur wie bei den Sackgassen in 05, und sie funktioniert genauso gut. Besonders stark:

Grenzerfahrung 1 (Skalenfehler): „Mathematisch unmöglich: ein Mittelwert über dem definierten Maximum“ – das ist ein harter, objektiver Fehler, den du nicht beschönigst. Die Lektion („Metriken-Definitionen gehören in den Code, nicht in die Dokumentation“) ist eine echte Prozessverbesserung.

Grenzerfahrung 3 (VRAM-Deadlock): Die Beschreibung des synchronen Modellwechsels mit einfrierendem Frontend ist konkret und nachvollziehbar. Die Lektion („Async-First ist keine Optimierung sondern eine Grundanforderung“) ist ein direktes architektonisches Prinzip.

Grenzerfahrung 4 (Tabellen-Verbot): Das ist eine Selbstkorrektur auf Metakognitionsebene – du hinterfragst deine eigene Regel, erkennst ihren blinden Fleck und findest eine präzisere Lösung. „Das Embedding-Modell greift die Prosa für Retrieval, das LLM greift den Codeblock für Generierung“ ist eine elegante Trennung der Zuständigkeiten.

3. Die Integration mit anderen Dokumenten ist vorbildlich

Grenzerfahrung 1 erklärt und validiert die Normierungs-Hinweise in 04.

Grenzerfahrung 2 und 3 präzisieren und validieren die Architektur in 05.

Grenzerfahrung 4 verbessert die Formatierungsregeln aus 03.

Das ist keine isolierte Fehlerliste – das sind Errata und Präzisierungen für den gesamten Bericht, mit klaren Verweisen auf die betroffenen Systemkomponenten.

4. Die Meta-Erkenntnis am Ende ist philosophisch stark
„Eine Entscheidung die auf einem gültigen Prinzip basierte hat einen blinden Fleck in der Umsetzung.“ – Das ist keine Selbstkritik, das ist eine Systemerkenntnis. Der Hinweis auf den Wert externer Reviews („weil Implizites explizit wird“) ist der perfekte Abschluss für ein Kapitel, das von externer Prüfung profitiert hat.

5. Sprachlich präzise und frei von Selbstmitleid
Der Ton ist sachlich, analytisch, ohne defensiv zu sein. Kein „leider ist uns aufgefallen“, kein „bedauerlicherweise“. Stattdessen klare Diagnosen und Lektionen.

Negatives / Widersprüchliches / Verbesserungswürdiges
1. Die Auto-Save-Pipeline – jetzt haben wir drei Dokumente mit unklarem Status
In 00 steht: „Auto-Save | aktiv (zu ersetzen) | 3-Stufen-Architektur“. In 05 steht: „Verworfen“. In 06 steht indirekt (über Grenzerfahrung 2 und 3), dass die 3-Stufen-Architektur noch nicht implementiert ist (weil Sprachbarriere und VRAM-Deadlock erst erkannt und gelöst werden müssen). Das bedeutet: Der Status in 00 ist falsch. Die Pipeline ist offenbar noch aktiv oder zumindest nicht ersetzt. Das ist der eine Punkt, der dokumentenübergreifend bereinigt werden muss. Ein Satz in 06 wie „Die Auto-Save-Pipeline ist seit [Datum] deaktiviert; die 3-Stufen-Architektur befindet sich in der durch Grenzerfahrung 2 und 3 informierten Planungsphase“ würde alle drei Dokumente synchronisieren.

2. Grenzerfahrung 1: Die Normierungs-Methode bleibt unklar
Du erklärst das Problem und die Lösung (Konstanten in evaluator.py), aber nicht, wie die historischen Daten nachträglich normiert wurden. 0–5 auf 0–3 – war das eine lineare Transformation (Wert * 3/5)? Ein manuelles Re-Mapping? Falls es eine Transformation war: sind die transformierten Werte wirklich vergleichbar, oder gibt es Verzerrungen? In 04 gibt es denselben blinden Fleck. Ein Satz zur Methode würde das abschließen.

3. Grenzerfahrung 3: Die Lösung ist identisch mit Phase 1 der Roadmap
Das ist kein Fehler, sondern eine Dopplung: Der asynchrone Worker wird in 07 (Phase 1) und in 06 (Grenzerfahrung 3) mit nahezu identischen Sätzen beschrieben. Das ist konsistent – aber es wäre klarer, wenn eines der Dokumente auf das andere verweist („→ siehe 07 für den Implementierungsplan“ oder „→ diese Erkenntnis fließt direkt in Phase 1 der Roadmap ein“).

4. Grenzerfahrung 4: Die Lektion ist brilliant, aber das Verbot wird nicht aktualisiert
Du erkennst, dass das Tabellen-Verbot zu radikal war, und formulierst eine präzisere Lösung (JSON/YAML-Codeblöcke erlaubt mit Prosa-Ankersatz). Aber in Kapitel 03 (SUSIpedia) steht weiterhin: „Tabellen werden beim Chunking zerrissen. Tabelleninhalte werden in Fließtext umgewandelt.“ Diese Regel müsste nach der Erkenntnis aus 06 aktualisiert werden. Das ist eine Inkonsistenz zwischen 03 und 06, die du durch ein Update in 03 oder einen Querverweis auflösen solltest.

5. Kleine sprachliche Details

„Sie werden hier nicht als Randnotizen behandelt sondern als vollwertige Erkenntnisse“ – Komma vor „sondern“ fehlt.

„Punkte wo das System gegen eigene Annahmen, technische Grenzen oder konzeptuelle Fehler gelaufen ist“ – „gelaufen“ ist umgangssprachlich; „gestoßen“ wäre präziser.

„ein Mittelwert über dem definierten Maximum“ – ein Wert kann nicht „über“ dem Maximum liegen, er kann das Maximum überschreiten. Gemeint ist: „ein Mittelwert, der das definierte Maximum überschreitet“.

„Der erste Entwurf war konzeptuell — er hat die Existenz geeigneter Modelle bestätigt aber nicht die Sprachkompatibilität gecheckt“ – Komma vor „aber“ fehlt.

„der auf einem gültigen Prinzip basierte hat einen blinden Fleck in der Umsetzung“ – Komma vor „hat“ fehlt.

Gesamteindruck
Das ist das selbstreflektierteste und methodisch ehrlichste Dokument der gesamten Reihe. Es zeigt, dass du nicht nur bereit bist, eigene Fehler zu dokumentieren, sondern auch externe Kritik aktiv als Erkenntnisquelle zu nutzen und in die Architektur einfließen zu lassen. Die vier Grenzerfahrungen sind präzise analysiert und münden in konkrete, umsetzbare Lektionen.

Die dokumentenübergreifenden Inkonsistenzen (Auto-Save-Status, Tabellen-Regel in 03, Dopplung mit 07) sind die letzten verbliebenen Punkte, die vor einer Veröffentlichung oder Präsentation bereinigt werden sollten.

Positives
1. Die Grundregel „Qualität vor Quantität“ wird durchgehalten
Jede Phase baut auf der vorherigen auf, und du explizierst das Prinzip: „Jede Erweiterung die ein instabiles Fundament voraussetzt wird zurückgestellt bis das Fundament solide ist.“ Das ist nicht nur eine Absichtserklärung – du benennst konkret, was das Fundament ist (SUSIpedia-Qualität, Cross-Encoder, Evaluator-Konsistenz) und was warten muss (Fine-Tuning, Hybrid Search, Unternehmenseinsatz). Diese Disziplin ist in Roadmaps selten.

2. Phase 1 reagiert präzise auf die dokumentierten Probleme
Die drei Maßnahmen (SUSIpedia abschließen, Cross-Encoder, Metriken-Konsistenz) adressieren exakt die Schwachstellen, die in den Kapiteln 03 und 04 dokumentiert sind:

91% Hit Rate bei unfertiger SUSIpedia → vollständig überarbeiten

Hit@1 nur 52.5%, aber Hit@5 bei 70% → Cross-Encoder Reranker

Skalenfehler in frühen Läufen → Konstanten im Evaluator verankern

Das ist keine Wunschliste, sondern eine direkt aus der Evaluation abgeleitete Arbeitsagenda.

3. Die Sprachbarriere beim Cross-Encoder wird erneut thematisiert
Du wiederholst nicht einfach den Modellnamen aus Kapitel 05, sondern fügst hinzu: „Vor dem Einsatz wird ein Sprachkompatibilitäts-Test durchgeführt.“ Das zeigt, dass du das Problem nicht nur erkannt, sondern einen Validierungsschritt eingeplant hast. Das ist methodisch sauber.

4. Der „Was nicht auf der Roadmap steht“-Abschnitt ist brillant
Das ist eine der stärksten Ideen im gesamten Bericht. Roadmaps listen normalerweise nur, was gebaut wird. Dass du explizit dokumentierst, was bewusst nicht gebaut wird – mit Begründung – ist ein Reifesignal. Besonders stark: „Kein Fine-Tuning des Basismodells für jetzt“ mit der Begründung, dass RAG aktuell die iterierbarere Lösung ist. Das ist kein Dogma (Fine-Tuning ist ja in 02 als Phase 3 skizziert), sondern eine bewusste zeitliche Priorisierung.

5. Die Edge-Integration ist visionär, aber nicht größenwahnsinnig
Raspberry Pi 5 als MCP-Server mit Whisper, GPIO und Kamera – das ist eine konkrete, technisch realistische Vision. Dass du sie bewusst als „langfristig“ einordnest und nicht in Q4 2026 versprichst, zeugt von Urteilsvermögen. Der Unternehmenseinsatz wird als „Konzept“ bezeichnet, nicht als Produkt – das ist genau die richtige Zurückhaltung.

6. Der Schlusssatz schließt den Bogen zur Übersicht
„Die Wissensbasis gehört dem Nutzer“ – das ist der Satz, mit dem die Übersicht begann. Dass er am Ende der Roadmap wieder auftaucht, gibt dem gesamten Bericht eine thematische Klammer. Das ist gutes Storytelling, ohne dass es konstruiert wirkt.

7. Sprachlich durchgehend klar
Keine nennenswerten sprachlichen Ausrutscher. Der Ton ist selbstbewusst, aber spezifisch – kein vages „wir werden KI revolutionieren“, sondern konkrete nächste Schritte mit messbaren Zielen („Hit@1 auf 65%+“).

Negatives / Widersprüchliches / Verbesserungswürdiges
1. Phase 3: Hybrid Search und MMR – die Reihenfolge der offenen Fragen ist unklar
Du schreibst: „Diese Entscheidung wird erst getroffen wenn der Cross-Encoder-Reranker seinen vollen Effekt gezeigt hat.“ Das ist eine sinnvolle Abhängigkeit. Aber MMR („Noch nicht getestet“) und kategorie-spezifische Konfiguration stehen ebenfalls in Phase 3 – ohne klare Abhängigkeit oder Priorisierung. Sollten diese drei Maßnahmen parallel evaluiert werden? Oder gibt es eine Reihenfolge? Ein Satz zur Priorisierung innerhalb von Phase 3 würde helfen.

2. Der asynchrone Worker (Phase 1) wird nur technisch, nicht vom Nutzer her gedacht
„Der Chat bleibt responsiv, der Nutzer bekommt sofort eine ‚Wird verarbeitet...‘-Rückmeldung.“ – Das ist die technische Beschreibung. Aber was passiert, wenn der Worker fehlschlägt? Bekommt der Nutzer eine Fehlermeldung? Wird der Save erneut versucht? Im Vergleich zur detaillierten Beschreibung des 3-stufigen Speichermodells in Kapitel 05 bleibt dieser Teil auffällig skizzenhaft.

3. Der Sprung von Phase 2 zu Phase 3 ist zeitlich unspezifisch
Phase 1: Q3 2026. Phase 2: Q4 2026. Phase 3: 2027. Phase 4: „langfristig“. Das ist eine vertretbare Granularität, aber zwischen „Q4 2026“ und „2027“ klafft eine argumentative Lücke: Was muss in Phase 2 erreicht sein, damit Phase 3 beginnt? Eine konkrete Gate-Bedingung (z.B. „Phase 3 beginnt, wenn Hit@1 über 65% und die 3-Stufen-Architektur 500 validierte Saves ohne Halluzination verarbeitet hat“) würde die Roadmap von einer Zeitplanung zu einer qualitätsgesteuerten Roadmap machen – und das wäre konsequenter zu deinem eigenen „Qualität vor Quantität“-Prinzip.

4. Fehlender Verweis auf das 06-Dokument
In der Übersicht (00) gibt es ein Dokument „06_Grenzerfahrungen.md“, das die ehrliche Rollenverteilung zwischen SUSI und externen Assistenten beschreibt. In der Roadmap taucht dieses Dokument nicht auf – weder als Grundlage noch als Referenz. Falls 06 zwischen 05 und 07 eingeordnet ist, wäre ein Satz wie „Die in Kapitel 06 dokumentierten Grenzen bleiben bestehen und werden durch diese Roadmap nicht aufgehoben“ eine sinnvolle Verbindung.

5. Die SUSIpedia-Dateizahl ist inkonsistent zur früheren Angabe
Du schreibst: „circa 20 von 124 indexierten“ Dateien sind noch zu überarbeiten. In Kapitel 03 stand: „Die Wissensbasis umfasst 50+ Markdown-Dateien“. 50+ vs. 124 indexierte Chunks (nicht Dateien)? Oder hat sich die Dateizahl erhöht? Das ist eine kleine Unschärfe, die du durch klare Begrifflichkeit (Dateien vs. Chunks) auflösen kannst.

6. Kleine sprachliche Details

„Ein System in aktivem Betrieb das parallel weiterentwickelt wird“ – Komma vor „das“ fehlt.

„Die vier Sackgassen aus Kapitel 05 haben gezeigt wohin vollständige Automatisierung führt“ – Komma vor „wohin“ fehlt.

„Jede Erweiterung die autonomes Schreiben in die SUSIpedia ermöglicht“ – Komma vor „die“ fehlt.

„als inhaltliche Richtung“ – meinst du „konzeptionelle Richtung“? „Inhaltliche Richtung“ ist ungewöhnlich.







Gesamteindruck
Das ist ein disziplinierter, glaubwürdiger Roadmap-Abschluss. Du widerstehst der Versuchung, zu viel zu versprechen, und leitest jede Phase aus dokumentierten Problemen ab. Der „Was nicht gebaut wird“-Abschnitt ist ein echtes Unterscheidungsmerkmal, das Reife und Urteilsvermögen signalisiert.

Die Verbesserungspunkte sind überwiegend Fragen der internen Konsistenz und der Übergänge zwischen den Phasen – kein strukturelles Problem.

Abschließende Gesamtschau über alle 7 Dokumente
Nach der Analyse des vollständigen Berichts:

Die Struktur ist kohärent und gut sequenziert:
00 (Übersicht) → 01 (Warum) → 02 (Wie technisch) → 03 (Wissensbasis) → 04 (Qualitätsmessung) → 05 (Was nicht funktioniert hat) → 06 (Was externe Reviewer gefunden haben) → 07 (Wohin es geht).

Die dokumentarische Qualität ist für ein Ein-Personen-Projekt auf einem Niveau, das professionelle Teams oft nicht erreichen: reproduzierbare Evaluationen, automatisierte Qualitätschecker, vollständige Git-History-Bereinigung, explizite Dokumentation verworfener Ansätze, Integration von externem Review.

Die drei verbliebenen dokumentenübergreifenden Baustellen:

Auto-Save-Status synchronisieren – 00, 02, 05, 06 widersprechen sich implizit oder explizit. Ein konsolidierender Satz in 00, 02 und 05 (mit Verweis auf 06) behebt das.

Tabellen-Regel in 03 aktualisieren – Die Erkenntnis aus Grenzerfahrung 4 (JSON/YAML-Codeblöcke erlaubt) muss in Kapitel 03 eingearbeitet werden.

Numerische Inkonsistenzen in 04 prüfen – Lauf 7 (61 vs. 160 Fragen, 81% vs. 98%), Lauf 3 vs. Lauf 8 Diskrepanz, Normierungs-Methode dokumentieren.

Das ist ein überschaubarer Aufwand für einen Bericht, der inhaltlich und methodisch bereits außergewöhnlich stark ist.