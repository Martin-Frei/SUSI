# Increment 03 — Wire core/views.py to the real RAG API

## Goal

Make the web layer actually call the RAG core. Today core/views.py loads
rag/query.py through `importlib.util.spec_from_file_location` and calls a
signature that did not exist, so every request fell into the except branch;
and it shells out to `python rag/ingest.py` via subprocess (wrong interpreter,
cwd-dependent). After increments 01-02 the real functions exist with the right
signatures, so this replaces the hacks with normal imports.

OUT of scope: the upload path-traversal fix and requirements cleanup
(increment 05); persisting history/settings in the DB (increment 04). Do not
change those areas here.

## Files

- Edit:   `core/views.py`
- Create: `tests/conftest.py`            (configure Django for view tests)
- Create: `tests/test_views_wiring.py`   (new tests)

## Required API / behavior

### Import block — replace the top of core/views.py
Replace everything from the first line through the `csrf_exempt` import
(the block that currently contains a duplicate `render` import, `import os`,
`import subprocess`, and `from django.views.decorators.csrf import csrf_exempt`)
with EXACTLY:
```python
import shutil
from pathlib import Path

from django.conf import settings
from django.http import HttpResponse
from django.shortcuts import render
from django.views.decorators.http import require_http_methods
```
Removed because unused/duplicated: `os`, `subprocess`, `csrf_exempt`, the second
`render` import, and the stray `# Create your views here.` comment.

### _ask_susi — use a normal import (keep it lazy, inside the function)
Replace the whole `_ask_susi` body with:
```python
def _ask_susi(question: str, top_k=8, temperature=0.0,
              system_prompt="susi_standard", llm_model="qwen2.5-coder:7b") -> str:
    """Call ask_susi() from rag.query. Import is lazy so a missing heavy stack
    fails gracefully instead of breaking Django startup."""
    try:
        from rag.query import ask_susi
        return ask_susi(
            question,
            top_k=top_k,
            temperature=temperature,
            system_prompt=system_prompt,
            llm_model=llm_model,
        )
    except Exception as e:
        return f"[SUSI Fehler]: {e}"
```

### _get_frontend_config — use a normal import; keep the fallback dict
Replace its body so it imports `get_frontend_config` directly:
```python
def _get_frontend_config() -> dict:
    """Load parameter config from susi_config.yaml via rag.query."""
    try:
        from rag.query import get_frontend_config
        return get_frontend_config()
    except Exception:
        # Fallback if the YAML cannot be loaded
        return {
            "llm_options":         [{"name": "Qwen 2.5 Coder 7B", "model": "qwen2.5-coder:7b"}],
            "prompt_options":      [{"name": "susi_standard", "label": "SUSI Standard"}],
            "top_k_min":           3,
            "top_k_max":           15,
            "top_k_default":       8,
            "temperature_min":     0.0,
            "temperature_max":     1.0,
            "temperature_step":    0.1,
            "temperature_default": 0.0,
            "prompt_default":      "susi_standard",
            "llm_default":         "qwen2.5-coder:7b",
        }
```

### _ingest_file — replace subprocess with a direct call
Replace the whole `_ingest_file` body with:
```python
def _ingest_file(filepath: str) -> tuple[bool, str]:
    try:
        dest_dir = Path(settings.DOCS_PATH) / "uploads"
        dest_dir.mkdir(parents=True, exist_ok=True)

        filename = Path(filepath).name
        dest_path = dest_dir / filename
        shutil.copy2(filepath, dest_path)

        # Direct call instead of `subprocess.run(["python", "rag/ingest.py"])`:
        # the subprocess used the wrong interpreter and depended on the cwd.
        from rag.ingest import ingest_docs
        ingest_docs()

        return True, f"✅ '{filename}' erfolgreich indexiert und ab sofort befragbar."
    except Exception as e:
        return False, f"⚠️ Fehler beim Indexieren: {e}"
```
The previous `subprocess.TimeoutExpired` except branch is removed along with it.

Everything else in core/views.py (the view functions, history helpers) stays
unchanged.

## Tests (no hardware / no external deps)

### tests/conftest.py — create EXACTLY
```python
import os

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "susi_project.settings")
django.setup()
```

### tests/test_views_wiring.py — create EXACTLY
```python
def test_get_frontend_config_uses_real_yaml_not_fallback():
    from core.views import _get_frontend_config
    cfg = _get_frontend_config()
    names = [o["name"] for o in cfg["prompt_options"]]
    # The real YAML has praezise_cot; the hard-coded fallback stub does not.
    # So seeing it proves the importlib hack is gone and the real fn is used.
    assert "praezise_cot" in names


def test_ask_susi_helper_fails_gracefully():
    from core.views import _ask_susi
    # No Ollama/langchain in the gate env -> must return an error STRING, not raise.
    result = _ask_susi("ping")
    assert isinstance(result, str)
    assert result.startswith("[SUSI Fehler]")
```

## Acceptance

- `.delegate_venv/Scripts/python.exe -m ruff check --select F core/views.py tests/conftest.py tests/test_views_wiring.py` → 0 findings.
- `.delegate_venv/Scripts/python.exe -m pytest -q tests/` → all green (11 prior + 2 new = 13).
- `.delegate_venv/Scripts/python.exe manage.py check` → clean.

## Do NOT

- Do NOT touch `rag/`, `susi_project/`, templates, or `.md` docs.
- Do NOT change the upload validation / path handling in `upload_view`
  (that is increment 05).
- Do NOT add a top-level (module-level) import of `rag.query` or `rag.ingest`
  — keep them inside the functions so Django startup never needs the heavy stack.
- Do NOT add dependencies or touch `core/models.py` (increment 04).
