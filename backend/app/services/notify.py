"""Outbound notifications: SMS and email.

No gateway is connected in this deployment. `send_otp` is the single place a
real one plugs in — an SMS provider (MSG91, Twilio, or NIC's own SMS gateway
for a government deployment) and an SMTP relay. Until then it logs that a
message would have been sent, never the code itself, and the route returns the
code in its response only while OTP_DEMO_MODE is on.
"""

from __future__ import annotations

import logging

log = logging.getLogger(__name__)


def send_otp(otp: str, *, phone: str | None, email: str | None) -> bool:
    """Deliver an OTP. Returns True if it was handed to at least one channel."""
    channels = [c for c in (phone and "sms", email and "email") if c]
    log.info("OTP issued; would deliver via %s (no gateway configured)", ", ".join(channels) or "nothing")
    return bool(channels)


def send_new_device_alert(
    *, phone: str | None, email: str | None, device: str, decision_url: str
) -> bool:
    """'New sign-in to your E-Panchayat account from <device>. Was this you?
    Approve or deny: <link>' — by SMS and email."""
    channels = [c for c in (phone and "sms", email and "email") if c]
    log.info(
        "New-device sign-in alert for %s; would deliver via %s (no gateway configured)",
        device, ", ".join(channels) or "nothing",
    )
    return bool(channels)
