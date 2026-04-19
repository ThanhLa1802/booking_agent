from django.contrib import admin
from .models import Instrument, Course


@admin.register(Instrument)
class InstrumentAdmin(admin.ModelAdmin):
    list_display = ("name", "style", "is_active")
    list_filter = ("style", "is_active")
    search_fields = ("name",)


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ("instrument", "grade", "fee", "duration_minutes", "is_active")
    list_filter = ("instrument__style", "grade", "is_active")
    search_fields = ("instrument__name", "name")
