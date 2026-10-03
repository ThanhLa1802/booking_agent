"""
Notification providers — MOCK implementations.

Each provider returns True on success. Real SMTP / Twilio / FCM clients
implement the same ``send`` signature later.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


class MockEmailProvider:
    name = "mock-email"

    def send(self, recipient: str, subject: str, body: str) -> bool:
        logger.info("[MOCK EMAIL] to=%s subject=%s\n%s", recipient, subject, body)
        return True


class MockSmsProvider:
    name = "mock-sms"

    def send(self, recipient: str, subject: str, body: str) -> bool:
        logger.info("[MOCK SMS] to=%s\n%s", recipient, body)
        return True


_PROVIDERS = {
    "EMAIL": MockEmailProvider(),
    "SMS": MockSmsProvider(),
    "PUSH": MockEmailProvider(),
}


def get_provider(channel: str):
    return _PROVIDERS.get(channel, _PROVIDERS["EMAIL"])
