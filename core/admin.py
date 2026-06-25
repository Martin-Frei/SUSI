from django.contrib import admin
from .models import Chat, Message, QueueItem

admin.site.register(Chat)
admin.site.register(Message)
admin.site.register(QueueItem)