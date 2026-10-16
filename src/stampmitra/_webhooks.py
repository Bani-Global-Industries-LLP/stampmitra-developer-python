"""Webhook signature verification.

Scheme (from the delivery worker, ``src/webhooks/webhook-signing.ts``)::

    signature = hex( HMAC-SHA256( secret, f"{timestamp}.{raw_body}" ) )

sent in the headers ``X-Webhook-Signature`` and ``X-Webhook-Timestamp`` (Unix
seconds); ``X-Webhook-Event-Id`` carries the event id. ``raw_body`` must be the
exact bytes received (the server signs ``JSON.stringify(payload)``): pass the
raw request body, not a re-serialised dict.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from typing import Optional, Union

from .errors import WebhookSignatureError
from .models import WebhookEvent

SIGNATURE_HEADER = "X-Webhook-Signature"
TIMESTAMP_HEADER = "X-Webhook-Timestamp"
EVENT_ID_HEADER = "X-Webhook-Event-Id"
DEFAULT_TOLERANCE_SECONDS = 300

__all__ = [
    "DEFAULT_TOLERANCE_SECONDS",
    "EVENT_ID_HEADER",
    "SIGNATURE_HEADER",
    "TIMESTAMP_HEADER",
    "compute_signature",
    "construct_event",
    "verify_signature",
]


def _to_bytes(payload: Union[str, bytes, bytearray]) -> bytes:
    if isinstance(payload, str):
        return payload.encode("utf-8")
    if isinstance(payload, (bytes, bytearray)):
        return bytes(payload)
    raise WebhookSignatureError(
        "payload must be the raw request body (str or bytes), not a parsed object: re-serialising changes the signed bytes"
    )


def compute_signature(payload: Union[str, bytes], timestamp: Union[str, int], secret: str) -> str:
    """Hex HMAC-SHA256 over ``"<timestamp>.<payload>"``."""
    message = str(timestamp).encode("utf-8") + b"." + _to_bytes(payload)
    return hmac.new(secret.encode("utf-8"), message, hashlib.sha256).hexdigest()


def verify_signature(
    payload: Union[str, bytes],
    timestamp: Union[str, int],
    signature: str,
    secret: str,
    tolerance_seconds: Optional[int] = DEFAULT_TOLERANCE_SECONDS,
    *,
    now: Optional[float] = None,
) -> bool:
    """Verify a webhook delivery. Returns ``True`` or raises :class:`WebhookSignatureError`.

    The failure reason is in ``error.code``: ``signature_mismatch``,
    ``timestamp_outside_tolerance``, ``invalid_timestamp`` or ``missing_secret``.
    The signature must be lowercase hex exactly as sent. Uses a constant-time comparison and rejects timestamps further than
    ``tolerance_seconds`` from now (pass ``None`` to disable the age check).
    """
    if not secret:
        raise WebhookSignatureError("webhook secret is empty", code="missing_secret")
    try:
        ts = int(str(timestamp).strip())
    except ValueError:
        raise WebhookSignatureError("invalid webhook timestamp", code="invalid_timestamp") from None
    expected = compute_signature(payload, str(timestamp).strip(), secret)
    given = signature if isinstance(signature, str) else ""
    if not hmac.compare_digest(expected.encode("ascii"), given.encode("utf-8")):
        raise WebhookSignatureError("webhook signature does not match", code="signature_mismatch")
    if tolerance_seconds is not None:
        current = time.time() if now is None else now
        if abs(current - ts) > tolerance_seconds:
            raise WebhookSignatureError(
                f"webhook timestamp outside the {tolerance_seconds}s tolerance (possible replay)",
                code="timestamp_outside_tolerance",
            )
    return True


def construct_event(
    payload: Union[str, bytes],
    timestamp: Union[str, int],
    signature: str,
    secret: str,
    tolerance_seconds: Optional[int] = DEFAULT_TOLERANCE_SECONDS,
    *,
    now: Optional[float] = None,
) -> WebhookEvent:
    """Verify the signature, then parse the body into a :class:`WebhookEvent`."""
    verify_signature(payload, timestamp, signature, secret, tolerance_seconds, now=now)
    try:
        data = json.loads(_to_bytes(payload))
    except ValueError as exc:
        raise WebhookSignatureError(f"webhook body is not valid JSON: {exc}") from None
    if not isinstance(data, dict):
        raise WebhookSignatureError("webhook body must be a JSON object")
    return WebhookEvent.model_validate(data)
