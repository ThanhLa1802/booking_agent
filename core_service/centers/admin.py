from django.contrib import admin
from .models import ExamCenter, ExamSlot


@admin.register(ExamCenter)
class ExamCenterAdmin(admin.ModelAdmin):
    list_display = ("name", "city", "admin_user", "is_active")
    list_filter = ("city", "is_active")
    search_fields = ("name", "city")


@admin.register(ExamSlot)
class ExamSlotAdmin(admin.ModelAdmin):
    list_display = (
        "course",
        "center",
        "exam_date",
        "start_time",
        "capacity",
        "reserved_count",
        "is_active",
    )
    list_filter = ("center", "exam_date", "is_active")
    search_fields = ("course__instrument__name", "center__name")
