# rag/query.py
# RAG-Pipeline & CLI — Hauptdatei.
#
# Refactoring 17.07.2026: Aufgeteilt in Module (config, keywords,
# llm_client, utils, debug). Debug-System mit Phasen-Timing.
#
# Debug-Steuerung über susi_config.yaml:
#   debug:
#     active: true
#     level: INFO          # DEBUG zeigt Chunks + Reranker-Scores
#     log_to_file: true    # logs/susi_pipeline.log
#     show_chunks: false
#     show_timings: true   # ⏱️ Phasen-Tabelle nach jeder Frage
#
# Aktivieren: susi_env\Scripts\activate
# Starten:    python -m rag.query   (oder python rag/query.py)

import sys
import os
os.environ["CUDA_VISIBLE_DEVICES"] = ""

# Projekt-Root in den Pfad — damit "python rag/query.py" direkt funktioniert
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import time
import requests
from langchain_ollama import OllamaEmbeddings
from langchain_chroma import Chroma
from sentence_transformers import CrossEncoder

from rag.config import (
    load_config, OLLAMA_URL, CHROMA_PATH, EMBEDDING_MODEL,
)
from rag.llm_client import detect_language, rewrite_query
from rag.utils import get_time
from rag.router import get_profile, apply_profile
from rag import agent_datum
from rag.debug import (
    get_logger, Timer, TimingCollector,
    debug_show_chunks, debug_show_reranker,
)

log = get_logger(__name__)


# ── Reranker (einmalig laden, Singleton) ─────────────────────────
_reranker_cfg   = load_config().get("reranker", {})
RERANKER_ACTIVE = _reranker_cfg.get("active", False)
RERANKER_MODEL  = _reranker_cfg.get("model", "BAAI/bge-reranker-v2-m3")

_reranker = None

def get_reranker():
    """Lazy-Init des CrossEncoder Rerankers. Wird einmalig geladen
    und danach als Singleton wiederverwendet."""
    global _reranker
    if _reranker is None and RERANKER_ACTIVE:
        log.info("🔁 Lade Reranker: %s", RERANKER_MODEL)
        _reranker = CrossEncoder(RERANKER_MODEL, device="cpu")
    return _reranker


