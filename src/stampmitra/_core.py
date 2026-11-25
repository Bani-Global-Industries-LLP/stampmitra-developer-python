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
from typing import Any, Awaitable, Callable, Dict, List, Mapping, Optional, Tuple, TypeVar, cast
from urllib.parse import quote, urlencode, urlsplit

import httpx
from pydantic import ValidationError as PydanticValidationError

from ._ops import FilePart, Op
from ._redact import redact_body, redact_headers
from ._version import __version__
from .errors import (
    APIConnectionError,
    APITimeoutError,
    AuthenticationError,
    ConfigurationError,
    ConflictError,
    FieldIssue,
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
    #: Safe to re-send automatically after a response: GET, or POST carrying an Idempotency-Key
    #: (every POST except webhook replay is auto-keyed; replay is keyed only if the caller supplies one).
    retry_safe: bool
    #: An Idempotency-Key header is present (auto-generated or caller-supplied).
    has_key: bool = False
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
        self.base_url = _validate_base_url((base_url or os.environ.get("STAMPMITRA_BASE_URL") or DEFAULT_BASE_URL).rstrip("/"))
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
        multipart: Optional[Multipart] = None,
        options: Optional[RequestOptions] = None,
    ) -> PreparedRequest:
        options = options or RequestOptions()
        path = op.path
        for name, value in (path_params or {}).items():
            path = path.replace("{" + name + "}", quote(value, safe=""))
        url = self.base_url + path
        if query:
            qs = urlencode({k: _query_value(val) for k, val in query.items() if val is not None})
            if qs:
                url += "?" + qs
        headers: Dict[str, str] = {
            "Accept": "application/json",
            "User-Agent": self.user_agent,
        }
        content: Optional[bytes] = None
        if multipart is not None:
            content, headers["Content-Type"] = encode_multipart(multipart.fields, multipart.files)
        elif body is not None:
            content = json.dumps(body, separators=(",", ":")).encode("utf-8")
            headers["Content-Type"] = "application/json"
        elif op.method != "GET":
            headers["Content-Type"] = "application/json"
        headers.update(self.default_headers)
        if options.headers:
            headers.update(options.headers)
        headers["Authorization"] = f"Bearer {self._api_key}"
        idem = options.idempotency_key
        if idem is None and op.auto_idempotency and not _has_header(headers, "Idempotency-Key"):
            idem = _new_idempotency_key()  # generated once; reused across automatic retries
        if idem is not None and op.method != "GET":
            headers["Idempotency-Key"] = idem
        has_key = _has_header(headers, "Idempotency-Key")
        return PreparedRequest(
            op=op,
            method=op.method,
            url=url,
            headers=headers,
            content=content,
            timeout=options.timeout if options.timeout is not None else self.timeout,
            max_retries=options.max_retries if options.max_retries is not None else self.max_retries,
            retry_safe=not op.never_retry and (op.method == "GET" or has_key or op.retry_without_key),
            has_key=has_key,
            body=body,
        )

    # ------------------------------------------------------------------ retry
    def backoff_delay(self, attempt: int, retry_after: Optional[float] = None) -> float:
        """Full-jitter exponential backoff; ``Retry-After`` (capped) wins when present."""
        if retry_after is not None:
            return min(max(retry_after, 0.0), RETRY_AFTER_CAP)
        return self.random() * min(BACKOFF_CAP, BACKOFF_BASE * float(2**attempt))

    def should_retry_status(
        self, prep: PreparedRequest, status: int, attempt: int, err: Optional[StampMitraError] = None
    ) -> bool:
        if attempt >= prep.max_retries or not prep.retry_safe:
            return False
        if status == 429:
            # SANDBOX_ESTAMP_ORDER_LIMIT is a quota (cancel or wait for open sandbox orders), not a rate limit.
            return err is None or err.code != "SANDBOX_ESTAMP_ORDER_LIMIT"
        if status == 409:
            # Only "the first request with this key is still running": resend the identical request after Retry-After.
            return prep.has_key and err is not None and err.code == "IDEMPOTENCY_IN_PROGRESS"
        return status in RETRY_STATUSES

    def should_retry_exception(self, prep: PreparedRequest, exc: Exception, attempt: int) -> bool:
        if attempt >= prep.max_retries or prep.op.never_retry:
            return False
        # Never retried (cancel, replace, PAN-card link, both top-ups, webhook replay): ``never_retry`` is handled above
        # and is not retry-safe, so a connection failure is surfaced, never re-sent.
        return prep.retry_safe and isinstance(exc, (httpx.TransportError,))

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
        details: Optional[Dict[str, Any]] = None
        issues: List[FieldIssue] = []
        wallet: Optional[str] = None
        message = ""
        if isinstance(body, dict):
            err = body.get("error")
            if isinstance(err, dict):
                code = _str(err.get("code"))
                message = _str(err.get("message")) or ""
                request_id = _str(err.get("requestId")) or request_id
                field_name = _str(err.get("field"))
                raw_details = err.get("details")
                if isinstance(raw_details, dict):
                    details = raw_details
                    wallet = _str(raw_details.get("wallet"))
                    raw_errors = raw_details.get("errors")
                    if isinstance(raw_errors, list):
                        issues = [_issue(e) for e in raw_errors if isinstance(e, dict)]
            elif isinstance(err, str):
                message = err
            elif isinstance(body.get("message"), str):
                message = body["message"]
        elif isinstance(body, str) and body.strip():
            message = body.strip()[:300]
        if not message:
            message = f"HTTP {status}" + (f" {response.reason_phrase}" if response.reason_phrase else "")
        kwargs: Dict[str, Any] = {
            "status": status,
            "code": code,
            "request_id": request_id,
            "body": body,
            "field": field_name,
            "details": details,
            "errors": issues,
            "wallet": wallet,
            "retry_after": self.retry_after_seconds(response),
        }
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
            return RateLimitError(message, **kwargs)
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

    def parse_list(self, op: Op[T], response: httpx.Response) -> List[T]:
        """Parse a JSON-array body (also tolerates ``{"<key>": [...]}`` / ``{"items": [...]}``)."""
        try:
            data: Any = response.json() if response.content else []
        except ValueError:
            data = []
        if isinstance(data, dict):
            data = next((v for v in data.values() if isinstance(v, list)), [])
        out: List[T] = []
        meta = ResponseMeta(
            response.status_code, dict(response.headers.items()), response.headers.get("x-request-id"), response.content
        )
        for row in data if isinstance(data, list) else []:
            try:
                item: T = op.model.model_validate(row)
            except PydanticValidationError:
                item = cast(T, op.model.model_construct(**row) if isinstance(row, dict) else op.model())
            item._response = meta
            out.append(item)
        return out

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


