# Increment 04 — Persist chat history in the Django ORM

## Goal

Replace the process-global `_conversation_store` dict in core/views.py with a
real `ChatMessage` model. The global dict is lost on every restart, is shared
across all workers/processes, and grows unbounded. A per-session DB table fixes
all three.

Note: request settings (top_k, temperature, etc.) already live in
`request.session` with the DB session backend, so they are already persistent —
this increment only moves the chat history, it does NOT touch settings storage.

OUT of scope: the migration file (Claude generates it with makemigrations after
you write the model); security/cleanup (increment 05).

## Files

- Edit: `core/models.py`   (add ChatMessage)
- Edit: `core/views.py`    (rewrite history helpers; remove the global dict)
- Edit: `core/tests.py`    (add a Django TestCase)

Do NOT create a migration file yourself — Claude runs `makemigrations`.

## Required API / behavior

### core/models.py — replace the stub with
```python
from django.db import models


class ChatMessage(models.Model):
    """One chat turn, scoped to a browser session. Replaces the in-memory
    global dict so history survives restarts and is not shared across workers."""

    ROLE_CHOICES = [("user", "user"), ("susi", "susi")]

    session_key = models.CharField(max_length=40, db_index=True)
    role = models.CharField(max_length=10, choices=ROLE_CHOICES)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]

    def __str__(self):
        return f"{self.session_key} {self.role}: {self.content[:40]}"
```

### core/views.py — changes
1. DELETE the module-level `_conversation_store: dict[str, list] = {}` line and
   its comment header.
2. Add a top-level import of the model in the import block (after the django
   imports): `from core.models import ChatMessage`.
3. Replace BOTH `_get_history` and `_add_to_history` with:
```python
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
```
The old 50-message cap is dropped: it only existed to bound the in-memory dict;
DB rows scoped per session do not need it. All other view functions are unchanged
and keep calling `_get_history` / `_add_to_history` exactly as before (the return
shape — a list of `{"role", "content"}` dicts — is identical).

### core/tests.py — replace the stub with
```python
from django.test import TestCase

from core.models import ChatMessage


class ChatMessageModelTest(TestCase):
    def test_messages_persist_and_order_chronologically(self):
        ChatMessage.objects.create(session_key="abc", role="user", content="frage 1")
        ChatMessage.objects.create(session_key="abc", role="susi", content="antwort 1")
        ChatMessage.objects.create(session_key="other", role="user", content="fremd")

        msgs = list(ChatMessage.objects.filter(session_key="abc"))
        self.assertEqual(len(msgs), 2)
        self.assertEqual([m.role for m in msgs], ["user", "susi"])
        self.assertEqual(msgs[0].content, "frage 1")

    def test_history_is_scoped_per_session(self):
        ChatMessage.objects.create(session_key="s1", role="user", content="a")
        ChatMessage.objects.create(session_key="s2", role="user", content="b")
        self.assertEqual(ChatMessage.objects.filter(session_key="s1").count(), 1)
```

## Acceptance (Claude runs these after generating the migration)

- `ruff check --select F core/models.py core/views.py core/tests.py` → 0 findings.
- `manage.py makemigrations core` → creates `core/migrations/0001_initial.py`.
- `manage.py makemigrations --check --dry-run` → "No changes detected".
- `manage.py test core` → green (2 new tests).
- `pytest -q tests/` → still 13 green.
- `manage.py check` → clean.

## Do NOT

- Do NOT create or edit any migration file (Claude does that).
- Do NOT touch `rag/`, `susi_project/`, templates, `.md` docs, or `core/urls.py`.
- Do NOT change settings storage (session-based, already persistent).
- Do NOT add dependencies. Do NOT alter the upload/ingest code.
