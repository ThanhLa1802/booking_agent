"""
Payment gateway abstraction — MOCK implementation for now.

Real providers (VNPay / MoMo / ZaloPay / Stripe) implement the same interface
later; the domain code only depends on ``get_gateway()``.
"""
from __future__ import annotations

import logging
import uuid
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from .models import (
    Booking,
    BookingStatus,
    Payment,
    PaymentMethod,
    PaymentStatus,
)

logger = logging.getLogger(__name__)


class PaymentGateway:
    """Interface every provider must implement."""

    method: str = PaymentMethod.MOCK

    def initiate(self, booking: Booking) -> Payment:  # pragma: no cover - iface
        raise NotImplementedError

    def confirm(self, payment: Payment) -> Payment:  # pragma: no cover - iface
        raise NotImplementedError

    def refund(self, payment: Payment, amount: Decimal) -> Payment:  # pragma: no cover
        raise NotImplementedError


class MockPaymentGateway(PaymentGateway):
    """
    In-process fake gateway.

    - ``initiate`` creates an INITIATED payment with a fake provider reference.
    - ``confirm`` marks it PAID and moves the booking to PAID.
    - ``refund`` records the refund and updates the booking payment status.

    Nothing leaves the process — this is intentionally a stub so a real
    provider can be dropped in without touching business logic.
    """

    method = PaymentMethod.MOCK

    @transaction.atomic
    def initiate(self, booking: Booking) -> Payment:
        payment = Payment.objects.create(
            booking=booking,
            amount=booking.price,
            currency=booking.currency,
            method=self.method,
            status=PaymentStatus.INITIATED,
            provider_ref=f"MOCK-{uuid.uuid4().hex[:12].upper()}",
            is_mock=True,
            raw_response={"mock": True, "action": "initiate"},
        )
        return payment

    @transaction.atomic
    def confirm(self, payment: Payment) -> Payment:
        payment = Payment.objects.select_for_update().get(pk=payment.pk)
        booking = Booking.objects.select_for_update().get(pk=payment.booking_id)

        payment.status = PaymentStatus.PAID
        payment.paid_at = timezone.now()
        payment.raw_response = {"mock": True, "action": "confirm"}
        payment.save(update_fields=["status", "paid_at", "raw_response"])

        booking.payment_status = PaymentStatus.PAID
        booking.status = BookingStatus.PAID
        booking.hold_expires_at = None
        booking.version += 1
        booking.save(
            update_fields=["payment_status", "status", "hold_expires_at", "version"]
        )
        return payment

    @transaction.atomic
    def refund(self, payment: Payment, amount: Decimal) -> Payment:
        payment = Payment.objects.select_for_update().get(pk=payment.pk)
        booking = Booking.objects.select_for_update().get(pk=payment.booking_id)

        amount = min(Decimal(amount), Decimal(payment.amount))
        payment.refund_amount = amount
        payment.status = (
            PaymentStatus.REFUNDED
            if amount >= payment.amount
            else PaymentStatus.PARTIALLY_REFUNDED
        )
        payment.refunded_at = timezone.now()
        payment.raw_response = {
            "mock": True,
            "action": "refund",
            "amount": str(amount),
        }
        payment.save(
            update_fields=["refund_amount", "status", "refunded_at", "raw_response"]
        )

        booking.payment_status = payment.status
        booking.version += 1
        booking.save(update_fields=["payment_status", "version"])
        return payment


def get_gateway() -> PaymentGateway:
    """Return the configured gateway. Only MOCK exists today."""
    return MockPaymentGateway()
