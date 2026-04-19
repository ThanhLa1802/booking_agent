from django.contrib import admin
from .models import Booking, BookingStatus


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "student_name",
        "user",
        "slot",
        "status",
        "created_at",
    )
    list_filter = ("status",)
    search_fields = ("student_name", "user__username", "slot__course__instrument__name")
    actions = ["cancel_selected"]

    @admin.action(description="Cancel selected bookings")
    def cancel_selected(self, request, queryset):
        queryset.update(status=BookingStatus.CANCELLED)
