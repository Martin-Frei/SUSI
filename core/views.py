import shutil
from pathlib import Path, PurePosixPath

from django.conf import settings
from django.core.exceptions import SuspiciousFileOperation
from django.utils.text import get_valid_filename
from django.http import HttpResponse
from django.shortcuts import render
from django.views.decorators.http import require_http_methods

from core.models import ChatMessage


def _session_key(request) -> str:
    if not request.session.session_key:
        request.session.create()
    return request.session.session_key


def _get_history(request) -> list:
    key = _session_key(request)
    return [
        {"role": m.role, "content": m.content}
        for m in ChatMessage.objects.filter(session_key=key).order_by("created_at", "id")
    ]


def _add_to_history(request, role: str, content: str):
    key = _session_key(request)
    ChatMessage.objects.create(session_key=key, role=role, content=content)


# ── Hilfsfunktion: SUSI befragen ─────────────────────────────────────────────
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


# ── Hilfsfunktion: Frontend-Config laden ─────────────────────────────────────
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


# ── Hilfsfunktion: Safe filename ─────────────────────────────────────────────
def _safe_filename(name: str) -> str:
    """Return a safe leaf filename for an upload.

    Strips any directory components (handling both forward and back slashes) so
    a crafted name like '../../etc/passwd' cannot escape the upload directory,
    then validates the leaf. Raises SuspiciousFileOperation for empty, '.' or
    '..' names."""
    leaf = PurePosixPath(name.replace("\\", "/")).name
    return get_valid_filename(leaf)


# ── Hilfsfunktion: Datei in SUSIpedia ingesten ───────────────────────────────
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
    try:
        filename = _safe_filename(uploaded.name)
    except SuspiciousFileOperation:
        return render(
            request,
            "core/partials/upload_status.html",
            {"success": False, "message": "⚠️ Ungültiger Dateiname."},
        )
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