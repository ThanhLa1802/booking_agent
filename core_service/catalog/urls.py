from django.urls import path

from .views import CourseDetailView, CourseListView, InstrumentListView

urlpatterns = [
    path("instruments/", InstrumentListView.as_view(), name="instrument-list"),
    path("courses/", CourseListView.as_view(), name="course-list"),
    path("courses/<int:pk>/", CourseDetailView.as_view(), name="course-detail"),
]
