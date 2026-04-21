from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    AssignExaminerView,
    ExamCalendarView,
    ExamCenterListView,
    ExaminerUnavailabilityViewSet,
    ExaminerViewSet,
    ExamSlotListView,
)

router = DefaultRouter()
router.register(r"examiners", ExaminerViewSet, basename="examiner")
router.register(
    r"examiner-unavailability",
    ExaminerUnavailabilityViewSet,
    basename="examiner-unavailability",
)

urlpatterns = [
    path("", ExamCenterListView.as_view(), name="center-list"),
    path("slots/", ExamSlotListView.as_view(), name="slot-list"),
    path("slots/<int:slot_id>/assign-examiner/", AssignExaminerView.as_view(), name="assign-examiner"),
    path("calendar/", ExamCalendarView.as_view(), name="exam-calendar"),
    path("", include(router.urls)),
]
