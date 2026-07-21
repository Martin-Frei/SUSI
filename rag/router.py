# rag/router.py
# Retrieval-getriebener Router für SUSI
# Bestimmt das optimale Profil anhand der Reranker-gewichteten Chunk-Quellen
# Stand: 20.06.2026

from __future__ import annotations
from pathlib import Path

# Minimum Reranker-Score damit der Router ein Profil wählt.
# Alles darunter ist Rauschen — Fallback greift.
# bge-reranker-v2-m3 Logit-Skala: 0–0.5 = irrelevant, 2+ = guter Match
ROUTER_MIN_SCORE = 0.5


# ── Profil-Auswahl via Reranker-Voting ────────────────────────────

def get_profile(ranked_docs: list, folder_profile_map: dict, profiles: dict,
               fallback_profile: str = "persoenlich") -> tuple[str, dict]:
    """
    Analysiert die Top-Chunks nach dem Reranking und wählt ein Profil.

    Args:
        ranked_docs:        Liste von (score: float, doc: Document) — bereits rerankt, absteigende Reihenfolge
        folder_profile_map: dict aus susi_config.yaml → router.folder_profile_map
        profiles:           dict aus susi_config.yaml → profiles
        fallback_profile:   Profil-Name wenn alle Scores unter Threshold (aus susi_config.yaml)

    Returns:
        (profil_name: str, profil_config: dict)

    Edge-Cases:
        - Keine Chunks: erstes Profil in profiles wird genutzt
        - Alle Scores <= 0.01: fallback_profile greift (kein Signal aus Retrieval)
            Neuer Test: <= 0.5 greift als Schwellenwert 
          Das passiert wenn ChromaDB zwar Chunks findet, der Reranker aber alle
          als irrelevant einstuft — z.B. bei Fragen außerhalb der SUSIpedia.
    """
    profil_gewichte: dict[str, float] = {}

    for score, doc in ranked_docs:
        source = doc.metadata.get("source", "")
        profil = _source_to_profile(source, folder_profile_map)
        profil_gewichte[profil] = profil_gewichte.get(profil, 0.0) + float(score)

    if not profil_gewichte:
        fallback = fallback_profile if fallback_profile in profiles else next(iter(profiles))
        print(f"  ⚠️  Keine Chunks — Fallback: {fallback}")
        return fallback, profiles[fallback]

    # Edge-Case: alle Scores nahe 0 → kein Signal → Fallback
    # Verhindert zufällige Profil-Auswahl bei irrelevanten Chunks
    max_score = max(profil_gewichte.values())
    if max_score <= ROUTER_MIN_SCORE:
        fallback = fallback_profile if fallback_profile in profiles else next(iter(profiles))
        print(f"  ⚠️  Alle Scores <= {ROUTER_MIN_SCORE} — kein Signal — Fallback: {fallback}")
        return fallback, profiles[fallback]

    gewinner = max(profil_gewichte, key=lambda p: profil_gewichte[p])
    _log_voting(profil_gewichte, gewinner)

    return gewinner, profiles[gewinner]


def _source_to_profile(source: str, folder_profile_map: dict) -> str:
    """
    Mappt einen Chunk-Quellpfad auf ein Profil.
    Beispiel: 'docs/coding/susi/susi_architektur.md' → 'projekte'
    Erstes passendes Segment in folder_profile_map gewinnt.
    Fallback: 'persoenlich'
    """
    normalized = Path(source).as_posix().lower()
    parts = normalized.split("/")

    for part in parts:
        if part in folder_profile_map:
            return folder_profile_map[part]

    return "persoenlich"


def _log_voting(gewichte: dict[str, float], gewinner: str) -> None:
    """Gibt Voting-Ergebnis auf Konsole aus."""
    print("  🗳️  Router-Voting:")
    for profil, gewicht in sorted(gewichte.items(), key=lambda x: x[1], reverse=True):
        marker = "✅" if profil == gewinner else "  "
        print(f"     {marker} {profil:<15} {gewicht:.4f}")
    print(f"  → Profil gewählt: {gewinner}")


# ── Profil auf query-Parameter mappen ─────────────────────────────

def apply_profile(profil_config: dict, system_prompts: dict) -> dict:
    """
    Übersetzt ein Profil-Dict in die Parameter die query.py direkt nutzen kann.

    Returns:
        {
            "llm_model":     str,
            "top_k":         int,
            "top_n":         int,
            "algorithm":     str,
            "temperature":   float,
            "system_prompt": str,   ← Prompt-Text, nicht Name
            "thinking":      bool,  ← Platzhalter für qwen3, von Ollama ignoriert wenn nicht unterstützt
        }
    """
    prompt_name = profil_config.get("system_prompt", "praezise_neu")
    system_prompt = system_prompts.get(prompt_name, system_prompts.get("praezise_neu", ""))

    return {
        "llm_model":     profil_config["llm"],
        "top_k":         profil_config["top_k"],
        "top_n":         profil_config["top_n"],
        "algorithm":     profil_config["algorithm"],
        "temperature":   profil_config["temperature"],
        "system_prompt": system_prompt,
        "thinking":      profil_config.get("thinking", False),
    }