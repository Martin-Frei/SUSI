# Feedback & offene Punkte

Stand: 2026-06-15 · Branch `feature/rag-core-and-web-fixes`

Dieses Dokument fasst zusammen, was auf diesem Branch behoben wurde und – vor
allem – was **bewusst offen gelassen** wurde und warum. Es ist als Übergabe an
den Maintainer gedacht.

---

## Was behoben wurde (6 Commits)

| Commit | Inhalt |
|---|---|
| `Make the RAG core reusable and unit-testable` | `ask_susi()` bekam echte Parameter, Heavy-Imports (langchain/chromadb) sind jetzt **lazy**, DB wird gecacht, `worth_saving`-Substring-Bug gefixt, Debug-Prints/toter Code/Typo entfernt. |
| `Add susi_config.yaml as the single source for sidebar + prompts` | Fehlende `get_frontend_config()` + `susi_config.yaml` ergänzt; Prompt-Registry inkl. `praezise_cot`. |
| `Wire the web layer to the real RAG API` | `importlib`-Hack und `subprocess`-Ingest raus, echte Imports rein. **Das Web-Frontend funktioniert wieder.** |
| `Persist chat history in the database instead of a global dict` | `ChatMessage`-Modell statt prozess-globalem Dict; pro Session isoliert, übersteht Neustarts. |
| `Harden file upload against path traversal` | `_safe_filename()` verhindert Ausbruch aus dem Upload-Verzeichnis. |
| `Split requirements into a curated list, eval extras and a lock` | `requirements.txt` von 168 Paketen (UTF-16, inkl. `anthropic`) auf ~8 echte Direkt-Deps reduziert; Full-Freeze als Lockfile erhalten. |

Verifikation: ruff-F clean, 17 pytest-Tests grün, 2 Django-DB-Tests grün, keine
fehlenden Migrationen, `manage.py check` sauber. Plan + Specs liegen in `tasks/`.

---

## Offen gelassen – und warum

### 1. Self-write-Gedächtnis ohne Pflicht-Review (mittlere Priorität)
SUSI schreibt LLM-Zusammenfassungen zurück in die SUSIpedia und liest sie beim
nächsten Lauf wieder ein. Das ist eine **Feedback-Schleife, die Halluzinationen
verfestigen kann** – modellgenerierter Text wird zur „Quelle der Wahrheit".

*Warum nicht angefasst:* Das ist ein **Feature-Redesign**, kein Bugfix. Es
bräuchte einen verpflichtenden Human-in-the-loop-Review vor dem Persistieren
(in der CLI gibt es ihn ansatzweise über den Speicher-Dialog, im Web fehlt er
ganz). Gehört in einen eigenen, bewusst designten Increment statt in eine
Aufräum-Runde.

### 2. `DEBUG = True` / hartkodierter `SECRET_KEY` / `ALLOWED_HOSTS = []`
*Warum nicht angefasst:* Für den aktuellen **rein lokalen** Single-User-Betrieb
unkritisch. Das wird erst relevant, sobald SUSI über das Netz erreichbar ist
(geplante Raspberry-Pi-/Gesichtserkennungs-Stufe). Dann braucht es:
`DEBUG=False`, `SECRET_KEY` aus einer Env-Variable, gesetzte `ALLOWED_HOSTS` und
eine echte Authentifizierung. Sollte zusammen mit dem Deployment-Schritt
gemacht werden, nicht vorgezogen werden.

### 3. Synchroner Ingest blockiert den Web-Request
`_ingest_file` / `save_to_susipedia` rufen `ingest_docs()` jetzt direkt auf (statt
fragiler `subprocess`-Variante) – aber weiterhin **synchron**. Bei großen Uploads
wartet der HTTP-Request, bis die Indexierung fertig ist.

*Warum nicht angefasst:* Echte Lösung wäre ein Task-Queue/Background-Worker
(z.B. Django-Q, Celery oder ein Thread). Das ist neue Infrastruktur und für den
lokalen Einzelnutzer aktuell verschmerzbar. Der vorherige `subprocess`-Aufruf
blockierte übrigens genauso – wir haben es also nicht verschlechtert, nur die
Interpreter-/CWD-Bugs beseitigt.

### 4. Keine Authentifizierung
Jeder mit Zugriff auf den Port kann SUSI befragen und Dateien hochladen.
*Warum nicht angefasst:* Gleiche Begründung wie #2 – lokal okay, gehört zum
Netz-/Deployment-Thema.

### 5. Kosmetik / Altlasten (niedrige Priorität)
Bewusst **nicht** angefasst, weil harmlos und nicht den Aufwand wert:
- `clean_structure.txt` zeigt noch den alten Root-Namen `Stock_prediction/`.
- Hartkodierte Pfade (`C:\Users\tsinn\...`) in README / Eval-Docs.
- Leere Django-Boilerplate-Stubs mit ungenutzten Imports (`core/admin.py`,
  `rag/admin.py`, `rag/views.py`, `rag/models.py`, die `tests.py`-Reste) – ruff
  meldet hier noch F401-Findings.
- `susi_project/settings.py`: ungenutzter `import os` und ein doppeltes
  `BASE_DIR =` (Zeile 17 und 126).
- README-Embedding-Widerspruch: Text nennt `nomic-embed-text`, die Eval kürt
  `bge-m3` als Sieger. Code nutzt weiterhin `nomic-embed-text`.

*Warum nicht angefasst:* Reine Doku-/Stub-Kosmetik ohne Funktionswirkung. Lässt
sich in 10 Minuten am Stück machen, wenn gewünscht – wäre aber Rauschen in
dieser fokussierten Fix-Serie gewesen.

---

## Hinweise zum Branch

- **Nicht gemergt, nicht gepusht.** Merge nach `main` ist eine bewusste
  Maintainer-Entscheidung.
- Der Gate lief in einem isolierten venv (`.delegate_venv`, git-ignoriert) mit
  nur Django + pytest + ruff + PyYAML + pytz – **ohne** langchain/chromadb/ollama.
  Dass die Tests dort laufen, ist der Beweis, dass die Lazy-Imports greifen.
- Vor dem ersten echten Lauf: `pip install -r requirements.txt` und sicherstellen,
  dass Ollama mit `qwen2.5-coder:7b` + `nomic-embed-text` läuft.
