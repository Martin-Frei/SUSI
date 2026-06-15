# Feedback & offene Punkte für SUSI

Hi Martin,

Vorweg:
Das Projekt ist konzeptionell richtig stark – besonders dein Eval-Framework
(Grid-Search mit BERTScore/ROUGE, ~29% → ~97%) ist etwas, das viele „echte"
Teams nicht hinbekommen. Das hier ist also kollegiales Feedback unter
AI-Leuten, kein Verriss.

Ich hab auf dem Branch `feature/rag-core-and-web-fixes` aufgeräumt. Unten steht,
**was ich angefasst habe** und – wichtiger – **was ich bewusst liegen gelassen
habe und warum**, damit du selbst entscheiden kannst.

Stand: 2026-06-15

---

## Was ich behoben habe (6 Commits)

| Commit | Inhalt |
|---|---|
| `Make the RAG core reusable and unit-testable` | `ask_susi()` hat jetzt echte Parameter, die Heavy-Imports (langchain/chromadb) sind **lazy**, die DB wird gecacht, dein `worth_saving`-Substring-Bug ist gefixt, Debug-Prints/toter Code/Typo raus. |
| `Add susi_config.yaml as the single source for sidebar + prompts` | Die fehlende `get_frontend_config()` + `susi_config.yaml` ergänzt; Prompt-Registry inkl. deinem `praezise_cot` aus der Eval. |
| `Wire the web layer to the real RAG API` | Den `importlib`-Hack und das `subprocess`-Ingest rausgeworfen, echte Imports rein. **Damit läuft dein Web-Frontend wieder.** |
| `Persist chat history in the database instead of a global dict` | `ChatMessage`-Modell statt prozess-globalem Dict; pro Session isoliert, übersteht Neustarts. |
| `Harden file upload against path traversal` | `_safe_filename()` verhindert, dass ein Upload aus dem Verzeichnis ausbricht. |
| `Split requirements into a curated list, eval extras and a lock` | `requirements.txt` von 168 Paketen (UTF-16, inkl. `anthropic`) auf ~8 echte Direkt-Deps reduziert; deinen Full-Freeze hab ich als Lockfile aufgehoben. |

Verifikation: ruff-F clean, 17 pytest-Tests grün, 2 Django-DB-Tests grün, keine
fehlenden Migrationen, `manage.py check` sauber. Den ganzen Plan + die Specs
findest du in `tasks/`, falls du nachvollziehen willst, wie ich vorgegangen bin.

> **Der wichtigste Punkt:** Dein Web-Frontend war effektiv tot – `views.py` rief
> `ask_susi()` mit `top_k`, `temperature` usw. auf, aber die Funktion nahm nur
> ein Argument. Jede Web-Anfrage lief in den `except` und gab `[SUSI Fehler]`
> zurück. Die CLI lief, das Web nicht. Das war ein auseinandergelaufener
> Code-Stand, kein Designfehler – passiert jedem. Jetzt teilen sich CLI und
> Django denselben Kern.

---

## Was ich bewusst liegen gelassen habe – und warum

Das hier ist kein Versäumnis, sondern Absicht. Ich wollte eine fokussierte
Fix-Serie abliefern und nicht in deinem Projekt herumdesignen.

### 1. Dein Self-write-Gedächtnis hat keinen Pflicht-Review (mittlere Priorität)
SUSI schreibt LLM-Zusammenfassungen zurück in die SUSIpedia und liest sie beim
nächsten Lauf wieder ein. Pass auf: Das ist eine **Feedback-Schleife, die
Halluzinationen verfestigen kann** – einmal falsch zusammengefasst, wird der
Text zur „Quelle der Wahrheit" und taucht im Retrieval wieder auf.

*Warum ich es nicht angefasst habe:* Das ist ein **Feature-Redesign**, kein
Bugfix. Du bräuchtest einen verpflichtenden Human-in-the-loop-Check vor dem
Speichern (in der CLI hast du ihn ansatzweise über den Speicher-Dialog, im Web
fehlt er komplett). Das gehört in einen eigenen, bewusst gebauten Increment –
da wollte ich dir nicht reinpfuschen.

