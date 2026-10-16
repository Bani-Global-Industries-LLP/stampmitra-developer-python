"""``StampMitra`` (sync) and ``AsyncStampMitra`` clients. Both share :class:`stampmitra._core.Core`."""

from __future__ import annotations

import logging
import time
from types import TracebackType
from typing import Any, Dict, Mapping, Optional, Type, TypedDict, TypeVar

import httpx

from . import _resources_async as ra
from . import _resources_sync as rs
from ._core import DEFAULT_MAX_RETRIES, DEFAULT_TIMEOUT, Core, PreparedRequest, RequestOptions
from ._ops import Op
from .errors import StampMitraError
from .models import StampMitraModel

T = TypeVar("T", bound=StampMitraModel)


class AppInfo(TypedDict, total=False):
    """Identify your application in the ``User-Agent`` header."""

    name: str
    version: str
    url: str


def _timeout(seconds: float) -> httpx.Timeout:
    return httpx.Timeout(seconds)


class StampMitra:
    """Synchronous client for the StampMitra Developer API.

    >>> client = StampMitra(api_key="sk_test_...")          # doctest: +SKIP
    >>> client.verify.pan("ABCDE1234F").valid               # doctest: +SKIP

    Server-side use only: never ship ``sk_`` keys in browsers or mobile apps.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        *,
        base_url: Optional[str] = None,
        timeout: float = DEFAULT_TIMEOUT,
        max_retries: int = DEFAULT_MAX_RETRIES,
        http_client: Optional[httpx.Client] = None,
        transport: Optional[httpx.BaseTransport] = None,
        default_headers: Optional[Mapping[str, str]] = None,
        app_info: Optional[AppInfo] = None,
        logger: Optional[logging.Logger] = None,
        debug: bool = False,
        validate_input: bool = True,
        allow_custom_key: bool = False,
    ) -> None:
        self._core = Core(
            api_key=api_key,
            base_url=base_url,
            timeout=timeout,
            max_retries=max_retries,
            default_headers=default_headers,
            app_info=app_info,
            logger=logger,
            debug=debug,
            validate_input=validate_input,
            allow_custom_key=allow_custom_key,
        )
        self._owns_http = http_client is None
        self._http = http_client or httpx.Client(transport=transport, follow_redirects=False)
        self.verify = rs.Verify(self)
        self.services = rs.Services(self)
        self.estamp = rs.Estamp(self)
        self.orders = rs.Orders(self)
        self.payments = rs.Payments(self)
        self.usage = rs.Usage(self)
        self.logs = rs.Logs(self)
        self.webhooks = rs.Webhooks(self)

    # -- public attributes ------------------------------------------------
    @property
    def environment(self) -> str:
        """``"test"`` or ``"live"``, derived from the key prefix."""
        return self._core.environment

    @property
    def base_url(self) -> str:
        return self._core.base_url

    @property
    def _v(self) -> bool:
        return self._core.validate_input

    def __repr__(self) -> str:
        return repr(self._core).replace("<StampMitra", "<StampMitra(sync)", 1)

    # -- lifecycle --------------------------------------------------------
    def close(self) -> None:
        if self._owns_http:
            self._http.close()

    def __enter__(self) -> StampMitra:
        return self

    def __exit__(
        self, exc_type: Optional[Type[BaseException]], exc: Optional[BaseException], tb: Optional[TracebackType]
    ) -> None:
        self.close()

    # -- transport --------------------------------------------------------
    def _call(
        self,
        op: Op[T],
        *,
        path_params: Optional[Mapping[str, str]] = None,
        query: Optional[Mapping[str, Any]] = None,
        body: Optional[Dict[str, Any]] = None,
        options: Optional[RequestOptions] = None,
    ) -> T:
        core = self._core
        prep: PreparedRequest = core.prepare(op, path_params=path_params, query=query, body=body, options=options)
        attempt = 0
        while True:
            core.log_request(prep, attempt)
            started = time.monotonic()
            try:
                response = self._http.request(
                    prep.method, prep.url, headers=prep.headers, content=prep.content, timeout=_timeout(prep.timeout)
                )
            except httpx.HTTPError as exc:
                if core.should_retry_exception(prep, exc, attempt):
                    delay = core.backoff_delay(attempt)
                    core.log_retry(prep, type(exc).__name__, delay, attempt)
                    core.sleep(delay)
                    attempt += 1
                    continue
                raise core.wrap_exception(exc) from exc
            core.log_response(prep, response, time.monotonic() - started)
            if response.status_code >= 400:
                err: StampMitraError = core.error_from_response(response)
                if core.should_retry_status(prep, response.status_code, attempt):
                    delay = core.backoff_delay(attempt, core.retry_after_seconds(response))
                    core.log_retry(prep, f"status {response.status_code}", delay, attempt)
                    core.sleep(delay)
                    attempt += 1
                    continue
                raise err
            return core.parse_response(op, response)


class AsyncStampMitra:
    """Asynchronous client (same API as :class:`StampMitra`; every method is a coroutine).

    Use ``async with AsyncStampMitra() as client:`` or call ``await client.aclose()``.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        *,
        base_url: Optional[str] = None,
        timeout: float = DEFAULT_TIMEOUT,
        max_retries: int = DEFAULT_MAX_RETRIES,
        http_client: Optional[httpx.AsyncClient] = None,
        transport: Optional[httpx.AsyncBaseTransport] = None,
        default_headers: Optional[Mapping[str, str]] = None,
        app_info: Optional[AppInfo] = None,
        logger: Optional[logging.Logger] = None,
        debug: bool = False,
        validate_input: bool = True,
        allow_custom_key: bool = False,
    ) -> None:
        self._core = Core(
            api_key=api_key,
            base_url=base_url,
            timeout=timeout,
            max_retries=max_retries,
            default_headers=default_headers,
            app_info=app_info,
            logger=logger,
            debug=debug,
            validate_input=validate_input,
            allow_custom_key=allow_custom_key,
        )
        self._owns_http = http_client is None
        self._http = http_client or httpx.AsyncClient(transport=transport, follow_redirects=False)
        self.verify = ra.Verify(self)
        self.services = ra.Services(self)
        self.estamp = ra.Estamp(self)
        self.orders = ra.Orders(self)
        self.payments = ra.Payments(self)
        self.usage = ra.Usage(self)
        self.logs = ra.Logs(self)
        self.webhooks = ra.Webhooks(self)

    @property
    def environment(self) -> str:
        return self._core.environment

    @property
    def base_url(self) -> str:
        return self._core.base_url

    @property
    def _v(self) -> bool:
        return self._core.validate_input

    def __repr__(self) -> str:
        return repr(self._core).replace("<StampMitra", "<AsyncStampMitra", 1)

    async def aclose(self) -> None:
        if self._owns_http:
            await self._http.aclose()

    async def __aenter__(self) -> AsyncStampMitra:
        return self

    async def __aexit__(
        self, exc_type: Optional[Type[BaseException]], exc: Optional[BaseException], tb: Optional[TracebackType]
    ) -> None:
        await self.aclose()

    async def _call(
        self,
        op: Op[T],
        *,
        path_params: Optional[Mapping[str, str]] = None,
        query: Optional[Mapping[str, Any]] = None,
        body: Optional[Dict[str, Any]] = None,
        options: Optional[RequestOptions] = None,
    ) -> T:
        core = self._core
        prep: PreparedRequest = core.prepare(op, path_params=path_params, query=query, body=body, options=options)
        attempt = 0
        while True:
            core.log_request(prep, attempt)
            started = time.monotonic()
            try:
                response = await self._http.request(
                    prep.method, prep.url, headers=prep.headers, content=prep.content, timeout=_timeout(prep.timeout)
                )
            except httpx.HTTPError as exc:
                if core.should_retry_exception(prep, exc, attempt):
                    delay = core.backoff_delay(attempt)
                    core.log_retry(prep, type(exc).__name__, delay, attempt)
                    await core.async_sleep(delay)
                    attempt += 1
                    continue
                raise core.wrap_exception(exc) from exc
            core.log_response(prep, response, time.monotonic() - started)
            if response.status_code >= 400:
                err: StampMitraError = core.error_from_response(response)
                if core.should_retry_status(prep, response.status_code, attempt):
                    delay = core.backoff_delay(attempt, core.retry_after_seconds(response))
                    core.log_retry(prep, f"status {response.status_code}", delay, attempt)
                    await core.async_sleep(delay)
                    attempt += 1
                    continue
                raise err
            return core.parse_response(op, response)
