from django.db import models
from rest_framework import generics, status, viewsets
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import UserRole
from .models import ExamCenter, ExamSlot, Examiner, ExaminerUnavailability
from .serializers import (
    AssignExaminerSerializer,
    ExamCenterSerializer,
    ExaminerSerializer,
    ExaminerUnavailabilitySerializer,
    ExamSlotSerializer,
)


def _is_center_admin(user) -> bool:
    """Return True if the authenticated user has the CENTER_ADMIN role."""
    try:
        return user.profile.role == UserRole.CENTER_ADMIN
    except Exception:
        return False


# ── Public read-only views ────────────────────────────────────────────────────


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
            .select_related("center", "course__instrument", "examiner")
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


# ── CENTER_ADMIN — Examiner CRUD ──────────────────────────────────────────────


class ExaminerViewSet(viewsets.ModelViewSet):
    """
    CRUD for examiners. Only CENTER_ADMIN may write; reads are restricted
    to the admin's own center.
    """

    permission_classes = (IsAuthenticated,)
    serializer_class = ExaminerSerializer

    def get_queryset(self):
        user = self.request.user
        if not _is_center_admin(user):
            return Examiner.objects.none()
        try:
            center = user.managed_center
        except ExamCenter.DoesNotExist:
            return Examiner.objects.none()
        return Examiner.objects.filter(center=center).prefetch_related("specializations")

    def perform_create(self, serializer):
        if not _is_center_admin(self.request.user):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("Only CENTER_ADMIN can create examiners.")
        try:
            center = self.request.user.managed_center
        except ExamCenter.DoesNotExist:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("Your account is not linked to any exam center.")
        serializer.save(center=center)


class ExaminerUnavailabilityViewSet(viewsets.ModelViewSet):
    """Manage leave / unavailability periods for an examiner. CENTER_ADMIN only."""

    permission_classes = (IsAuthenticated,)
    serializer_class = ExaminerUnavailabilitySerializer

    def get_queryset(self):
        user = self.request.user
        if not _is_center_admin(user):
            return ExaminerUnavailability.objects.none()
        try:
            center = user.managed_center
        except ExamCenter.DoesNotExist:
            return ExaminerUnavailability.objects.none()
        return ExaminerUnavailability.objects.filter(examiner__center=center)


# ── CENTER_ADMIN — Assign examiner to slot ────────────────────────────────────


class AssignExaminerView(APIView):
    """
    POST /api/centers/slots/{slot_id}/assign-examiner/
    Body: { "examiner_id": <int> }

    Validates:
    - Examiner is active
    - Examiner is not on leave on the slot date
    - Examiner has not reached max_exams_per_day on the slot date
    """

    permission_classes = (IsAuthenticated,)

    def post(self, request, slot_id):
        if not _is_center_admin(request.user):
            return Response(
                {"detail": "Only CENTER_ADMIN can assign examiners."},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            slot = ExamSlot.objects.select_related("center").get(pk=slot_id)
        except ExamSlot.DoesNotExist:
            return Response({"detail": "Slot not found."}, status=status.HTTP_404_NOT_FOUND)

        # ensure the slot belongs to the admin's center
        try:
            center = request.user.managed_center
        except ExamCenter.DoesNotExist:
            return Response(
                {"detail": "Your account is not linked to any exam center."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if slot.center_id != center.pk:
            return Response(
                {"detail": "You can only manage slots at your own center."},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = AssignExaminerSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        examiner = Examiner.objects.get(pk=serializer.validated_data["examiner_id"])
        ok, reason = examiner.is_assignable_to_slot(slot)
        if not ok:
            return Response({"detail": reason}, status=status.HTTP_409_CONFLICT)

        slot.examiner = examiner
        slot.save(update_fields=["examiner"])
        return Response(ExamSlotSerializer(slot).data, status=status.HTTP_200_OK)


# ── CENTER_ADMIN — Exam Calendar ──────────────────────────────────────────────


class ExamCalendarView(generics.ListAPIView):
    """
    GET /api/centers/calendar/
    Returns all slots (including fully booked) for the current admin's center,
    with examiner details. Supports date_from / date_to filters.
    """

    permission_classes = (IsAuthenticated,)
    serializer_class = ExamSlotSerializer

    def get_queryset(self):
        if not _is_center_admin(self.request.user):
            return ExamSlot.objects.none()
        try:
            center = self.request.user.managed_center
        except ExamCenter.DoesNotExist:
            return ExamSlot.objects.none()

        qs = ExamSlot.objects.filter(center=center).select_related(
            "center", "course__instrument", "examiner"
        )
        date_from = self.request.query_params.get("date_from")
        date_to = self.request.query_params.get("date_to")
        if date_from:
            qs = qs.filter(exam_date__gte=date_from)
        if date_to:
            qs = qs.filter(exam_date__lte=date_to)
        return qs
