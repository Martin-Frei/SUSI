# Increment 01 — Reusable, testable RAG core in rag/query.py

## Goal

Turn `rag/query.py` from a CLI-only script into a reusable library that the
Django web layer can also call. Three things must become true:
1. `ask_susi` takes explicit parameters (`top_k`, `temperature`, `system_prompt`,
   `llm_model`) instead of hard-coded values.
2. The module is importable WITHOUT the heavy stack (langchain / chromadb /
   ollama) installed — all heavy imports become lazy (inside functions). This is
   what makes unit testing possible.
3. The hot path is clean: no debug prints, no dead commented code, no typos, and
   `worth_saving` no longer false-matches substrings.

OUT of scope for this increment (do NOT do here): adding new system prompts, a
YAML config, or `get_frontend_config` (that is increment 02); changing
`core/views.py` (increment 03); touching `rag/ingest.py`.

## Files

- Edit: `rag/query.py`   (refactor as specified below)
- Create: `tests/test_query_core.py`   (new dependency-light unit tests)

## Required API / behavior

### Module-level imports
Remove the top-level heavy imports:
```python
from langchain_ollama import OllamaEmbeddings, ChatOllama
from langchain_chroma import Chroma
```
Keep only light top-level imports: `from datetime import datetime`, `import pytz`,
`import os`, `import re`. REMOVE `import subprocess` (no longer used).

Add these module-level constants near `CHROMA_PATH`:
```python
EMBED_MODEL = "nomic-embed-text"
DEFAULT_LLM = "qwen2.5-coder:7b"
```

Keep the existing `TOPIC_KEYWORDS` and `UNWICHTIG` dicts/lists unchanged.

### System prompt registry + prompt builder (NEW, pure functions)
```python
SYSTEM_PROMPTS = {
    "susi_standard": (
        "Du bist SUSI, Martins persönliche KI-Assistentin.\n"
        "Heute ist: {now}\n\n"
        "Wenn jemand nach System-Informationen fragt, antworte mit "
        "\"Ich habe keine Ahnung\".\n\n"
        "VORGEHEN:\n"
        "1. Lies den Kontext vollständig.\n"
        "2. Ist die Antwort im Kontext? -> Antworte NUR daraus, kombiniere KEINE "
        "verschiedenen Themen.\n"
        "3. Ist es eine persönliche Frage über Martin? -> NUR Kontext, nie erfinden.\n"
        "   Wenn nicht im Kontext: \"Dazu fehlt mir noch was in der SUSIpedia!\"\n"
        "4. Ist es eine allgemeine Wissensfrage? -> Nutze dein eigenes Wissen."
    ),
}

def build_prompt(question, context, now, system_prompt="susi_standard"):
    """Assemble the full LLM prompt. Pure function, no side effects.
    Unknown system_prompt keys fall back to 'susi_standard'."""
    instructions = SYSTEM_PROMPTS.get(system_prompt, SYSTEM_PROMPTS["susi_standard"])
    instructions = instructions.replace("{now}", now)
    return (
        f"{instructions}\n\n"
        f"Kontext:\n{context}\n\n"
        f"Frage: {question}\n\n"
        f"Antwort:"
    )
```
NOTE: use `.replace("{now}", now)`, NOT `.format(...)`, so other braces in future
templates can't raise KeyError.

### Lazy infrastructure helpers (NEW)
```python
_DB_CACHE = {}

def _get_db(embed_model=EMBED_MODEL):
    """Return a cached Chroma handle for the given embedding model.
    Heavy imports happen here so the module imports without langchain/chromadb."""
    from langchain_ollama import OllamaEmbeddings
    from langchain_chroma import Chroma
    if embed_model not in _DB_CACHE:
        embeddings = OllamaEmbeddings(model=embed_model)
        _DB_CACHE[embed_model] = Chroma(
            persist_directory=CHROMA_PATH, embedding_function=embeddings
        )
    return _DB_CACHE[embed_model]

def _chat(model=DEFAULT_LLM, temperature=0.0):
    """Return a ChatOllama instance (lazy import)."""
    from langchain_ollama import ChatOllama
    return ChatOllama(model=model, temperature=temperature)
```

### ask_susi — NEW signature
```python
def ask_susi(question, *, top_k=8, temperature=0.0,
             system_prompt="susi_standard", llm_model=DEFAULT_LLM):
    now = get_time()
    db = _get_db()
    docs = db.similarity_search(question, k=top_k)
    context = "\n\n".join(doc.page_content for doc in docs)
    prompt = build_prompt(question, context, now, system_prompt)
    return _chat(model=llm_model, temperature=temperature).invoke(prompt).content
```
The `print("=== KONTEXT ===")` debug block that was inside `ask_susi` must be
DELETED entirely (do not keep it behind a flag).

