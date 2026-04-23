from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from .models import Booking
from .serializers import (
    BookingCancelSerializer,
    BookingCreateSerializer,
    BookingRescheduleSerializer,
    BookingSerializer,
)


class BookingListCreateView(generics.ListAPIView):
    permission_classes = (IsAuthenticated,)
    serializer_class = BookingSerializer

    def get_queryset(self):
        return (
            Booking.objects.filter(user=self.request.user)
            .select_related("slot__center", "slot__course__instrument")
        )

    def post(self, request):
        serializer = BookingCreateSerializer(
            data=request.data, context={"request": request}
        )
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        booking = serializer.save()
        return Response(
            BookingSerializer(booking).data, status=status.HTTP_201_CREATED
        )


class BookingDetailView(generics.RetrieveAPIView):
    permission_classes = (IsAuthenticated,)
    serializer_class = BookingSerializer

    def get_queryset(self):
        return Booking.objects.filter(user=self.request.user).select_related(
            "slot__center", "slot__course__instrument"
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

        return Response(BookingSerializer(booking).data)
