# core/views.py

import yaml
import os
from django.shortcuts import render
from django.http import HttpResponse
from django.views.decorators.http import require_POST

# Config einmalig beim Start laden
CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "rag", "susi_config.yaml")

def _load_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

cfg = _load_config()


def chat_view(request):
    """Hauptseite — Chat mit SUSI"""
    history = request.session.get("history", [])
    return render(request, "core/chat.html", {
        "history":         history,
        "llm_model":       cfg["generation"]["llm_model"],
        "embedding_model": cfg["retrieval"]["embedding_model"],
        "top_k":           cfg["retrieval"]["top_k"],
        "num_ctx":         cfg["generation"]["num_ctx"],
        "algorithm":       cfg["retrieval"]["algorithm"],
        "temperature":     cfg["generation"]["temperature"],
        "system_prompt":   cfg["generation"]["system_prompt"],
    })


@require_POST
def ask_view(request):
    """HTMX-Endpunkt — Frage stellen, Antwort + Metriken zurückgeben"""
    from rag.query import ask_susi

    question = request.POST.get("question", "").strip()
    if not question:
        return HttpResponse("")

    # ── Chat-History für Query Rewriter aufbereiten ────────────────
    # Aus der Session-History die letzten Q/A Paare extrahieren.
    # Der Rewriter nutzt max. 2 Paare um Folgefragen aufzulösen.
    # Beispiel: "the coast line you mention" → Rewriter sieht vorherige
    # Antwort und kann den Bezug korrekt auflösen.
    #
    # Format für rewrite_query(): [{"question": str, "answer": str}, ...]
    # Nur vollständige Paare (user + susi) werden übergeben.
    session_history = request.session.get("history", [])
    chat_history = []
    i = 0
    while i < len(session_history) - 1:
        if session_history[i]["role"] == "user" and session_history[i+1]["role"] == "susi":
            chat_history.append({
                "question": session_history[i]["content"],
                "answer":   session_history[i+1]["content"],
            })
            i += 2
        else:
            i += 1
    # Nur die letzten 2 Paare — Rewriter soll nicht ausufern
    chat_history = chat_history[-2:] if chat_history else None

    result = ask_susi(question, chat_history=chat_history)

    # History in Session speichern (inkl. Metriken)
    history = request.session.get("history", [])
    history.append({
        "role":    "user",
        "content": question,
    })
    history.append({
        "role":                  "susi",
        "content":               result["answer"],
        "tok_per_sec":           result["tok_per_sec"],
        "antwortzeit_sek":       result["antwortzeit_sek"],
        "tokens_generiert":      result["tokens_generiert"],
        "quelldateien":          result["quelldateien"],
        "reranker_used":         result.get("reranker_used", False),
        "chunks_gefunden":       result.get("chunks_gefunden", 0),
        "chunks_nach_reranking": result.get("chunks_nach_reranking", 0),
    })
    request.session["history"] = history
    request.session.modified = True

    return render(request, "core/partials/message_pair.html", {
        "question":              question,
        "answer":                result["answer"],
        "tok_per_sec":           result["tok_per_sec"],
        "antwortzeit_sek":       result["antwortzeit_sek"],
        "tokens_generiert":      result["tokens_generiert"],
        "quelldateien":          result["quelldateien"],
        "reranker_used":         result.get("reranker_used", False),
        "chunks_gefunden":       result.get("chunks_gefunden", 0),
        "chunks_nach_reranking": result.get("chunks_nach_reranking", 0),
    })


@require_POST
def settings_view(request):
    """HTMX-Endpunkt — Config-Parameter zur Laufzeit ändern"""
    global cfg

    llm_model = request.POST.get("llm_model")
    top_k     = request.POST.get("top_k")
    num_ctx   = request.POST.get("num_ctx")

    if llm_model:
        cfg["generation"]["llm_model"] = llm_model
    if top_k:
        cfg["retrieval"]["top_k"] = int(top_k)
    if num_ctx:
        cfg["generation"]["num_ctx"] = int(num_ctx)

    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        yaml.dump(cfg, f, allow_unicode=True)

    return HttpResponse('<div class="status-msg status-msg--ok">Einstellungen gespeichert.</div>')


def history_view(request):
    """HTMX-Endpunkt — Chat-History als Fragment zurückgeben"""
    history = request.session.get("history", [])
    return render(request, "core/history.html", {"history": history})


@require_POST
def upload_view(request):
    """Datei-Upload in SUSIpedia"""
    import subprocess
    from django.conf import settings

    uploaded_file = request.FILES.get("file")
    if not uploaded_file:
        return HttpResponse('<div style="color:red;font-size:11px;">Keine Datei erhalten.</div>')

    docs_path = os.path.join(settings.BASE_DIR, cfg["paths"]["docs"])
    save_path = os.path.join(docs_path, uploaded_file.name)

    with open(save_path, "wb") as f:
        for chunk in uploaded_file.chunks():
            f.write(chunk)

    subprocess.run(["python", "rag/ingest.py"], capture_output=True)

    return render(request, "core/upload_status.html", {
        "filename": uploaded_file.name,
        "success":  True,
    })