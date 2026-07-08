# core/views.py

import yaml
import os
from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse
from django.views.decorators.http import require_POST
from .models import Chat, Message

# Config einmalig beim Start laden
CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "rag", "susi_config.yaml")

def _load_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

cfg = _load_config()


# ── Hilfsfunktion: aktiven Chat aus Session holen oder neu anlegen ─────────
# Die Session speichert nur noch die active_chat_id (UUID).
# Alle Messages werden aus der DB geladen.
# Kein History-Dict mehr in der Session.

def _get_or_create_chat(request) -> Chat:
    """
    Gibt den aktiven Chat zurück oder legt einen neuen an.

    Die active_chat_id wird in der Session gespeichert.
    Existiert kein Chat mit dieser ID (z.B. nach DB-Reset), wird ein neuer angelegt.
    """
    chat_id  = request.session.get("active_chat_id")
    chat_mode = request.session.get("chat_mode", "AUTO")

    if chat_id:
        try:
            return Chat.objects.get(id=chat_id)
        except Chat.DoesNotExist:
            pass

    # Neuen Chat anlegen
    chat = Chat.objects.create(mode=chat_mode)
    request.session["active_chat_id"] = str(chat.id)
    return chat


# ── Manuell-Modus: Settings-Helper ─────────────────────────────────
# Zentrale Stelle für die Default-Logik — nicht in den Views duplizieren
# (Lektion vom dreifach duplizierten Mapping-Dict in der Eval-Pipeline).

def _config_defaults() -> dict:
    """Manuell-Defaults aus der Config — greift wenn ein Chat noch
    keine eigenen manuell_settings hat."""
    return {
        "llm_model":     cfg["generation"]["llm_model"],
        "top_k":         cfg["retrieval"]["top_k"],
        "temperature":   cfg["generation"]["temperature"],
        "num_ctx":       cfg["generation"]["num_ctx"],
        "system_prompt": cfg["generation"]["system_prompt"],
        "algorithm":     cfg["retrieval"]["algorithm"],
        "thinking":      False,
    }


def _get_manuell_settings(chat: Chat) -> dict:
    """Manuell-Werte des Chats, aufgefüllt mit Config-Defaults für
    fehlende Keys. Chat ohne eigene Werte → reine Defaults."""
    defaults = _config_defaults()
    if chat.manuell_settings:
        defaults.update(chat.manuell_settings)
    return defaults


def _thinking_faehige_modelle() -> set:
    """Namen der Modelle die laut Config den Thinking-Modus können."""
    return {m["name"] for m in cfg.get("available_models", [])
            if m.get("thinking", False)}


def chat_view(request):
    """Hauptseite — Chat mit SUSI"""
    chat      = _get_or_create_chat(request)
    messages  = chat.messages.all()
    chat_mode = request.session.get("chat_mode", "AUTO")

    # Alle Chats für die Sidebar-Liste (neueste zuerst)
    all_chats = Chat.objects.all()

    # Slider zeigen die Manuell-Werte DIESES Chats (oder Config-Defaults
    # wenn der Chat noch keine hat) — nicht mehr die rohe Config.
    ms = _get_manuell_settings(chat)

    return render(request, "core/chat.html", {
        "chat":             chat,
        "messages":         messages,
        "all_chats":        all_chats,
        "chat_mode":        chat_mode,
        "modes":            [("AUTO", "AUTO"), ("MANUELL", "MANUELL"), ("CODING", "CODING")],
        "llm_model":        ms["llm_model"],
        "embedding_model":  cfg["retrieval"]["embedding_model"],
        "top_k":            ms["top_k"],
        "num_ctx":          ms["num_ctx"],
        "algorithm":        ms["algorithm"],
        "temperature":      ms["temperature"],
        "system_prompt":    ms["system_prompt"],
        "thinking":         ms["thinking"],
        "available_models": cfg.get("available_models", []),
    })


@require_POST
def new_chat_view(request):
    """HTMX-Endpunkt — Neuen Chat anlegen und aktivieren.

    Vererbung: der neue Chat übernimmt die manuell_settings des bisher
    aktiven Chats. So muss der User nicht bei jedem neuen Chat die
    Slider neu einstellen — ab dann lebt jeder Chat eigenständig."""
    chat_mode = request.session.get("chat_mode", "AUTO")

    # Manuell-Werte vom bisher aktiven Chat erben (falls vorhanden)
    geerbte_settings = None
    alte_chat_id = request.session.get("active_chat_id")
    if alte_chat_id:
        try:
            alter_chat = Chat.objects.get(id=alte_chat_id)
            geerbte_settings = alter_chat.manuell_settings
        except Chat.DoesNotExist:
            pass

    chat = Chat.objects.create(mode=chat_mode, manuell_settings=geerbte_settings)
    request.session["active_chat_id"] = str(chat.id)
    request.session.modified = True

    # Komplette Seite neu laden — einfachste Lösung für Chat-Wechsel
    from django.shortcuts import redirect
    return redirect("core:chat")


