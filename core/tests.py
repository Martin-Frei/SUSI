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
