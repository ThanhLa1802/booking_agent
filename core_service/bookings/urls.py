from django.urls import path
from .views import BookingCancelView, BookingDetailView, BookingListCreateView, BookingRescheduleView

urlpatterns = [
    path("", BookingListCreateView.as_view(), name="booking-list-create"),
    path("<int:pk>/", BookingDetailView.as_view(), name="booking-detail"),
    path("<int:pk>/cancel/", BookingCancelView.as_view(), name="booking-cancel"),
    path("<int:pk>/reschedule/", BookingRescheduleView.as_view(), name="booking-reschedule"),
]
