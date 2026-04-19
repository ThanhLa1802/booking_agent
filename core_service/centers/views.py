from django.db import models
from rest_framework import generics
from rest_framework.permissions import AllowAny
from .models import ExamCenter, ExamSlot
from .serializers import ExamCenterSerializer, ExamSlotSerializer


class ExamCenterListView(generics.ListAPIView):
    permission_classes = (AllowAny,)
    serializer_class = ExamCenterSerializer

    def get_queryset(self):
        qs = ExamCenter.objects.filter(is_active=True)
        city = self.request.query_params.get("city")
        if city:
            qs = qs.filter(city__icontains=city)
        return qs


class ExamSlotListView(generics.ListAPIView):
    permission_classes = (AllowAny,)
    serializer_class = ExamSlotSerializer

    def get_queryset(self):
        qs = (
            ExamSlot.objects.filter(
                is_active=True, reserved_count__lt=models.F("capacity")
            )
            .select_related("center", "course__instrument")
        )
        course_id = self.request.query_params.get("course")
        center_id = self.request.query_params.get("center")
        city = self.request.query_params.get("city")
        date_from = self.request.query_params.get("date_from")
        date_to = self.request.query_params.get("date_to")

        if course_id:
            qs = qs.filter(course_id=course_id)
        if center_id:
            qs = qs.filter(center_id=center_id)
        if city:
            qs = qs.filter(center__city__icontains=city)
        if date_from:
            qs = qs.filter(exam_date__gte=date_from)
        if date_to:
            qs = qs.filter(exam_date__lte=date_to)
        return qs
