# core/urls.py

from django.urls import path
from . import views

app_name = "core"

urlpatterns = [
    path("",                        views.chat_view,        name="chat"),
    path("ask/",                    views.ask_view,         name="ask"),
    path("upload/",                 views.upload_view,      name="upload"),
    path("history/",                views.history_view,     name="history"),
    path("settings/",               views.settings_view,    name="settings"),
    path("set_mode/",               views.set_mode_view,    name="set_mode"),
    path("new_chat/",               views.new_chat_view,    name="new_chat"),
    path("chat/<uuid:chat_id>/",    views.switch_chat_view, name="switch_chat"),
    path("queue/add/",              views.queue_add_view,   name="queue_add"),
]