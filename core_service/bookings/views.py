from decimal import Decimal

from auditing.services import log_action
from django.utils import timezone
from notifications.services import (
    notify_booking_confirmation,
    notify_payment_receipt,
)
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import (
    Booking,
    BookingStatus,
    ExamResult,
    PaymentStatus,
    ResultStatus,
)
from .payments import get_gateway
from .serializers import (
    BookingCancelSerializer,
    BookingCreateSerializer,
    BookingRescheduleSerializer,
    BookingSerializer,
    CandidateDocumentSerializer,
    ExamResultSerializer,
)


class BookingListCreateView(generics.ListAPIView):
    permission_classes = (IsAuthenticated,)
    serializer_class = BookingSerializer

    def get_queryset(self):
        return (
            Booking.objects.filter(user=self.request.user)
            .select_related("slot__center", "slot__course__instrument")
            .prefetch_related("payments", "documents")
        )

    def post(self, request):
        # ── idempotency: replay the original response on a repeated key ───────
        idem_key = request.headers.get("Idempotency-Key") or request.data.get(
            "idempotency_key"
        )
        if idem_key:
            existing = Booking.objects.filter(
                user=request.user, idempotency_key=idem_key
            ).first()
            if existing is not None:
                return Response(
                    BookingSerializer(existing).data, status=status.HTTP_200_OK
                )

        data = dict(request.data)
        if idem_key:
            data["idempotency_key"] = idem_key
        serializer = BookingCreateSerializer(
            data=data, context={"request": request}
        )
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        booking = serializer.save()
        log_action(
            actor=request.user,
            action="booking.created",
            entity_type="Booking",
            entity_id=booking.pk,
            metadata={"slot_id": booking.slot_id, "price": str(booking.price)},
            request=request,
        )
        return Response(
            BookingSerializer(booking).data, status=status.HTTP_201_CREATED
        )


class BookingDetailView(generics.RetrieveAPIView):
    permission_classes = (IsAuthenticated,)
    serializer_class = BookingSerializer

    def get_queryset(self):
        return (
            Booking.objects.filter(user=self.request.user)
            .select_related("slot__center", "slot__course__instrument")
            .prefetch_related("payments", "documents")
        )


class BookingCancelView(APIView):
    permission_classes = (IsAuthenticated,)

    def post(self, request, pk):
        try:
            booking = Booking.objects.get(pk=pk, user=request.user)
        except Booking.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

        serializer = BookingCancelSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            booking = serializer.cancel(booking)
        except Exception as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        log_action(
            actor=request.user,
            action="booking.cancelled",
            entity_type="Booking",
            entity_id=booking.pk,
            request=request,
        )
        return Response(BookingSerializer(booking).data)


class BookingRescheduleView(APIView):
    """
    POST /api/bookings/{pk}/reschedule/
    Body: { "new_slot_id": <int>, "reason": "..." }

    Atomically moves a confirmed booking from its current slot to a new slot.
    Only the booking owner may reschedule.
    """

    permission_classes = (IsAuthenticated,)

    def post(self, request, pk):
        try:
            booking = Booking.objects.get(pk=pk, user=request.user)
        except Booking.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

        serializer = BookingRescheduleSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            booking = serializer.reschedule(booking)
        except Exception as exc:
            error_msg = str(exc)
            # slot full → 409 Conflict
            if "fully booked" in error_msg.lower():
                return Response({"detail": error_msg}, status=status.HTTP_409_CONFLICT)
            return Response({"detail": error_msg}, status=status.HTTP_400_BAD_REQUEST)

        log_action(
            actor=request.user,
            action="booking.rescheduled",
            entity_type="Booking",
            entity_id=booking.pk,
            metadata={"new_slot_id": booking.slot_id},
            request=request,
        )
        return Response(BookingSerializer(booking).data)


class BookingPayView(APIView):
    """
    POST /api/bookings/{pk}/pay/
    Body: { "method": "MOCK" }  (optional)

    MOCK: marks the booking paid via the in-process gateway. A real provider
    would return a checkout URL here instead.
    """

    permission_classes = (IsAuthenticated,)

    def post(self, request, pk):
        try:
            booking = Booking.objects.get(pk=pk, user=request.user)
        except Booking.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

        if booking.status == BookingStatus.CANCELLED:
            return Response(
                {"detail": "Cannot pay for a cancelled booking."},
                status=status.HTTP_409_CONFLICT,
            )
        if booking.payment_status == PaymentStatus.PAID:
            return Response(BookingSerializer(booking).data, status=status.HTTP_200_OK)

        gateway = get_gateway()
        payment = gateway.initiate(booking)
        payment = gateway.confirm(payment)
        booking.refresh_from_db()

        try:
            notify_booking_confirmation(booking)
            notify_payment_receipt(booking, payment)
        except Exception:  # notifications must not break payment
            pass

        log_action(
            actor=request.user,
            action="booking.paid",
            entity_type="Booking",
            entity_id=booking.pk,
            metadata={"payment_id": payment.pk, "amount": str(payment.amount)},
            request=request,
        )
        return Response(BookingSerializer(booking).data, status=status.HTTP_200_OK)


