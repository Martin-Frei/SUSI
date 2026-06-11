# core\urls.py

from django.urls import path
from . import views

app_name = "core"

urlpatterns = [
    path("",          views.chat_view,     name="chat"),
    path("ask/",      views.ask_view,      name="ask"),       # HTMX: POST Frage → Antwort HTML
    path("upload/",   views.upload_view,   name="upload"),    # HTMX: POST File Upload
    path("history/",  views.history_view,  name="history"),   # HTMX: GET History-Fragment
    path("settings/", views.settings_view, name="settings"),  # HTMX: POST Parameter speichern
]