# rag/debug.py
# Zentrales Debug- und Logging-System für die SUSI-Pipeline.
#
# Design (nach Tutor-Feedback Tanveer):
#   - Nativer Python-Logger statt print()/debug_print()
#   - Context Manager für Phasen-Timing (kein globales Timing-Dict)
#   - Dual-Output: Terminal + rotierende Log-Datei logs/susi_pipeline.log
#   - Gesteuert über susi_config.yaml → debug-Block:
#
#       debug:
#         active: true          # Master-Schalter
#         level: DEBUG          # DEBUG | INFO | WARNING
#         log_to_file: true     # logs/susi_pipeline.log
#         show_chunks: false    # Chunk-Inhalte im Log (viel Output!)
#         show_timings: true    # Phasen-Timing-Tabelle nach jeder Frage
#
# Verwendung:
#   from rag.debug import get_logger, Timer, TimingCollector
#
#   log = get_logger(__name__)
#   log.info("🌍 Sprache erkannt: %s", lang)
#
#   timings = TimingCollector()
#   with Timer("retrieval", timings):
#       docs = db.similarity_search(...)
#   timings.report()   # druckt Timing-Tabelle wenn show_timings=true

import logging
import time
import os
from logging.handlers import RotatingFileHandler
from contextlib import contextmanager

from rag.config import load_config

# ── Debug-Config lesen (einmalig beim Import) ────────────────────
_debug_cfg = load_config().get("debug", {})

DEBUG_ACTIVE  = _debug_cfg.get("active", True)
DEBUG_LEVEL   = _debug_cfg.get("level", "INFO").upper()
LOG_TO_FILE   = _debug_cfg.get("log_to_file", True)
SHOW_CHUNKS   = _debug_cfg.get("show_chunks", False)
SHOW_TIMINGS  = _debug_cfg.get("show_timings", True)

_LOG_DIR  = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")
_LOG_FILE = os.path.join(_LOG_DIR, "susi_pipeline.log")

_LEVEL_MAP = {
    "DEBUG":   logging.DEBUG,
    "INFO":    logging.INFO,
    "WARNING": logging.WARNING,
}

_configured = False


def _configure_root():
    """Einmalige Logger-Konfiguration: Console + rotierende Datei.
    Idempotent — mehrfacher Aufruf fügt keine doppelten Handler hinzu."""
    global _configured
    if _configured:
        return

    root = logging.getLogger("susi")
    root.setLevel(_LEVEL_MAP.get(DEBUG_LEVEL, logging.INFO))
    root.propagate = False  # nicht doppelt über Root-Logger ausgeben

    # Console-Handler — kompaktes Format wie die bisherigen prints
    console = logging.StreamHandler()
    console.setFormatter(logging.Formatter("  %(message)s"))
    root.addHandler(console)

    # File-Handler — volles Format mit Timestamp + Modul + Level
    # RotatingFileHandler: max 2 MB pro Datei, 3 Backups (susi_pipeline.log.1 etc.)
    if LOG_TO_FILE:
        os.makedirs(_LOG_DIR, exist_ok=True)
        file_handler = RotatingFileHandler(
            _LOG_FILE, maxBytes=2_000_000, backupCount=3, encoding="utf-8"
        )
        file_handler.setFormatter(logging.Formatter(
            "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"
        ))
        root.addHandler(file_handler)

    if not DEBUG_ACTIVE:
        root.setLevel(logging.WARNING)  # nur Warnungen/Fehler wenn debug aus

    _configured = True


def get_logger(name: str) -> logging.Logger:
    """Gibt einen Logger unterhalb des susi-Namespace zurück.
    Aufruf: log = get_logger(__name__)"""
    _configure_root()
    # rag.query → susi.rag.query — alles hängt unter "susi"
    return logging.getLogger(f"susi.{name}")


# ── Phasen-Timing ────────────────────────────────────────────────

class TimingCollector:
    """Sammelt Phasen-Timings einer einzelnen Frage.
    Pro ask_susi()-Aufruf eine neue Instanz — kein globaler State,
    dadurch thread-safe wenn Django mehrere Requests parallel bedient."""

    def __init__(self):
        self.phases: list[tuple[str, float]] = []

    def add(self, name: str, seconds: float):
        self.phases.append((name, seconds))

    @property
    def total(self) -> float:
        return sum(s for _, s in self.phases)

    def report(self, log: logging.Logger | None = None):
        """Druckt die Timing-Tabelle (wenn show_timings aktiv)."""
        if not SHOW_TIMINGS or not self.phases:
            return
        out = log.info if log else print
        out("⏱️  Phasen-Timing:")
        for name, seconds in self.phases:
            pct = (seconds / self.total * 100) if self.total > 0 else 0
            out(f"   {name:<22} {seconds:>7.3f}s  ({pct:>4.1f}%)")
        out(f"   {'─' * 40}")
        out(f"   {'GESAMT':<22} {self.total:>7.3f}s")


@contextmanager
def Timer(phase_name: str, collector: TimingCollector | None = None,
          log: logging.Logger | None = None):
    """Context Manager für Phasen-Timing.

    Verwendung:
        with Timer("retrieval", timings):
            docs = db.similarity_search(...)

    Misst die Wandzeit des Blocks und trägt sie in den Collector ein.
    Bei DEBUG-Level wird jede Phase auch einzeln geloggt.
    """
    start = time.perf_counter()
    try:
        yield
    finally:
        elapsed = time.perf_counter() - start
        if collector is not None:
            collector.add(phase_name, elapsed)
        if log is not None:
            log.debug("⏱️  %s: %.3fs", phase_name, elapsed)


# ── Debug-Ausgaben für Pipeline-Interna ──────────────────────────

def debug_show_chunks(docs, log: logging.Logger, title: str = "Chunks"):
    """Zeigt Chunk-Quellen und (bei show_chunks=true) auch Inhalte.
    Nur aktiv bei DEBUG-Level."""
    if not log.isEnabledFor(logging.DEBUG):
        return
    log.debug("🔍 %s (%d):", title, len(docs))
    for i, doc in enumerate(docs, 1):
        source = doc.metadata.get("source", "?")
        if SHOW_CHUNKS:
            log.debug("   %d. %s\n      %s", i, source, doc.page_content[:150])
        else:
            log.debug("   %d. %s", i, source)


def debug_show_reranker(ranked_docs, log: logging.Logger, top_n: int):
    """Zeigt Reranker-Scores der Top-Chunks. Nur bei DEBUG-Level."""
    if not log.isEnabledFor(logging.DEBUG):
        return
    log.debug("🔁 Reranker-Scores (Top %d):", top_n)
    for i, (score, doc) in enumerate(ranked_docs[:top_n], 1):
        source = doc.metadata.get("source", "?")
        log.debug("   %d. %.4f  %s", i, score, source)