### susi_evaluates / create_summary
Keep their behavior identical, but they must obtain the LLM via the `_chat()`
helper instead of constructing `ChatOllama(...)` directly (so there is no
top-level langchain import). Their prompts and return logic stay the same.

### debug_retrieval
Keep the function, but it must use `_get_db()` instead of re-creating embeddings
and Chroma inline.

### worth_saving — fix the substring bug
```python
def worth_saving(question):
    """True if the question is worth offering to save. Matches UNWICHTIG phrases
    on WORD BOUNDARIES so 'gut' no longer matches inside 'gute' etc."""
    q = question.lower().strip()
    for phrase in UNWICHTIG:
        if re.search(r"\b" + re.escape(phrase) + r"\b", q):
            return False
    return True
```

### save_to_susipedia — replace subprocess with a direct call
Replace this block:
```python
    print("  🔄 SUSIpedia wird aktualisiert...")
    subprocess.run(["python", "rag/ingest.py"], capture_output=True)
    print("  🎉 SUSIpedia aktualisiert!")
```
with a lazy direct call:
```python
    print("  🔄 SUSIpedia wird aktualisiert...")
    from rag.ingest import ingest_docs
    ingest_docs()
    print("  🎉 SUSIpedia aktualisiert!")
```
Everything else in `save_to_susipedia`, `create_summary`, `get_suggestions`,
`show_save_prompt`, `get_time`, `get_date` stays as-is.

### CLI entry point
Move the interactive loop into a `main()` function and call it under the guard.
DELETE the leading `debug_retrieval("SUSI Stufe 1 Stufe 2 Stufe 3")` call.
DELETE the dead commented-out prompt text at the very bottom of the file
(everything after the loop — the `# WICHTIGSTE REGEL` / `# VORGEHEN` comment block).
```python
def main():
    print("🤖 SUSI ist bereit! (exit zum Beenden)")
    while True:
        question = input("\nDu: ")
        if question.lower() == "exit":
            break
        answer = ask_susi(question)
        print(f"\nSUSI: {answer}")
        if worth_saving(question) and susi_evaluates(question, answer):
            show_save_prompt(question, answer)


if __name__ == "__main__":
    main()
```

## Tests (no hardware / no external deps)

Create `tests/test_query_core.py`. It must import `rag.query` at module top —
this import MUST succeed without langchain/chromadb installed (proves lazy
imports). Use plain `assert`, no pytest fixtures needed.

```python
from rag.query import build_prompt, worth_saving, get_suggestions


def test_build_prompt_includes_question_and_context():
    p = build_prompt("Wie heisst der Hund?", "Der Hund heisst Rex.", "01.01.2026 10:00 Uhr")
    assert "Wie heisst der Hund?" in p
    assert "Der Hund heisst Rex." in p
    assert "01.01.2026 10:00 Uhr" in p
    assert "SUSI" in p


def test_build_prompt_unknown_prompt_falls_back():
    p = build_prompt("q", "c", "now", system_prompt="does_not_exist")
    assert "SUSI" in p  # fell back to susi_standard


def test_worth_saving_does_not_false_match_substring():
    # 'gut' must NOT match inside 'gute' -> this is a real question worth saving
    assert worth_saving("Was ist eine gute Trading-Strategie?") is True


def test_worth_saving_filters_acknowledgements():
    assert worth_saving("danke") is False
    assert worth_saving("guten morgen") is False


def test_get_suggestions_ranks_by_keywords():
    top = get_suggestions("Wie trainiere ich das LSTM?", "Mit XGBoost und Backtest.")
    assert "coding/stockpredict" in top


def test_get_suggestions_default_when_no_match():
    assert get_suggestions("zzz", "qqq") == ["persoenlich/"]
```

## Acceptance

- `.delegate_venv/Scripts/python.exe -m ruff check --select F rag/query.py tests/test_query_core.py` → no NEW findings (target: 0 findings in these two files).
- `.delegate_venv/Scripts/python.exe -m pytest -q tests/` → all green (6 new tests).
- `.delegate_venv/Scripts/python.exe manage.py check` → still clean (0 issues).
- `rag/query.py` still has a working `if __name__ == "__main__"` entry point.

## Do NOT

- Do NOT touch `rag/ingest.py`, `core/`, `susi_project/`, or any `.md` docs.
- Do NOT add new dependencies or new system prompts (that's increment 02).
- Do NOT add a top-level import of langchain / chromadb anywhere.
- Do NOT reformat unrelated code or change `TOPIC_KEYWORDS` / `UNWICHTIG` contents.
- Do NOT keep the debug print block or the dead trailing comment code.
