from rest_framework import generics
from rest_framework.permissions import AllowAny
from .models import Instrument, Course
from .serializers import InstrumentSerializer, CourseSerializer


class InstrumentListView(generics.ListAPIView):
    permission_classes = (AllowAny,)
    serializer_class = InstrumentSerializer
    queryset = Instrument.objects.filter(is_active=True)

    def get_queryset(self):
        qs = super().get_queryset()
        style = self.request.query_params.get("style")
        if style:
            qs = qs.filter(style=style)
        return qs


class CourseListView(generics.ListAPIView):
    permission_classes = (AllowAny,)
    serializer_class = CourseSerializer

    def get_queryset(self):
        qs = Course.objects.filter(is_active=True).select_related("instrument")
        instrument_id = self.request.query_params.get("instrument")
        style = self.request.query_params.get("style")
        grade = self.request.query_params.get("grade")
        if instrument_id:
            qs = qs.filter(instrument_id=instrument_id)
        if style:
            qs = qs.filter(instrument__style=style)
        if grade:
            qs = qs.filter(grade=grade)
        return qs


class CourseDetailView(generics.RetrieveAPIView):
    permission_classes = (AllowAny,)
    serializer_class = CourseSerializer
    queryset = Course.objects.filter(is_active=True).select_related("instrument")
