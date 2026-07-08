"""KRYP-26 — Trivial beneficiary-notification stub.

KRYP-30 extension point: a real ``NotificationService`` port/adapter (SMS/push)
will replace this later. For now it only logs — deliberately no abstraction.
"""
import logging

logger = logging.getLogger(__name__)


def notify_beneficiary_sms(momo_number: str, message: str) -> None:
    """Log a would-be SMS confirmation to the beneficiary (KRYP-30 stub)."""
    logger.info("SMS to %s: %s", momo_number, message)
