"""Transport-independent core shared by the sync and async clients.

Everything here is pure (no I/O) except the injectable ``sleep`` / ``random``
hooks and logging, so retry/backoff behaviour is unit-testable with a fake clock.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import platform
import random
import re
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Awaitable, Callable, Dict, Mapping, Optional, TypeVar
from urllib.parse import quote, urlencode

import httpx
from pydantic import ValidationError as PydanticValidationError

from ._ops import Op
from ._redact import redact_body, redact_headers
from ._version import __version__
from .errors import (
    APIConnectionError,
    APITimeoutError,
    AuthenticationError,
    ConfigurationError,
    ConflictError,
    NotFoundError,
    PaymentRequiredError,
    PermissionDeniedError,
    RateLimitError,
    StampMitraError,
    UpstreamError,
    ValidationError,
)
from .models import ApiObject, ResponseMeta, StampMitraModel

T = TypeVar("T", bound=StampMitraModel)

DEFAULT_BASE_URL = "https://api-b2b.stampmitra.in"
DEFAULT_TIMEOUT = 30.0
DEFAULT_MAX_RETRIES = 2
BACKOFF_BASE = 0.5
BACKOFF_CAP = 8.0
RETRY_AFTER_CAP = 60.0
RETRY_STATUSES = frozenset({429, 502, 503, 504})
API_KEY_RE = re.compile(r"^sk_(test|live)_[A-Za-z0-9_-]{8,}$")

_log = logging.getLogger("stampmitra")


@dataclass(frozen=True)
class RequestOptions:
    """Per-request overrides accepted by every SDK method (``options=``)."""

    timeout: Optional[float] = None
    max_retries: Optional[int] = None
    idempotency_key: Optional[str] = None
    headers: Optional[Mapping[str, str]] = None


@dataclass
class PreparedRequest:
    op: Op[Any]
    method: str
    url: str
    headers: Dict[str, str]
    content: Optional[bytes]
    timeout: float
    max_retries: int
    #: Safe to re-send automatically after a response: GET, or POST carrying an Idempotency-Key.
    retry_safe: bool
    body: Optional[Dict[str, Any]] = field(default=None, repr=False)


def _runtime() -> str:
    return f"python/{platform.python_version()}"


class Core:
    def __init__(
        self,
        *,
        api_key: Optional[str],
        base_url: Optional[str],
        timeout: float,
        max_retries: int,
        default_headers: Optional[Mapping[str, str]],
        app_info: Optional[Mapping[str, object]],
        logger: Optional[logging.Logger],
        debug: bool,
        validate_input: bool,
        allow_custom_key: bool,
    ) -> None:
        key = api_key if api_key is not None else os.environ.get("STAMPMITRA_API_KEY")
        if not key or not key.strip():
            raise ConfigurationError("No API key provided. Pass api_key=... or set the STAMPMITRA_API_KEY environment variable.")
        key = key.strip()
        if not allow_custom_key and not API_KEY_RE.match(key):
            raise ConfigurationError(
                "API key must look like sk_test_... or sk_live_... (pass allow_custom_key=True to bypass this check)."
            )
        if max_retries < 0:
            raise ConfigurationError("max_retries must be >= 0")
        if timeout <= 0:
            raise ConfigurationError("timeout must be > 0")
        self._api_key = key
        self.environment = "live" if key.startswith("sk_live_") else "test"
        self.base_url = (base_url or os.environ.get("STAMPMITRA_BASE_URL") or DEFAULT_BASE_URL).rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self.validate_input = validate_input
        self.logger: Optional[logging.Logger] = logger if logger is not None else (_log if debug else None)
        ua = f"stampmitra-python/{__version__} ({_runtime()})"
        if app_info:
            name = app_info.get("name")
            if name:
                ua += f" {name}"
                if app_info.get("version"):
                    ua += f"/{app_info.get('version')}"
                if app_info.get("url"):
                    ua += f" (+{app_info.get('url')})"
        self.user_agent = ua
        self.default_headers = dict(default_headers or {})
        # Injectable for tests (fake clock / deterministic jitter).
        self.sleep: Callable[[float], None] = time.sleep
        self.async_sleep: Callable[[float], Awaitable[None]] = asyncio.sleep
        self.random: Callable[[], float] = random.random

    def __repr__(self) -> str:  # never leak the key
        return f"<StampMitra environment={self.environment!r} base_url={self.base_url!r}>"

    # ---------------------------------------------------------------- request
    def prepare(
        self,
        op: Op[Any],
        *,
        path_params: Optional[Mapping[str, str]] = None,
        query: Optional[Mapping[str, Any]] = None,
        body: Optional[Dict[str, Any]] = None,
        options: Optional[RequestOptions] = None,
    ) -> PreparedRequest:
        options = options or RequestOptions()
        path = op.path
        for name, value in (path_params or {}).items():
            path = path.replace("{" + name + "}", quote(value, safe=""))
        url = self.base_url + path
        if query:
            qs = urlencode({k: str(val) for k, val in query.items() if val is not None})
            if qs:
                url += "?" + qs
        headers: Dict[str, str] = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": self.user_agent,
        }
        headers.update(self.default_headers)
        if options.headers:
            headers.update(options.headers)
        headers["Authorization"] = f"Bearer {self._api_key}"
        idem = options.idempotency_key
        if idem is None and op.auto_idempotency and not _has_header(headers, "Idempotency-Key"):
            idem = str(uuid.uuid4())  # generated once; reused across automatic retries
        if idem is not None and op.method != "GET":
            headers["Idempotency-Key"] = idem
        content = json.dumps(body, separators=(",", ":")).encode("utf-8") if body is not None else None
        has_key = _has_header(headers, "Idempotency-Key")
        return PreparedRequest(
            op=op,
            method=op.method,
            url=url,
            headers=headers,
            content=content,
            timeout=options.timeout if options.timeout is not None else self.timeout,
            max_retries=options.max_retries if options.max_retries is not None else self.max_retries,
            retry_safe=op.method == "GET" or has_key,
            body=body,
        )

    # ------------------------------------------------------------------ retry
    def backoff_delay(self, attempt: int, retry_after: Optional[float] = None) -> float:
        """Full-jitter exponential backoff; ``Retry-After`` (capped) wins when present."""
        if retry_after is not None:
            return min(max(retry_after, 0.0), RETRY_AFTER_CAP)
        return self.random() * min(BACKOFF_CAP, BACKOFF_BASE * float(2**attempt))

    def should_retry_status(self, prep: PreparedRequest, status: int, attempt: int) -> bool:
        return attempt < prep.max_retries and prep.retry_safe and status in RETRY_STATUSES

    def should_retry_exception(self, prep: PreparedRequest, exc: Exception, attempt: int) -> bool:
        if attempt >= prep.max_retries:
            return False
        if prep.retry_safe:
            return isinstance(exc, (httpx.TransportError,))
        # Billed, non-idempotent POST: only when the failure provably happened before the
        # request was sent (TCP connect failed / connect timed out).
        return isinstance(exc, (httpx.ConnectError, httpx.ConnectTimeout))

    @staticmethod
    def retry_after_seconds(response: httpx.Response) -> Optional[float]:
        raw = response.headers.get("retry-after")
        if raw is None:
            return None
        raw = raw.strip()
        try:
            return max(float(raw), 0.0)
        except ValueError:
            pass
        try:
            when = parsedate_to_datetime(raw)
            if when.tzinfo is None:
                when = when.replace(tzinfo=timezone.utc)
            return max((when - datetime.now(timezone.utc)).total_seconds(), 0.0)
        except (TypeError, ValueError):
            return None

    # ----------------------------------------------------------------- errors
    @staticmethod
    def wrap_exception(exc: Exception) -> StampMitraError:
        if isinstance(exc, httpx.TimeoutException):
            return APITimeoutError(f"Request timed out: {exc or type(exc).__name__}")
        return APIConnectionError(f"Connection error: {exc or type(exc).__name__}")

    def error_from_response(self, response: httpx.Response) -> StampMitraError:
        status = response.status_code
        request_id = response.headers.get("x-request-id")
        body: Any
        try:
            body = response.json()
        except ValueError:
            body = response.text
        code: Optional[str] = None
        field_name: Optional[str] = None
        message = ""
        if isinstance(body, dict):
            err = body.get("error")
            if isinstance(err, dict):
                code = _str(err.get("code"))
                message = _str(err.get("message")) or ""
                request_id = _str(err.get("requestId")) or request_id
                field_name = _str(err.get("field"))
            elif isinstance(err, str):
                message = err
            elif isinstance(body.get("message"), str):
                message = body["message"]
        elif isinstance(body, str) and body.strip():
            message = body.strip()[:300]
        if not message:
            message = f"HTTP {status}" + (f" {response.reason_phrase}" if response.reason_phrase else "")
        kwargs: Dict[str, Any] = {"status": status, "code": code, "request_id": request_id, "body": body, "field": field_name}
        if status in (400, 422):
            return ValidationError(message, **kwargs)
        if status == 401:
            return AuthenticationError(message, **kwargs)
        if status == 402:
            return PaymentRequiredError(message, **kwargs)
        if status == 403:
            return PermissionDeniedError(message, **kwargs)
        if status == 404:
            return NotFoundError(message, **kwargs)
        if status == 409:
            return ConflictError(message, **kwargs)
        if status == 429:
            return RateLimitError(message, retry_after=self.retry_after_seconds(response), **kwargs)
        if status >= 500:
            return UpstreamError(message, **kwargs)
        return StampMitraError(message, **kwargs)

    # --------------------------------------------------------------- response
    @staticmethod
    def parse_response(op: Op[T], response: httpx.Response) -> T:
        meta = ResponseMeta(
            response.status_code,
            dict(response.headers.items()),
            response.headers.get("x-request-id"),
            response.content,
        )
        data: Any
        try:
            data = response.json() if response.content else {}
        except ValueError:
            data = {"data": response.text}
        model_cls: Any = op.model
        if not isinstance(data, dict):
            model_cls, data = ApiObject, {"data": data}
        try:
            result: T = model_cls.model_validate(data)
        except PydanticValidationError:
            # Never fail on an unexpected value type: keep the data unvalidated.
            result = model_cls.model_construct(**data)
        result._response = meta
        return result

    # ---------------------------------------------------------------- logging
    def log_request(self, prep: PreparedRequest, attempt: int) -> None:
        if self.logger is None:
            return
        self.logger.debug(
            "stampmitra request %s %s attempt=%d headers=%s body=%s",
            prep.method,
            prep.url,
            attempt + 1,
            redact_headers(prep.headers),
            redact_body(prep.body) if prep.body is not None else None,
        )

    def log_response(self, prep: PreparedRequest, response: httpx.Response, elapsed: float) -> None:
        if self.logger is None:
            return
        try:
            body: Any = redact_body(response.json())
        except ValueError:
            body = "<non-JSON body omitted>"
        self.logger.debug(
            "stampmitra response %s %s status=%d elapsed=%.3fs request_id=%s headers=%s body=%s",
            prep.method,
            prep.url,
            response.status_code,
            elapsed,
            response.headers.get("x-request-id"),
            redact_headers(dict(response.headers)),
            body,
        )

    def log_retry(self, prep: PreparedRequest, reason: str, delay: float, attempt: int) -> None:
        if self.logger is not None:
            self.logger.debug(
                "stampmitra retry %s %s reason=%s delay=%.3fs next_attempt=%d", prep.method, prep.url, reason, delay, attempt + 2
            )


def _has_header(headers: Mapping[str, str], name: str) -> bool:
    return any(k.lower() == name.lower() for k in headers)


def _str(value: Any) -> Optional[str]:
    return value if isinstance(value, str) else None
