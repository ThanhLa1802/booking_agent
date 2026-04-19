from django.urls import path
from .views import ExamCenterListView, ExamSlotListView

urlpatterns = [
    path("", ExamCenterListView.as_view(), name="center-list"),
    path("slots/", ExamSlotListView.as_view(), name="slot-list"),
]