# ── Kern-Funktion ─────────────────────────────────────────────────
def ask_susi(question, chat_history: list | None = None, mode: str = "auto",
             overrides: dict | None = None, eval_mode: bool = False):
    """
    Stellt eine Frage an SUSI und gibt ein Dict zurück.

    Args:
        question:     Die aktuelle Frage des Nutzers
        chat_history: Optionale Session-History für den Query Rewriter.
                      Format: [{"question": str, "answer": str}, ...]
                      Wird von views.py befüllt — max. letzte 2 Q/A Paare.
        mode:         Frontend-Modus ("auto" | "manuell" | "chunking").
                      agent_datum ist bei auto UND manuell aktiv.
        overrides:    Manuell-Einstellungen aus chat.manuell_settings.
                      Wenn gesetzt: Router aus, diese Werte gewinnen.
        eval_mode:    True → zusätzliche Eval-Felder (kontext_vor/nach,
                      chunk_scores). Genutzt von grid_run.py --live.

    Returns:
        Dict mit answer, Metriken, Quellen — siehe Handoff-Doku.
        Bei eval_mode=True zusätzlich kontext_vor_reranking,
        kontext_nach_reranking, chunk_scores.
    """
    now = get_time()
    timings = TimingCollector()

    # Mode normalisieren — das Frontend sendet "AUTO"/"MANUELL"/"CHUNKING"
    mode = (mode or "auto").lower()
    log.debug("── Neue Frage [mode=%s, eval=%s]: %s", mode, eval_mode, question[:80])

    # Config frisch laden (damit Frontend-Änderungen sofort wirken)
    cfg = load_config()

    # Fallback-Parameter aus Config
    top_k           = cfg["retrieval"]["top_k"]
    algorithm       = cfg["retrieval"]["algorithm"]
    llm_model       = cfg["generation"]["llm_model"]
    temperature     = cfg["generation"]["temperature"]
    num_ctx         = cfg["generation"]["num_ctx"]
    keep_alive      = cfg["generation"]["keep_alive"]
    prompt_name     = cfg["generation"]["system_prompt"]
    system_prompt   = cfg["system_prompts"][prompt_name]
    thinking        = False

    reranker_active = cfg.get("reranker", {}).get("active", False)
    reranker_top_n  = cfg.get("reranker", {}).get("top_n", 3)
    router_active   = cfg.get("router", {}).get("active", False)
    query_rewrite   = cfg.get("query_rewriting", {}).get("active", True)
    router_profil   = "fallback"

    # ── MANUELL-Modus: Overrides anwenden ─────────────────────────
    if overrides:
        llm_model   = overrides.get("llm_model", llm_model)
        top_k       = int(overrides.get("top_k", top_k))
        temperature = float(overrides.get("temperature", temperature))
        num_ctx     = int(overrides.get("num_ctx", num_ctx))
        algorithm   = overrides.get("algorithm", algorithm)
        thinking    = bool(overrides.get("thinking", False))
        override_prompt_name = overrides.get("system_prompt")
        if override_prompt_name and override_prompt_name in cfg["system_prompts"]:
            system_prompt = cfg["system_prompts"][override_prompt_name]
        router_active = False
        router_profil = "manuell"
        log.info("🎛️  MANUELL: %s | k=%s | t=%s | ctx=%s | thinking=%s",
                 llm_model, top_k, temperature, num_ctx, thinking)

    # 0. Sprache erkennen — vor Agent, Rewriter und Retrieval
    with Timer("detect_language", timings, log):
        lang = detect_language(question, llm_model, keep_alive)

    # 0a. agent_datum — deterministische Kalenderfragen (Zweig 1)
    if mode in ("auto", "manuell") and lang == "de" and agent_datum.is_calendar_question(question):
        agent_start = time.time()
        agent_antwort = agent_datum.answer_calendar_question(question)
        agent_wall = round(time.time() - agent_start, 3)
        log.info("🧮 agent_datum aktiv — deterministische Antwort (%.3fs)", agent_wall)
        result = {
            "answer":                agent_antwort,
            "tok_per_sec":           0.0,
            "antwortzeit_sek":       agent_wall,
            "tokens_generiert":      0,
            "quelldateien":          ["🧮 agent_datum (deterministisch)"],
            "llm_model":             "agent_datum",
            "embedding_model":       EMBEDDING_MODEL,
            "reranker_used":         False,
            "chunks_gefunden":       0,
            "chunks_nach_reranking": 0,
            "router_profil":         "agent_datum",
            "thinking":              False,
            "rewritten_query":       question,
        }
        if eval_mode:
            result["kontext_vor_reranking"]  = ""
            result["kontext_nach_reranking"] = ""
            result["chunk_scores"]           = []
        return result

    rewritten_query = question
    if query_rewrite:
        with Timer("rewrite_query", timings, log):
            rewritten_query = rewrite_query(question, llm_model, keep_alive, chat_history, lang)

    # 1. Retrieval (mit umgeschriebener Frage)
    with Timer("retrieval", timings, log):
        embeddings = OllamaEmbeddings(model=EMBEDDING_MODEL)
        db = Chroma(persist_directory=CHROMA_PATH, embedding_function=embeddings)

        if algorithm == "mmr":
            docs = db.max_marginal_relevance_search(rewritten_query, k=top_k)
        else:
            docs = db.similarity_search(rewritten_query, k=top_k)

    chunks_gefunden = len(docs)
    debug_show_chunks(docs, log, title="Chunks vor Reranking")

    # Kontext VOR Reranking speichern (nur bei eval_mode)
    kontext_vor = ""
    if eval_mode:
        kontext_vor = "\n---\n".join(
            f"[{d.metadata.get('source', '?')}]\n{d.page_content}" for d in docs
        )

    # 2. Reranking
    reranker_used = False
    ranked_docs = []
    chunk_scores = []

    if reranker_active:
        with Timer("reranking", timings, log):
            reranker = get_reranker()
            if reranker:
                pairs = [(rewritten_query, doc.page_content) for doc in docs]
                
                # ── DEBUG: Chunk-Längen vor Reranking ──
                for i, (q, chunk) in enumerate(pairs):
                    src = docs[i].metadata.get("source", "?")
                    log.info(f"  📏 Chunk {i}: {len(chunk)} chars | {src}")
                    
                scores = reranker.predict(pairs)
                ranked_docs = sorted(
                    zip([float(s) for s in scores], docs),
                    key=lambda x: x[0],
                    reverse=True
                )
                if eval_mode:
                    chunk_scores = [
                        (round(s, 4), d.metadata.get("source", "?"), d.page_content[:100])
                        for s, d in ranked_docs
                    ]
                debug_show_reranker(ranked_docs, log, reranker_top_n)
                docs = [doc for _, doc in ranked_docs[:reranker_top_n]]
                reranker_used = True

    # Kontext NACH Reranking speichern (nur bei eval_mode)
    kontext_nach = ""
    if eval_mode:
        kontext_nach = "\n---\n".join(
            f"[{d.metadata.get('source', '?')}]\n{d.page_content}" for d in docs
        )

    # 3. Router — Profil anhand der Top-Chunks bestimmen
    if router_active and ranked_docs:
        with Timer("router", timings, log):
            folder_profile_map = cfg.get("router", {}).get("folder_profile_map", {})
            profiles           = cfg.get("profiles", {})
            system_prompts     = cfg.get("system_prompts", {})

            fallback_profile = cfg.get("router", {}).get("fallback_profile", "persoenlich")
            profil_name, profil_config = get_profile(ranked_docs[:reranker_top_n], folder_profile_map, profiles, fallback_profile)
            params = apply_profile(profil_config, system_prompts)

            llm_model     = params["llm_model"]
            temperature   = params["temperature"]
            system_prompt = params["system_prompt"]
            thinking      = params["thinking"]
            router_profil = profil_name

        log.info("🤖 LLM: %s | thinking: %s | t=%s", llm_model, thinking, temperature)

    # 4. Kontext zusammenbauen
    context = "\n\n".join([doc.page_content for doc in docs])
    quelldateien = list({doc.metadata.get("source", "?") for doc in docs})

    # 4a. agent_datum Zweig 2 — Dauer/Alter aus Chunk, deterministisch
    duration_entity = (agent_datum.is_duration_question(question)
                       or agent_datum.is_duration_question(rewritten_query))
    if duration_entity and docs:
        fact = None
        fact_source = None
        with Timer("agent_datum_zweig2", timings, log):
            for doc in docs:
                fact = agent_datum.calculate_duration_from_chunk(question, doc.page_content, entity_name=duration_entity)
                if fact:
                    fact_source = doc.metadata.get("source", "?")
                    break
        if fact:
            context = fact + "\n\n" + context
            quelldateien = ["🧮 agent_datum (Zweig 2)"] + quelldateien
            log.info("🧮 agent_datum Zweig 2 (%s): %s", duration_entity, fact[:80])
            log.info("   Quelle: %s", fact_source)
        else:
            log.warning("⚠️  Zweig 2 SKIP: entity=%s, kein Datum in %d Chunks",
                        duration_entity, len(docs))
    elif duration_entity:
        log.warning("⚠️  Zweig 2 SKIP: entity=%s, docs=EMPTY", duration_entity)

    # 5. Prompt bauen (Original-Frage ans LLM, nicht die umgeschriebene)
    lang_instruction = f"Answer in the language with ISO code '{lang}'."
    log.debug("🗣️  Sprach-Anweisung: %s", lang_instruction)

    prompt = f"""{system_prompt}

Heute ist: {now}

Kontext:
{context}

Frage: {question}

WICHTIG: {lang_instruction}
Antwort:"""

    # 6. Ollama-Payload
    options = {
        "temperature": temperature,
        "num_ctx":     num_ctx,
    }
    if thinking:
        options["thinking"] = True

    payload = {
        "model":      llm_model,
        "prompt":     prompt,
        "stream":     False,
        "keep_alive": keep_alive,
        "options":    options,
    }

    # 7. LLM aufrufen
    with Timer("generation", timings, log):
        start = time.time()
        response = requests.post(OLLAMA_URL, json=payload, timeout=120)
        response.raise_for_status()
        wall_time = round(time.time() - start, 2)

    data = response.json()

    eval_count    = data.get("eval_count", 0)
    eval_duration = data.get("eval_duration", 1)
    tok_per_sec   = round(eval_count / eval_duration * 1e9, 1) if eval_duration > 0 else 0.0

    # ⏱️ Phasen-Timing ausgeben (gesteuert über debug.show_timings)
    timings.report(log)

    result = {
        "answer":                data.get("response", "").strip(),
        "tok_per_sec":           tok_per_sec,
        "antwortzeit_sek":       wall_time,
        "tokens_generiert":      eval_count,
        "quelldateien":          quelldateien,
        "llm_model":             llm_model,
        "embedding_model":       EMBEDDING_MODEL,
        "reranker_used":         reranker_used,
        "chunks_gefunden":       chunks_gefunden,
        "chunks_nach_reranking": len(docs),
        "router_profil":         router_profil,
        "thinking":              thinking,
        "rewritten_query":       rewritten_query,
    }

    if eval_mode:
        result["kontext_vor_reranking"]  = kontext_vor
        result["kontext_nach_reranking"] = kontext_nach
        result["chunk_scores"]           = chunk_scores

    return result