class BookingRefundView(APIView):
    """
    POST /api/bookings/{pk}/refund/
    MOCK: refunds the computed policy amount for a paid booking.
    """

    permission_classes = (IsAuthenticated,)

    def post(self, request, pk):
        try:
            booking = Booking.objects.get(pk=pk, user=request.user)
        except Booking.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

        payment = booking.payments.filter(status=PaymentStatus.PAID).first()
        if payment is None:
            return Response(
                {"detail": "No paid payment to refund."},
                status=status.HTTP_409_CONFLICT,
            )

        from .policies import compute_refund_amount

        amount = compute_refund_amount(booking.price, booking.slot.exam_date)
        if amount <= Decimal("0"):
            return Response(
                {"detail": "Refund window has closed for this booking."},
                status=status.HTTP_409_CONFLICT,
            )

        payment = get_gateway().refund(payment, amount)
        booking.refresh_from_db()
        log_action(
            actor=request.user,
            action="booking.refunded",
            entity_type="Booking",
            entity_id=booking.pk,
            metadata={"payment_id": payment.pk, "amount": str(amount)},
            request=request,
        )
        return Response(BookingSerializer(booking).data, status=status.HTTP_200_OK)


class BookingDocumentView(APIView):
    """
    POST /api/bookings/{pk}/documents/
    Body: { "doc_type": "ID_CARD", "file_ref": "..." }

    MOCK upload: stores a reference string only (no file I/O).
    """

    permission_classes = (IsAuthenticated,)

    def post(self, request, pk):
        try:
            booking = Booking.objects.get(pk=pk, user=request.user)
        except Booking.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

        serializer = CandidateDocumentSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        document = serializer.save(booking=booking)
        log_action(
            actor=request.user,
            action="document.uploaded",
            entity_type="Booking",
            entity_id=booking.pk,
            metadata={"doc_type": document.doc_type},
            request=request,
        )
        return Response(
            CandidateDocumentSerializer(document).data, status=status.HTTP_201_CREATED
        )


class BookingResultView(APIView):
    """GET /api/bookings/{pk}/result/ — published exam result + certificate."""

    permission_classes = (IsAuthenticated,)

    def get(self, request, pk):
        try:
            booking = Booking.objects.get(pk=pk, user=request.user)
        except Booking.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

        try:
            result = booking.result
        except ExamResult.DoesNotExist:
            return Response(
                {"detail": "Result not published yet."},
                status=status.HTTP_404_NOT_FOUND,
            )
        data = ExamResultSerializer(result).data
        cert = getattr(result, "certificate", None)
        data["certificate"] = (
            {
                "serial_number": cert.serial_number,
                "file_ref": cert.file_ref,
                "issued_at": cert.issued_at,
            }
            if cert
            else None
        )
        return Response(data)


class PublishResultView(APIView):
    """
    POST /api/bookings/{pk}/result/publish/
    Body: { "mark": 88.5, "grade_awarded": "Merit", "examiner_comment": "..." }

    MOCK: center admin publishes a result and (optionally) issues a certificate.
    """

    permission_classes = (IsAuthenticated,)

    def post(self, request, pk):
        from accounts.models import UserProfile, UserRole
        from centers.models import ExamCenter

        try:
            profile = request.user.profile
        except (AttributeError, UserProfile.DoesNotExist):
            return Response({"detail": "No profile."}, status=status.HTTP_403_FORBIDDEN)

        if profile.role != UserRole.CENTER_ADMIN:
            return Response(
                {"detail": "Only CENTER_ADMIN can publish results."},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            booking = Booking.objects.select_related("slot__center").get(pk=pk)
        except Booking.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

        try:
            center = request.user.managed_center
        except ExamCenter.DoesNotExist:
            return Response(
                {"detail": "Your account is not linked to any exam center."},
                status=status.HTTP_403_FORBIDDEN,
            )
        if booking.slot.center_id != center.pk:
            return Response(
                {"detail": "Booking belongs to another center."},
                status=status.HTTP_403_FORBIDDEN,
            )

        result, _ = ExamResult.objects.get_or_create(booking=booking)
        result.status = ResultStatus.PUBLISHED
        result.mark = request.data.get("mark")
        result.grade_awarded = request.data.get("grade_awarded", "")
        result.examiner_comment = request.data.get("examiner_comment", "")
        result.published_at = timezone.now()
        result.save()

        from notifications.services import notify_result_published

        try:
            notify_result_published(booking, result)
        except Exception:
            pass

        log_action(
            actor=request.user,
            action="result.published",
            entity_type="Booking",
            entity_id=booking.pk,
            request=request,
        )
        return Response(ExamResultSerializer(result).data, status=status.HTTP_200_OK)
