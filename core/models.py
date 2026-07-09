# core/models.py
#
# Datenmodell für SUSI Chat-History + HitL Queue.
#
# Aufbau:
#   Chat        — ein Gespräch (ein Thema, ein Tab)
#   Message     — eine einzelne Nachricht inkl. aller RAG-Metadaten
#   QueueItem   — Wissens-Kandidat aus einem Chat, wartet auf Review → Ingest
#
# Designentscheidungen:
#   - quelldateien als JSONField: Quelldateien pro SUSI-Antwort gespeichert
#     damit bei Queue-Review nachvollziehbar ist woher SUSI das wusste.
#   - QueueItem.content eigenes Feld (keine direkte Kopie von Message.content):
#     Martin kann den Text vor dem Review anpassen / kürzen.
#   - QueueItem.mode gespeichert: beim Review sichtbar ob die Antwort aus
#     AUTO (Router) oder MANUELL kam — relevant für Qualitätsbewertung.
#   - on_delete=CASCADE: wird ein Chat gelöscht, verschwinden Messages + Items.

import uuid
from django.db import models


class Chat(models.Model):
    """
    Ein Gespräch mit SUSI — thematisch abgegrenzt, benannt, persistent.

    Ein Chat entspricht einem Tab in der Sidebar. Der User kann zwischen
    Chats wechseln; jeder Chat hat seine eigene Message-History.
    """

    MODE_CHOICES = [
        ("AUTO",    "AUTO — Router bestimmt Profil"),
        ("MANUELL", "MANUELL — User stellt Parameter"),
        ("CHUNKING", "CHUNKING — Dokument-Aufbereitung für Ingest"),
    ]

    id         = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title      = models.CharField(max_length=200, default="Neuer Chat")
    mode       = models.CharField(max_length=10, choices=MODE_CHOICES, default="AUTO")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # ── Manuell-Modus Einstellungen (pro Chat, mit Vererbung) ─────
    # JSON-Dict mit den Overrides für den MANUELL-Modus:
    #   {"llm_model": str, "top_k": int, "temperature": float,
    #    "num_ctx": int, "system_prompt": str, "algorithm": str,
    #    "thinking": bool}
    # null = Chat hat noch keine eigenen Werte → Config-Defaults greifen.
    # Neue Chats erben die Werte des zuletzt aktiven Chats (new_chat_view).
    # Geschrieben von settings_view, gelesen von ask_view/chat_view.
    manuell_settings = models.JSONField(null=True, blank=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self):
        return f"{self.title} [{self.mode}] ({self.created_at:%d.%m.%Y})"


class Message(models.Model):
    """
    Eine einzelne Nachricht innerhalb eines Chats.

    Speichert sowohl User-Nachrichten als auch SUSI-Antworten.
    SUSI-Antworten (role='susi') enthalten zusätzlich alle RAG-Metadaten
    die für spätere Queue-Reviews und Debugging relevant sind.
    """

    ROLE_CHOICES = [
        ("user", "User"),
        ("susi", "SUSI"),
    ]

    id      = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    chat    = models.ForeignKey(Chat, on_delete=models.CASCADE, related_name="messages")
    role    = models.CharField(max_length=10, choices=ROLE_CHOICES)
    content = models.TextField()

    created_at = models.DateTimeField(auto_now_add=True)

    # ── RAG-Metadaten (nur bei role='susi', sonst null) ───────────
    # Gespeichert für: Queue-Review ("woher wusste SUSI das?"),
    # spätere Eval-Analysen, und Debugging von Retrieval-Fehlern.

    tok_per_sec           = models.FloatField(null=True, blank=True)
    antwortzeit_sek       = models.FloatField(null=True, blank=True)
    tokens_generiert      = models.IntegerField(null=True, blank=True)
    llm_model             = models.CharField(max_length=100, blank=True, default="")
    router_profil         = models.CharField(max_length=50, blank=True, default="")
    reranker_used         = models.BooleanField(null=True, blank=True)
    chunks_gefunden       = models.IntegerField(null=True, blank=True)
    chunks_nach_reranking = models.IntegerField(null=True, blank=True)
    rewritten_query       = models.TextField(blank=True, default="")

    # Liste der Quelldateien die der Reranker als Top-Chunks gewählt hat.
    # Format: ["docs/projekte/stockpredict.md", "docs/coding/gmm.md"]
    # Beim Queue-Review sichtbar — beantwortet "woher wusste SUSI das?"
    quelldateien = models.JSONField(null=True, blank=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        preview = self.content[:60].replace("\n", " ")
        return f"[{self.role}] {preview}…"


class QueueItem(models.Model):
    """
    Ein Wissens-Kandidat der aus einem Chat für den SUSIpedia-Ingest vorgemerkt ist.

    Workflow:
        1. Martin markiert eine SUSI-Antwort im Chat → "→ Queue"
        2. QueueItem wird mit status='pending' angelegt
        3. Martin öffnet Queue-Ansicht, reviewed Content + Zielordner
        4. Bei Freigabe: status='approved', Datei wird in target_folder gespeichert
        5. Ingest-Script läuft → Chunk landet in ChromaDB
        6. Bei Ablehnung: status='rejected' (bleibt als Protokoll erhalten)

    QueueItem.content ist ein eigenes Feld (keine direkte Kopie von Message.content)
    damit Martin den Text vor dem Review anpassen oder kürzen kann.
    Der FK auf Message bleibt erhalten — Herkunft ist immer nachvollziehbar.
    """

    STATUS_CHOICES = [
        ("pending",  "Ausstehend — wartet auf Review"),
        ("approved", "Freigegeben — bereit für Ingest"),
        ("rejected", "Abgelehnt"),
    ]

    id      = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    message = models.ForeignKey(Message, on_delete=models.CASCADE, related_name="queue_items")

    # Inhalt — kann vor dem Review bearbeitet werden
    content = models.TextField()

    # Zielordner in der SUSIpedia, z.B. "docs/projekte/" oder "docs/lernen/"
    # Wird beim Anlegen vorgeschlagen (basierend auf router_profil der Message),
    # kann im Review-UI geändert werden.
    target_folder = models.CharField(max_length=200, default="docs/queue/")

    # Optionaler Dateiname — wenn leer wird beim Ingest ein Name generiert
    suggested_filename = models.CharField(max_length=200, blank=True, default="")

    status      = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    created_at  = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)

    # ── Review-Kontext ────────────────────────────────────────────
    # Metadaten der Ursprungs-Message, direkt am QueueItem gespeichert
    # damit der Review-Screen vollständig ist ohne Message nachladen zu müssen.

    # Welches Profil hat den Chunk geliefert? Hilft einzuschätzen ob das
    # Wissen thematisch gut eingeordnet war.
    router_profil = models.CharField(max_length=50, blank=True, default="")

    # Welche Quelldateien hat SUSI für diese Antwort genutzt?
    # Beim Review sichtbar: "SUSI hat das aus diesen Docs gezogen"
    quelldateien = models.JSONField(null=True, blank=True)

    # AUTO oder MANUELL — relevant für Qualitätsbewertung beim Review.
    # Eine MANUELL-Antwort mit gesetztem Profil ist verlässlicher als AUTO mit Fallback.
    mode = models.CharField(max_length=10, blank=True, default="AUTO")

    # Freitext-Notiz von Martin beim Review
    review_notiz = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"[{self.status}] → {self.target_folder} ({self.created_at:%d.%m.%Y})"