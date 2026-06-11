from django.shortcuts import render

# Create your views here.
import os
import shutil
import subprocess
from pathlib import Path

from django.conf import settings
from django.http import HttpResponse
from django.shortcuts import render
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt

# ── In-Memory Konversations-History (pro Session) ────────────────────────────
_conversation_store: dict[str, list] = {}


def _get_history(request) -> list:
    key = request.session.session_key or ""
    if not key:
        request.session.create()
        key = request.session.session_key
    return _conversation_store.setdefault(key, [])


def _add_to_history(request, role: str, content: str):
    history = _get_history(request)
    history.append({"role": role, "content": content})
    if len(history) > 50:
        _conversation_store[request.session.session_key] = history[-50:]


# ── Hilfsfunktion: SUSI befragen ─────────────────────────────────────────────
def _ask_susi(question: str, top_k=8, temperature=0.0,
              system_prompt="susi_standard", llm_model="qwen2.5-coder:7b") -> str:
    """
    Ruft ask_susi() aus rag/query.py auf.
    Alle Parameter werden aus der Session übergeben.
    """
    try:
        import importlib.util

        rag_path = Path(settings.BASE_DIR) / "rag" / "query.py"
        spec = importlib.util.spec_from_file_location("rag.query", rag_path)
        rag = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(rag)
        return rag.ask_susi(
            question,
            top_k=top_k,
            temperature=temperature,
            system_prompt=system_prompt,
            llm_model=llm_model,
        )
    except Exception as e:
        return f"[SUSI Fehler]: {e}"


# ── Hilfsfunktion: Frontend-Config laden ─────────────────────────────────────
def _get_frontend_config() -> dict:
    """Lädt Parameter-Config aus susi_config.yaml via query.py"""
    try:
        import importlib.util

        rag_path = Path(settings.BASE_DIR) / "rag" / "query.py"
        spec = importlib.util.spec_from_file_location("rag.query", rag_path)
        rag = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(rag)
        return rag.get_frontend_config()
    except Exception:
        # Fallback wenn YAML nicht geladen werden kann
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


# ── Hilfsfunktion: Datei in SUSIpedia ingesten ───────────────────────────────
def _ingest_file(filepath: str) -> tuple[bool, str]:
    try:
        dest_dir = Path(settings.DOCS_PATH) / "uploads"
        dest_dir.mkdir(parents=True, exist_ok=True)

        filename = Path(filepath).name
        dest_path = dest_dir / filename
        shutil.copy2(filepath, dest_path)

        result = subprocess.run(
            ["python", str(Path(settings.BASE_DIR) / "rag" / "ingest.py")],
            capture_output=True,
            text=True,
            timeout=120,
        )

        if result.returncode == 0:
            return True, f"✅ '{filename}' erfolgreich indexiert und ab sofort befragbar."
        else:
            return False, f"⚠️ Indexierung fehlgeschlagen: {result.stderr[:200]}"

    except subprocess.TimeoutExpired:
        return False, "⚠️ Indexierung hat zu lange gedauert (Timeout 120s)."
    except Exception as e:
        return False, f"⚠️ Fehler beim Indexieren: {e}"


# ── Views ─────────────────────────────────────────────────────────────────────

def chat_view(request):
    """Haupt-Chat-Seite — übergibt config aus susi_config.yaml"""
    history = _get_history(request)
    config  = _get_frontend_config()
    return render(request, "core/chat.html", {
        "history": history,
        "config":  config,
    })


@require_http_methods(["POST"])
def ask_view(request):
    """
    HTMX-Endpoint: empfängt Frage + liest Parameter aus Session.
    """
    question = request.POST.get("question", "").strip()

    if not question:
        return HttpResponse(
            '<div class="msg msg--error">Bitte eine Frage eingeben.</div>',
            content_type="text/html",
        )

    # Parameter aus Session (gesetzt durch settings_view)
    top_k         = int(request.session.get("top_k", 8))
    temperature   = float(request.session.get("temperature", 0.0))
    system_prompt = request.session.get("system_prompt", "susi_standard")
    llm_model     = request.session.get("llm_model", "qwen2.5-coder:7b")

    _add_to_history(request, "user", question)

    answer = _ask_susi(
        question,
        top_k=top_k,
        temperature=temperature,
        system_prompt=system_prompt,
        llm_model=llm_model,
    )

    _add_to_history(request, "susi", answer)

    return render(
        request,
        "core/partials/message_pair.html",
        {"question": question, "answer": answer},
    )


@require_http_methods(["POST"])
def settings_view(request):
    """
    HTMX-Endpoint: speichert Parameter in Session.
    Wird bei jeder Änderung in der Sidebar aufgerufen.
    """
    request.session["top_k"]         = int(request.POST.get("top_k", 8))
    request.session["temperature"]   = float(request.POST.get("temperature", 0.0))
    request.session["system_prompt"] = request.POST.get("system_prompt", "susi_standard")
    request.session["llm_model"]     = request.POST.get("llm_model", "qwen2.5-coder:7b")
    return HttpResponse(
        '<span style="color:var(--susi); font-size:10px;">✓ gespeichert</span>'
    )


@require_http_methods(["POST"])
def upload_view(request):
    """HTMX-Endpoint: File Upload + Ingest."""
    if "file" not in request.FILES:
        return render(
            request,
            "core/partials/upload_status.html",
            {"success": False, "message": "⚠️ Keine Datei empfangen."},
        )

    uploaded = request.FILES["file"]
    filename = uploaded.name
    ext = Path(filename).suffix.lower()

    allowed = getattr(settings, "ALLOWED_UPLOAD_EXTENSIONS", [".pdf", ".docx", ".txt", ".md"])
    if ext not in allowed:
        return render(
            request,
            "core/partials/upload_status.html",
            {"success": False, "message": f"⚠️ Dateityp '{ext}' nicht erlaubt."},
        )

    max_mb = getattr(settings, "MAX_UPLOAD_SIZE_MB", 20)
    if uploaded.size > max_mb * 1024 * 1024:
        return render(
            request,
            "core/partials/upload_status.html",
            {"success": False, "message": f"⚠️ Datei zu groß (max {max_mb} MB)."},
        )

    upload_dir = Path(settings.MEDIA_ROOT) / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    temp_path = upload_dir / filename

    with open(temp_path, "wb+") as f:
        for chunk in uploaded.chunks():
            f.write(chunk)

    success, message = _ingest_file(str(temp_path))

    return render(
        request,
        "core/partials/upload_status.html",
        {"success": success, "message": message, "filename": filename},
    )


@require_http_methods(["GET"])
def history_view(request):
    """HTMX-Endpoint: gibt History als Fragment zurück."""
    history = _get_history(request)
    return render(request, "core/partials/history.html", {"history": history})