@dataclass(frozen=True)
class Multipart:
    """A ``multipart/form-data`` body: text ``fields`` (name, value) and ``files``."""

    fields: List[Tuple[str, str]]
    files: List[FilePart]


def encode_multipart(fields: List[Tuple[str, str]], files: List[FilePart]) -> Tuple[bytes, str]:
    """Encode a multipart/form-data body. Returns ``(body, content_type)``; the bytes are built once, so an automatic
    retry re-sends exactly the same body (and the same Idempotency-Key)."""
    boundary = "stampmitra-" + os.urandom(16).hex()

    def clean(v: str) -> str:
        return v.replace("\r", "").replace("\n", "").replace('"', "%22")

    out = bytearray()
    for f in files:
        out += (
            f'--{boundary}\r\nContent-Disposition: form-data; name="{clean(f.name)}"; filename="{clean(f.filename)}"\r\n'
            f"Content-Type: {clean(f.content_type)}\r\n\r\n"
        ).encode()
        out += f.data + b"\r\n"
    for name, value in fields:
        out += f'--{boundary}\r\nContent-Disposition: form-data; name="{clean(name)}"\r\n\r\n{value}\r\n'.encode()
    out += f"--{boundary}--\r\n".encode()
    return bytes(out), f"multipart/form-data; boundary={boundary}"


def _query_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float) and value.is_integer():
        return str(int(value))  # 500.0 -> "500"
    return str(value)


def _issue(e: Dict[str, Any]) -> FieldIssue:
    idx = e.get("index")
    return FieldIssue(
        code=_str(e.get("code")),
        message=_str(e.get("message")),
        field=_str(e.get("field")),
        index=idx if isinstance(idx, int) and not isinstance(idx, bool) else None,
    )


def _validate_base_url(url: str) -> str:
    """Require https (plain http only for localhost, e.g. a local mock server) so the bearer key is never sent in clear text."""
    parts = urlsplit(url)
    host = (parts.hostname or "").lower()
    if parts.scheme == "https" and host:
        return url
    if parts.scheme == "http" and host in ("localhost", "127.0.0.1", "::1"):
        return url
    raise ConfigurationError("base_url must be an https:// URL (http:// is only allowed for localhost).")


def _new_idempotency_key() -> str:
    """CSPRNG UUIDv4 (``uuid.uuid4`` reads ``os.urandom``); fail loudly rather than fall back to a weak RNG."""
    try:
        return str(uuid.UUID(bytes=os.urandom(16), version=4))
    except NotImplementedError as exc:  # pragma: no cover - os.urandom unavailable
        raise ConfigurationError("No cryptographically secure random source available to generate an Idempotency-Key.") from exc


def _has_header(headers: Mapping[str, str], name: str) -> bool:
    return any(k.lower() == name.lower() for k in headers)


def _str(value: Any) -> Optional[str]:
    return value if isinstance(value, str) else None
