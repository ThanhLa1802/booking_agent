import json

import redis as _redis
from django.conf import settings
from django.db import models, transaction
from rest_framework import generics, serializers, status, viewsets
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
from .tasks import solve_schedule_plan


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


# ── CENTER_ADMIN — Batch schedule (OR-Tools plan + confirm) ───────────────────


class _BatchScheduleSerializer(serializers.Serializer):
    date_from = serializers.DateField()
    date_to = serializers.DateField()

    def validate(self, data):
        if data["date_to"] < data["date_from"]:
            raise serializers.ValidationError("date_to must be on or after date_from.")
        delta = (data["date_to"] - data["date_from"]).days
        if delta > 31:
            raise serializers.ValidationError(
                "Date range cannot exceed 31 days per request."
            )
        return data


class BatchScheduleView(APIView):
    """
    POST /api/centers/schedule/batch/
    Body: { "date_from": "YYYY-MM-DD", "date_to": "YYYY-MM-DD" }

    Fires a background Celery task that computes an OR-Tools schedule plan
    (read-only — no DB writes).  Returns the task_id immediately (HTTP 202).
    The admin must review the plan and call  BatchScheduleConfirmView  to
    commit it to the database.
    """

    permission_classes = (IsAuthenticated,)

    def post(self, request):
        if not _is_center_admin(request.user):
            return Response(
                {"detail": "Only CENTER_ADMIN can schedule examiners."},
                status=status.HTTP_403_FORBIDDEN,
            )
        try:
            center = request.user.managed_center
        except ExamCenter.DoesNotExist:
            return Response(
                {"detail": "Your account is not linked to any exam center."},
                status=status.HTTP_403_FORBIDDEN,
            )

        ser = _BatchScheduleSerializer(data=request.data)
        if not ser.is_valid():
            return Response(ser.errors, status=status.HTTP_400_BAD_REQUEST)

        date_from = ser.validated_data["date_from"].isoformat()
        date_to = ser.validated_data["date_to"].isoformat()

        task = solve_schedule_plan.delay(
            center_id=center.pk,
            date_from=date_from,
            date_to=date_to,
            user_id=request.user.pk,
        )
        return Response({"task_id": task.id}, status=status.HTTP_202_ACCEPTED)


class BatchScheduleConfirmView(APIView):
    """
    POST /api/centers/schedule/batch/{task_id}/confirm/

    Reads the plan stored in Redis by solve_schedule_plan, validates
    ownership, then bulk-assigns examiners to slots inside a single
    database transaction.  Updates the Redis record to status COMMITTED.
    """

    permission_classes = (IsAuthenticated,)

    def post(self, request, task_id):
        if not _is_center_admin(request.user):
            return Response(
                {"detail": "Only CENTER_ADMIN can confirm a schedule."},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Read plan from Redis
        rc = _redis.from_url(settings.REDIS_URL, decode_responses=True)
        raw = rc.get(f"schedule_task:{task_id}")
        if not raw:
            return Response(
                {"detail": "Task not found or expired."},
                status=status.HTTP_404_NOT_FOUND,
            )

        plan_data = json.loads(raw)

        if plan_data.get("status") != "SUCCESS":
            return Response(
                {"detail": f"Task is not ready (status={plan_data.get('status')})."},
                status=status.HTTP_409_CONFLICT,
            )

        if plan_data.get("user_id") != request.user.pk:
            return Response(
                {"detail": "You are not the owner of this schedule task."},
                status=status.HTTP_403_FORBIDDEN,
            )

        plan = plan_data.get("plan", [])
        if not plan:
            return Response({"assigned_count": 0}, status=status.HTTP_200_OK)

        # Bulk-assign inside a single transaction
        assigned_count = 0
        with transaction.atomic():
            for item in plan:
                updated = ExamSlot.objects.filter(
                    pk=item["slot_id"],
                    examiner__isnull=True,   # skip if already assigned
                ).update(examiner_id=item["examiner_id"])
                assigned_count += updated

        # Update Redis record to COMMITTED
        from datetime import datetime, timezone as _tz
        plan_data["status"] = "COMMITTED"
        plan_data["assigned_count"] = assigned_count
        plan_data["committed_at"] = datetime.now(_tz.utc).isoformat()
        rc.setex(f"schedule_task:{task_id}", 7_200, json.dumps(plan_data))

        return Response({"assigned_count": assigned_count}, status=status.HTTP_200_OK)
