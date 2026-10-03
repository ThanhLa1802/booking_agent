from django.urls import path

from .views import (
    BookingCancelView,
    BookingDetailView,
    BookingDocumentView,
    BookingListCreateView,
    BookingPayView,
    BookingRefundView,
    BookingRescheduleView,
    BookingResultView,
    PublishResultView,
)

urlpatterns = [
    path("", BookingListCreateView.as_view(), name="booking-list-create"),
    path("<int:pk>/", BookingDetailView.as_view(), name="booking-detail"),
    path("<int:pk>/cancel/", BookingCancelView.as_view(), name="booking-cancel"),
    path("<int:pk>/reschedule/", BookingRescheduleView.as_view(), name="booking-reschedule"),
    path("<int:pk>/pay/", BookingPayView.as_view(), name="booking-pay"),
    path("<int:pk>/refund/", BookingRefundView.as_view(), name="booking-refund"),
    path("<int:pk>/documents/", BookingDocumentView.as_view(), name="booking-documents"),
    path("<int:pk>/result/", BookingResultView.as_view(), name="booking-result"),
    path("<int:pk>/result/publish/", PublishResultView.as_view(), name="result-publish"),
]