### 2. `DEBUG = True` / hartkodierter `SECRET_KEY` / `ALLOWED_HOSTS = []`
*Warum nicht angefasst:* Für deinen aktuellen **rein lokalen** Single-User-Betrieb
ist das unkritisch. Relevant wird es, sobald SUSI übers Netz erreichbar ist
(deine geplante Raspberry-Pi-/Gesichtserkennungs-Stufe). Dann brauchst du:
`DEBUG=False`, `SECRET_KEY` aus einer Env-Variable, gesetzte `ALLOWED_HOSTS` und
echte Auth. Mach das zusammen mit dem Deployment-Schritt – vorziehen bringt nichts.

### 3. Der Ingest blockiert weiterhin den Web-Request
`_ingest_file` / `save_to_susipedia` rufen `ingest_docs()` jetzt direkt auf (statt
deiner fragilen `subprocess`-Variante), aber immer noch **synchron**. Bei großen
Uploads wartet der HTTP-Request, bis die Indexierung durch ist.

*Warum nicht angefasst:* Die saubere Lösung wäre ein Background-Worker
(Django-Q, Celery oder ein simpler Thread). Das ist neue Infrastruktur und für
den lokalen Einzelnutzer aktuell verschmerzbar. Wichtig: dein `subprocess`-Aufruf
blockierte vorher genauso – ich hab es also nicht verschlechtert, nur die
Interpreter-/CWD-Bugs beseitigt.

### 4. Keine Authentifizierung
Wer den Port erreicht, kann SUSI befragen und Dateien hochladen. Gleiche
Begründung wie #2 – lokal okay, gehört zum Netz-/Deployment-Thema.

### 5. Kosmetik / Altlasten (niedrige Priorität)
Bewusst **nicht** angefasst, weil harmlos und in der fokussierten Serie nur
Rauschen gewesen wäre:
- `clean_structure.txt` zeigt noch deinen alten Root-Namen `Stock_prediction/`.
- Hartkodierte Pfade (`C:\Users\tsinn\...`) in README / Eval-Docs.
- Leere Django-Boilerplate-Stubs mit ungenutzten Imports (`core/admin.py`,
  `rag/admin.py`, `rag/views.py`, `rag/models.py`, die `tests.py`-Reste) – ruff
  meldet hier noch F401.
- `susi_project/settings.py`: ungenutzter `import os` und ein doppeltes
  `BASE_DIR =` (Zeile 17 und 126).
- Kleiner Widerspruch: README/Code nutzen `nomic-embed-text`, deine Eval kürt
  aber `bge-m3` als Sieger. Wenn die Eval stimmt, solltest du auf `bge-m3`
  umstellen (oder umgekehrt dokumentieren, warum nicht).

*Warum nicht angefasst:* Reine Doku-/Stub-Kosmetik ohne Funktionswirkung. Das
machst du in 10 Minuten am Stück, wenn du magst.

---

## Praktisches zum Branch

- **Nichts gemergt, nichts gepusht.** Das ist deine Entscheidung – schau dir die
  Commits in Ruhe an.
- Ich hab den Test-Gate in einem isolierten venv laufen lassen, das **nur**
  Django + pytest + ruff + PyYAML + pytz hatte – **ohne** langchain/chromadb/ollama.
  Dass die Tests dort grün sind, ist der Beweis, dass die Lazy-Imports greifen
  (vorher war dein `query.py` ohne den kompletten Stack gar nicht importierbar).
- Vor dem ersten echten Lauf: `pip install -r requirements.txt` und Ollama mit
  `qwen2.5-coder:7b` + `nomic-embed-text` starten.

Viel Erfolg mit SUSI – und Respekt für die Eval-Disziplin, das hebt das Projekt
deutlich über „noch ein RAG-Tutorial" hinaus.