@require_POST
def switch_chat_view(request, chat_id):
    """HTMX-Endpunkt — Zu einem anderen Chat wechseln"""
    # Existenz prüfen, 404 wenn nicht vorhanden
    chat = get_object_or_404(Chat, id=chat_id)
    request.session["active_chat_id"] = str(chat.id)
    request.session["chat_mode"] = chat.mode
    request.session.modified = True

    from django.shortcuts import redirect
    return redirect("core:chat")


@require_POST
def ask_view(request):
    """HTMX-Endpunkt — Frage stellen, Antwort + Metriken zurückgeben"""
    from rag.query import ask_susi

    question = request.POST.get("question", "").strip()
    if not question:
        return HttpResponse("")

    chat      = _get_or_create_chat(request)
    chat_mode = request.session.get("chat_mode", "AUTO")

    # ── Chat-History für Query Rewriter aus DB laden ───────────────
    # Letzte 2 vollständige Q/A-Paare aus der DB holen.
    # Nur Messages des aktiven Chats — kein Cross-Chat-Kontext.
    db_messages  = list(chat.messages.order_by("created_at"))
    chat_history = []
    i = 0
    while i < len(db_messages) - 1:
        if db_messages[i].role == "user" and db_messages[i+1].role == "susi":
            chat_history.append({
                "question": db_messages[i].content,
                "answer":   db_messages[i+1].content[:200],  # Rewriter braucht nicht den vollen Text
            })
            i += 2
        else:
            i += 1
    chat_history = chat_history[-2:] if chat_history else None

    # ── User-Message in DB speichern ──────────────────────────────
    Message.objects.create(
        chat    = chat,
        role    = "user",
        content = question,
    )

    # ── SUSI fragen ───────────────────────────────────────────────
    # Im MANUELL-Modus: die Chat-eigenen Einstellungen als Overrides
    # mitgeben — sie umgehen in ask_susi() den Router.
    overrides = _get_manuell_settings(chat) if chat_mode == "MANUELL" else None
    result = ask_susi(question, chat_history=chat_history, mode=chat_mode,
                      overrides=overrides)

    # ── SUSI-Antwort mit allen Metadaten in DB speichern ──────────
    susi_msg = Message.objects.create(
        chat                  = chat,
        role                  = "susi",
        content               = result["answer"],
        tok_per_sec           = result.get("tok_per_sec"),
        antwortzeit_sek       = result.get("antwortzeit_sek"),
        tokens_generiert      = result.get("tokens_generiert"),
        llm_model             = result.get("llm_model", ""),
        router_profil         = result.get("router_profil", ""),
        reranker_used         = result.get("reranker_used", False),
        chunks_gefunden       = result.get("chunks_gefunden", 0),
        chunks_nach_reranking = result.get("chunks_nach_reranking", 0),
        rewritten_query       = result.get("rewritten_query", ""),
        quelldateien          = result.get("quelldateien", []),
    )

    # ── Chat-Titel automatisch setzen (erste Frage = Titel) ───────
    # Nur beim allerersten Q/A-Paar — danach bleibt der Titel.
    if chat.title == "Neuer Chat":
        chat.title = question[:80]
        chat.mode  = chat_mode
        chat.save()

    # Chat updated_at aktualisieren (auto_now=True macht das automatisch
    # beim save() — aber wir triggern es explizit damit die Sidebar-
    # Sortierung stimmt)
    Chat.objects.filter(id=chat.id).update(updated_at=susi_msg.created_at)

    return render(request, "core/partials/message_pair.html", {
        "question":              question,
        "answer":                result["answer"],
        "tok_per_sec":           result.get("tok_per_sec"),
        "antwortzeit_sek":       result.get("antwortzeit_sek"),
        "tokens_generiert":      result.get("tokens_generiert"),
        "quelldateien":          result.get("quelldateien", []),
        "reranker_used":         result.get("reranker_used", False),
        "chunks_gefunden":       result.get("chunks_gefunden", 0),
        "chunks_nach_reranking": result.get("chunks_nach_reranking", 0),
        "susi_msg_id":           str(susi_msg.id),
        "router_profil":         result.get("router_profil", ""),
        "llm_model":             result.get("llm_model", ""),
    })


