from django.contrib import admin

from .models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("id", "template", "channel", "recipient", "status", "created_at")
    list_filter = ("template", "channel", "status")
    search_fields = ("recipient", "subject")
