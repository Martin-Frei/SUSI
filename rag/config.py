# rag/config.py
# Konfiguration — Single Source of Truth aus susi_config.yaml
#
# Zwei Arten von Werten:
#   STATISCH (Modul-Level):  OLLAMA_URL, CHROMA_PATH, DOCS_PATH, EMBEDDING_MODEL
#                            Ändern sich nie zur Laufzeit.
#   DYNAMISCH (per Aufruf):  llm_model, top_k, temperature, num_ctx, system_prompt
#                            Werden in ask_susi() frisch aus load_config() gelesen,
#                            damit Änderungen an der YAML sofort wirken.
#
# Debug-Block (neu 17.07.):
#   debug:
#     active: true        # Master-Schalter für Debug-Logging
#     level: INFO         # DEBUG | INFO | WARNING
#     log_to_file: true   # logs/susi_pipeline.log (rotierend, 2MB, 3 Backups)
#     show_chunks: false  # Chunk-Inhalte im Log (viel Output)
#     show_timings: true  # Phasen-Timing-Tabelle nach jeder Frage

import sys
import os

# Projekt-Root in den Pfad — damit "python rag/xyz.py" direkt funktioniert
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import yaml


CONFIG_PATH = os.path.join(os.path.dirname(__file__), "susi_config.yaml")

def load_config() -> dict:
    """Lädt die komplette susi_config.yaml. Wird pro ask_susi()-Aufruf
    frisch aufgerufen damit Frontend-Änderungen sofort wirken."""
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


# ── Statische Konstanten (einmalig beim Import) ─────────────────
_cfg = load_config()

OLLAMA_URL      = "http://localhost:11434/api/generate"
CHROMA_PATH     = _cfg["retrieval"]["chroma_path"]
DOCS_PATH       = _cfg["paths"]["docs"]
EMBEDDING_MODEL = _cfg["retrieval"]["embedding_model"]

# Defaults für CLI-Speicherlogik (create_summary, susi_evaluates)
LLM_MODEL       = _cfg["generation"]["llm_model"]
KEEP_ALIVE      = _cfg["generation"]["keep_alive"]