# ── Eval-Wrapper (Rückwärtskompatibilität für grid_run.py) ────────
def ask_susi_eval(question: str, chat_history: list | None = None) -> dict:
    """
    Ruft ask_susi mit eval_mode=True auf.
    Einziger Konsument: grid_run.py mit --live Flag.
    """
    return ask_susi(question, chat_history=chat_history, eval_mode=True)


# ── Retrieval Debug ───────────────────────────────────────────────
def debug_retrieval(question):
    """Standalone-Debug: zeigt die Top-k Chunks für eine Frage an."""
    embeddings = OllamaEmbeddings(model=EMBEDDING_MODEL)
    db = Chroma(persist_directory=CHROMA_PATH, embedding_function=embeddings)
    top_k = load_config()["retrieval"]["top_k"]
    docs = db.similarity_search(question, k=top_k)
    print("\n🔍 DEBUG – Gefundene Chunks:")
    for i, doc in enumerate(docs, 1):
        source = doc.metadata.get("source", "?")
        print(f"\n{i}. {source}")
        print(doc.page_content[:150])
        print("---")


# ── CLI ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    from rag.utils import worth_saving, show_save_prompt
    from rag.llm_client import susi_evaluates

    print(f"🤖 SUSI ist bereit! (Embed: {EMBEDDING_MODEL} | Reranker: {RERANKER_MODEL})")
    print("   exit zum Beenden\n")

    while True:
        question = input("Du: ")
        if question.lower() == "exit":
            break

        result = ask_susi(question)
        profil_info   = f"Profil: {result['router_profil']}"
        thinking_info = " | 🧠 thinking" if result["thinking"] else ""
        print(f"\nSUSI: {result['answer']}")
        print(f"      ⚡ {result['tok_per_sec']} tok/s · {result['tokens_generiert']} Tokens · {result['antwortzeit_sek']}s · {profil_info}{thinking_info}\n")

        if worth_saving(question):
            if susi_evaluates(question, result["answer"]):
                show_save_prompt(question, result["answer"])
