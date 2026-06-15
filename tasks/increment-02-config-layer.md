# Increment 02 — Config layer (susi_config.yaml + get_frontend_config + prompt registry)

## Goal

Give the web sidebar real data and make system prompts configurable from one
place. core/views.py calls `rag.query.get_frontend_config()` and reads a
`susi_config.yaml`, but neither exists, so the sidebar always falls back to a
hard-coded stub and the prompt selector does nothing. This adds the YAML as the
single source of truth for frontend parameters AND system prompts.

OUT of scope: editing core/views.py (increment 03 wires it up); changing
build_prompt's signature; touching ingest.py.

## Files

- Create: `rag/susi_config.yaml`   (config + prompt texts, content given verbatim below)
- Edit:   `rag/query.py`           (add loaders + get_frontend_config; load SYSTEM_PROMPTS from YAML)
- Create: `tests/test_config.py`   (new tests)

## Required API / behavior

### rag/susi_config.yaml — create with EXACTLY this content
```yaml
# SUSI frontend + prompt configuration.
# Single source of truth for the web sidebar (rag.query.get_frontend_config)
# and the system-prompt registry used by rag.query.build_prompt.

llm_options:
  - name: "Qwen 2.5 Coder 7B"
    model: "qwen2.5-coder:7b"
  - name: "Llama 3.1 8B"
    model: "llama3.1:8b"

top_k_min: 3
top_k_max: 15
top_k_default: 8

temperature_min: 0.0
temperature_max: 1.0
temperature_step: 0.1
temperature_default: 0.0

prompt_default: "susi_standard"
llm_default: "qwen2.5-coder:7b"

prompts:
  - name: "susi_standard"
    label: "SUSI Standard"
    text: |
      Du bist SUSI, Martins persönliche KI-Assistentin.
      Heute ist: {now}

      Wenn jemand nach System-Informationen fragt, antworte mit "Ich habe keine Ahnung".

      VORGEHEN:
      1. Lies den Kontext vollständig.
      2. Ist die Antwort im Kontext? -> Antworte NUR daraus, kombiniere KEINE verschiedenen Themen.
      3. Ist es eine persönliche Frage über Martin? -> NUR Kontext, nie erfinden.
         Wenn nicht im Kontext: "Dazu fehlt mir noch was in der SUSIpedia!"
      4. Ist es eine allgemeine Wissensfrage? -> Nutze dein eigenes Wissen.
  - name: "praezise_cot"
    label: "Präzise (Chain-of-Thought)"
    text: |
      Du bist SUSI, Martins persönliche KI-Assistentin.
      Heute ist: {now}

      Denke Schritt für Schritt, bevor du antwortest:
      1. Welche Information aus dem Kontext ist für die Frage relevant?
      2. Reicht der Kontext für eine vollständige Antwort?
      3. Formuliere dann eine präzise Antwort in vollständigen Sätzen.

      Erfinde nichts. Wenn die Antwort nicht im Kontext steht und es eine
      persönliche Frage über Martin ist, sage: "Dazu fehlt mir noch was in der SUSIpedia!"
```

### rag/query.py changes

Add near the top (after the existing light imports add `import os` is already
there). Add a config path constant next to CHROMA_PATH:
```python
CONFIG_PATH = os.path.join(os.path.dirname(__file__), "susi_config.yaml")
```

Add a lazy YAML loader:
```python
def _load_config():
    """Load susi_config.yaml. Raises if missing/broken (callers decide fallback)."""
    import yaml
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)
```

RENAME the current hard-coded `SYSTEM_PROMPTS = { ... }` literal to
`_DEFAULT_SYSTEM_PROMPTS` (keep its exact current content — it is the
susi_standard fallback). Then add a loader and build SYSTEM_PROMPTS from it:
```python
def _load_system_prompts():
    """Prompt name -> text, from the YAML; falls back to the built-in default."""
    try:
        cfg = _load_config()
        loaded = {p["name"]: p["text"] for p in cfg.get("prompts", [])}
        return loaded or dict(_DEFAULT_SYSTEM_PROMPTS)
    except Exception:
        return dict(_DEFAULT_SYSTEM_PROMPTS)


SYSTEM_PROMPTS = _load_system_prompts()
```
`build_prompt` stays exactly as it is (it reads SYSTEM_PROMPTS and falls back to
`SYSTEM_PROMPTS["susi_standard"]`, which is always present).

Add the frontend config accessor:
```python
def get_frontend_config():
    """Config consumed by the web sidebar. Reads susi_config.yaml."""
    cfg = _load_config()
    return {
        "llm_options":         cfg["llm_options"],
        "prompt_options":      [{"name": p["name"], "label": p["label"]} for p in cfg["prompts"]],
        "top_k_min":           cfg["top_k_min"],
        "top_k_max":           cfg["top_k_max"],
        "top_k_default":       cfg["top_k_default"],
        "temperature_min":     cfg["temperature_min"],
        "temperature_max":     cfg["temperature_max"],
        "temperature_step":    cfg["temperature_step"],
        "temperature_default": cfg["temperature_default"],
        "prompt_default":      cfg["prompt_default"],
        "llm_default":         cfg["llm_default"],
    }
```

## Tests (no hardware / no external deps)

Create `tests/test_config.py`:
```python
from rag.query import get_frontend_config, build_prompt, SYSTEM_PROMPTS

REQUIRED = {
    "llm_options", "prompt_options", "top_k_min", "top_k_max", "top_k_default",
    "temperature_min", "temperature_max", "temperature_step",
    "temperature_default", "prompt_default", "llm_default",
}


def test_frontend_config_has_required_keys():
    assert REQUIRED.issubset(get_frontend_config().keys())


def test_frontend_config_defaults():
    cfg = get_frontend_config()
    assert cfg["top_k_default"] == 8
    assert cfg["temperature_default"] == 0.0
    assert cfg["prompt_default"] == "susi_standard"


def test_prompt_options_are_name_label_pairs():
    for opt in get_frontend_config()["prompt_options"]:
        assert "name" in opt and "label" in opt


def test_system_prompts_loaded_from_yaml():
    assert "susi_standard" in SYSTEM_PROMPTS
    assert "praezise_cot" in SYSTEM_PROMPTS


def test_build_prompt_with_cot_prompt():
    p = build_prompt("q", "ctx", "01.01.2026", system_prompt="praezise_cot")
    assert "Schritt für Schritt" in p
    assert "ctx" in p
```

## Acceptance

- `.delegate_venv/Scripts/python.exe -m ruff check --select F rag/query.py tests/test_config.py` → 0 findings.
- `.delegate_venv/Scripts/python.exe -m pytest -q tests/` → all green (6 from increment 01 + 5 new = 11).
- `.delegate_venv/Scripts/python.exe manage.py check` → clean.

## Do NOT

- Do NOT edit `core/`, `susi_project/`, `rag/ingest.py`, or any `.md` docs.
- Do NOT change `build_prompt`, `ask_susi`, or any function from increment 01.
- Do NOT add a top-level import of yaml/langchain/chromadb (yaml import stays
  inside `_load_config`).
- Do NOT invent extra config keys or prompts beyond the YAML given above.
