"""Typed exceptions raised by the SDK.

Every API failure maps to a subclass of :class:`StampMitraError` by HTTP status.
Transport problems raise :class:`APIConnectionError` / :class:`APITimeoutError`
(named to avoid shadowing the Python built-ins ``ConnectionError`` and
``TimeoutError``).
"""

from __future__ import annotations

from typing import Any, Dict, Optional

__all__ = [
    "APIConnectionError",
    "APITimeoutError",
    "AuthenticationError",
    "ConfigurationError",
    "ConflictError",
    "NotFoundError",
    "PaymentRequiredError",
    "PermissionDeniedError",
    "RateLimitError",
    "StampMitraError",
    "UpstreamError",
    "ValidationError",
    "WebhookSignatureError",
]


class StampMitraError(Exception):
    """Base class for every error raised by this SDK."""

    def __init__(
        self,
        message: str,
        *,
        status: Optional[int] = None,
        code: Optional[str] = None,
        request_id: Optional[str] = None,
        body: Any = None,
        field: Optional[str] = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status = status
        self.code = code
        self.request_id = request_id
        #: The parsed JSON error body (or the raw text when it was not JSON).
        self.body = body
        self.field = field

    def __str__(self) -> str:
        parts = [self.message]
        extra = []
        if self.status is not None:
            extra.append(f"status={self.status}")
        if self.code:
            extra.append(f"code={self.code}")
        if self.request_id:
            extra.append(f"request_id={self.request_id}")
        if extra:
            parts.append("(" + ", ".join(extra) + ")")
        return " ".join(parts)

    def __repr__(self) -> str:
        return (
            f"{type(self).__name__}(message={self.message!r}, status={self.status!r}, "
            f"code={self.code!r}, request_id={self.request_id!r})"
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": type(self).__name__,
            "message": self.message,
            "status": self.status,
            "code": self.code,
            "request_id": self.request_id,
            "field": self.field,
        }


class ConfigurationError(StampMitraError):
    """The client was constructed with missing or malformed configuration."""


class ValidationError(StampMitraError):
    """HTTP 400/422 from the API, or client-side input validation that failed.

    Client-side failures have ``status is None`` and are raised before any
    network call is made (so nothing is billed).
    """


class AuthenticationError(StampMitraError):
    """HTTP 401: missing, malformed or revoked API key."""


class PaymentRequiredError(StampMitraError):
    """HTTP 402: insufficient wallet balance or plan limit reached."""


class PermissionDeniedError(StampMitraError):
    """HTTP 403: key lacks the scope, or (for passport / driving licence) is not IP-allowlisted.

    The server message is surfaced verbatim in ``message``.
    """


class NotFoundError(StampMitraError):
    """HTTP 404."""


class ConflictError(StampMitraError):
    """HTTP 409, e.g. an Idempotency-Key reused with a different payload."""


class RateLimitError(StampMitraError):
    """HTTP 429. ``retry_after`` is the ``Retry-After`` header in seconds, if sent."""

    def __init__(self, message: str, *, retry_after: Optional[float] = None, **kwargs: Any) -> None:
        super().__init__(message, **kwargs)
        self.retry_after = retry_after


class UpstreamError(StampMitraError):
    """HTTP 5xx (502 etc.): StampMitra or an upstream data source failed."""


class APIConnectionError(StampMitraError):
    """The request never produced an HTTP response (DNS, TLS, refused, reset)."""


class APITimeoutError(APIConnectionError):
    """The request timed out."""


class WebhookSignatureError(StampMitraError):
    """Webhook signature missing, malformed, mismatched or stale."""
