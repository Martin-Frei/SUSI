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
