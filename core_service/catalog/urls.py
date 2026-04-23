from django.urls import path
from .views import InstrumentListView, CourseListView, CourseDetailView

urlpatterns = [
    path("instruments/", InstrumentListView.as_view(), name="instrument-list"),
    path("courses/", CourseListView.as_view(), name="course-list"),
    path("courses/<int:pk>/", CourseDetailView.as_view(), name="course-detail"),
]
