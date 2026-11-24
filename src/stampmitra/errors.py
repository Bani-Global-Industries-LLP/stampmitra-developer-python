"""Typed exceptions raised by the SDK.

Every API failure maps to a subclass of :class:`StampMitraError` by HTTP status.
Transport problems raise :class:`APIConnectionError` / :class:`APITimeoutError`
(named to avoid shadowing the Python built-ins ``ConnectionError`` and
``TimeoutError``).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

__all__ = [
    "APIConnectionError",
    "APITimeoutError",
    "AuthenticationError",
    "ConfigurationError",
    "ConflictError",
    "FieldIssue",
    "NotFoundError",
    "PaymentRequiredError",
    "PermissionDeniedError",
    "RateLimitError",
    "StampMitraError",
    "UpstreamError",
    "ValidationError",
    "WebhookSignatureError",
]


@dataclass(frozen=True)
class FieldIssue:
    """One finding of a rejected request body (``error.details.errors[]``), e.g. on an e-Stamp order.

    ``field`` is the path of the offending input (``stamps[0].firstParty.name``), ``code`` a stable machine code
    (``REQUIRED``, ``MIXED_STATE``, ``INVALID_UNIT`` ...; branch on it), ``message`` human-readable text and
    ``index`` the zero-based stamp line when the finding is inside ``stamps[i]``.
    """

    code: Optional[str] = None
    message: Optional[str] = None
    field: Optional[str] = None
    index: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return {"field": self.field, "code": self.code, "message": self.message, "index": self.index}


class StampMitraError(Exception):
    """Base class for every error raised by this SDK.

    Beyond ``status`` / ``code`` / ``message`` / ``request_id`` / ``body`` / ``field`` it exposes the optional
    ``error.details`` of the API error envelope as typed attributes: ``errors`` (a list of :class:`FieldIssue`, empty
    when absent), ``wallet`` (``"STAMP_DUTY"`` or ``"SERVICE_FEE"`` on a 402 from an e-Stamp order) and the raw
    ``details`` mapping. ``retry_after`` is the ``Retry-After`` header in seconds when the response carried one.
    """

    def __init__(
        self,
        message: str,
        *,
        status: Optional[int] = None,
        code: Optional[str] = None,
        request_id: Optional[str] = None,
        body: Any = None,
        field: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        errors: Optional[List[FieldIssue]] = None,
        wallet: Optional[str] = None,
        retry_after: Optional[float] = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status = status
        self.code = code
        self.request_id = request_id
        #: The parsed JSON error body (or the raw text when it was not JSON).
        self.body = body
        self.field = field
        #: ``error.details`` as sent by the API (``None`` when absent).
        self.details = details
        #: ``error.details.errors[]`` of a rejected e-Stamp order body (empty when absent).
        self.errors: List[FieldIssue] = list(errors or [])
        #: ``error.details.wallet`` on a 402: ``"STAMP_DUTY"`` or ``"SERVICE_FEE"`` (``None`` when not known).
        self.wallet = wallet
        #: ``Retry-After`` response header in seconds, when sent.
        self.retry_after = retry_after

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
            "errors": [e.to_dict() for e in self.errors],
            "wallet": self.wallet,
            "retry_after": self.retry_after,
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
    """HTTP 409: a state conflict (e.g. cancelling an order that is no longer cancellable), or
    ``IDEMPOTENCY_IN_PROGRESS`` (the first request with this key is still running; ``retry_after`` is set)."""


class RateLimitError(StampMitraError):
    """HTTP 429. ``retry_after`` is the ``Retry-After`` header in seconds, if sent."""


class UpstreamError(StampMitraError):
    """HTTP 5xx (502 etc.): StampMitra or an upstream data source failed."""


class APIConnectionError(StampMitraError):
    """The request never produced an HTTP response (DNS, TLS, refused, reset)."""


class APITimeoutError(APIConnectionError):
    """The request timed out."""


class WebhookSignatureError(StampMitraError):
    """Webhook signature missing, malformed, mismatched or stale."""