@require_POST
def settings_view(request):
    """HTMX-Endpunkt — Manuell-Einstellungen des aktiven Chats ändern.

    UMBAU 07.07.2026: Schreibt in chat.manuell_settings (DB) statt in
    die susi_config.yaml. Die Config bleibt damit unangetastete Single
    Source of Truth für Defaults und den AUTO-Modus — vorher hat jeder
    Slider-Klick die Produktions-Config für ALLE Modi umgeschrieben.

    Nimmt alle Manuell-Felder an: llm_model, top_k, temperature,
    num_ctx, system_prompt, algorithm, thinking."""
    chat = _get_or_create_chat(request)
    ms = _get_manuell_settings(chat)  # bestehende Werte + Defaults

    llm_model     = request.POST.get("llm_model")
    top_k         = request.POST.get("top_k")
    temperature   = request.POST.get("temperature")
    num_ctx       = request.POST.get("num_ctx")
    system_prompt = request.POST.get("system_prompt")
    algorithm     = request.POST.get("algorithm")
    thinking      = request.POST.get("thinking")

    if llm_model:
        ms["llm_model"] = llm_model
        # Thinking zurücksetzen wenn das neue Modell es nicht kann —
        # verhindert dass ein qwen3-Thinking-Flag an llama3.1 klebt.
        if llm_model not in _thinking_faehige_modelle():
            ms["thinking"] = False
    if top_k:
        ms["top_k"] = int(top_k)
    if temperature:
        ms["temperature"] = float(temperature)
    if num_ctx:
        ms["num_ctx"] = int(num_ctx)
    if system_prompt:
        ms["system_prompt"] = system_prompt
    if algorithm:
        ms["algorithm"] = algorithm
    if thinking is not None and thinking != "":
        # Thinking nur akzeptieren wenn das aktuelle Modell es kann
        if ms["llm_model"] in _thinking_faehige_modelle():
            ms["thinking"] = (thinking == "true")
        else:
            ms["thinking"] = False

    chat.manuell_settings = ms
    chat.save(update_fields=["manuell_settings"])

    return HttpResponse('<div class="status-msg status-msg--ok">Einstellungen gespeichert.</div>')


def history_view(request):
    """HTMX-Endpunkt — Chat-History als Fragment (legacy, für Kompatibilität)"""
    chat     = _get_or_create_chat(request)
    messages = chat.messages.all()
    return render(request, "core/history.html", {"messages": messages})


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


@require_POST
def set_mode_view(request):
    """HTMX-Endpunkt — Chat-Modus wechseln (AUTO / MANUELL / CODING)"""
    valid_modes = {"AUTO", "MANUELL", "CODING"}
    mode = request.POST.get("mode", "AUTO").upper()
    if mode not in valid_modes:
        mode = "AUTO"

    request.session["chat_mode"] = mode
    request.session.modified = True

    # Modus auch am aktiven Chat speichern
    chat = _get_or_create_chat(request)
    Chat.objects.filter(id=chat.id).update(mode=mode)

    return render(request, "core/partials/mode_toggle.html", {
        "chat_mode":     mode,
        "modes":         [("AUTO", "AUTO"), ("MANUELL", "MANUELL"), ("CODING", "CODING")],
        "llm_model":     cfg["generation"]["llm_model"],
        "embedding_model": cfg["retrieval"]["embedding_model"],
        "top_k":         cfg["retrieval"]["top_k"],
        "num_ctx":       cfg["generation"]["num_ctx"],
        "algorithm":     cfg["retrieval"]["algorithm"],
        "temperature":   cfg["generation"]["temperature"],
        "system_prompt": cfg["generation"]["system_prompt"],
    })


# ── Profil → Zielordner Mapping ───────────────────────────────────────────
# Wird beim Anlegen eines QueueItems genutzt um den Zielordner vorzuschlagen.
# Martin kann den Ordner im Review-UI noch ändern.
PROFIL_TO_FOLDER = {
    "susi":       "docs/susi/",
    "projekte":   "docs/projekte/",
    "lernen":     "docs/lernen/",
    "persoenlich": "docs/martin/",
    "technik":    "docs/technik/",
    "fallback":   "docs/queue/",
}


@require_POST
def queue_add_view(request):
    """HTMX-Endpunkt — SUSI-Antwort in die HitL Queue aufnehmen.

    Legt ein QueueItem mit status='pending' an.
    Gibt einen Mini-Fragment zurück der den "→ Queue" Button
    durch "✓ in Queue" ersetzt.

    POST-Parameter:
        message_id  — UUID der Message die in die Queue soll
    """
    from .models import QueueItem

    message_id = request.POST.get("message_id", "").strip()
    if not message_id:
        return HttpResponse('<span style="color:var(--error);font-size:10px;">Fehler: keine Message-ID</span>')

    message = get_object_or_404(Message, id=message_id, role="susi")

    # Zielordner aus router_profil ableiten
    target_folder = PROFIL_TO_FOLDER.get(message.router_profil, "docs/queue/")

    # QueueItem anlegen — content kopiert von Message, editierbar beim Review
    QueueItem.objects.create(
        message       = message,
        content       = message.content,
        target_folder = target_folder,
        router_profil = message.router_profil,
        quelldateien  = message.quelldateien,
        mode          = message.chat.mode,
    )

    # Button durch Bestätigung ersetzen
    return HttpResponse(
        '<span class="queue-confirmed">✓ in Queue</span>'
    )