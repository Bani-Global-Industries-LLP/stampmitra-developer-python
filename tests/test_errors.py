from __future__ import annotations

import httpx
import pytest
import respx

from stampmitra import (
    APIConnectionError,
    APITimeoutError,
    AuthenticationError,
    ConflictError,
    NotFoundError,
    PaymentRequiredError,
    PermissionDeniedError,
    RateLimitError,
    StampMitraError,
    UpstreamError,
    ValidationError,
)
from tests.conftest import BASE

CASES = [
    (400, ValidationError),
    (422, ValidationError),
    (401, AuthenticationError),
    (402, PaymentRequiredError),
    (403, PermissionDeniedError),
    (404, NotFoundError),
    (409, ConflictError),
    (429, RateLimitError),
    (500, UpstreamError),
    (502, UpstreamError),
    (503, UpstreamError),
    (418, StampMitraError),
]


@respx.mock
@pytest.mark.parametrize("status,cls", CASES)
def test_status_maps_to_typed_error(client, status, cls):
    body = {"error": {"code": "SOME_CODE", "message": "boom", "requestId": "rid-9", "field": "pan"}}
    # use a GET so retries (429/5xx) are exercised but exhausted quickly
    client._core.max_retries = 0
    respx.get(f"{BASE}/v1/services").mock(return_value=httpx.Response(status, json=body))
    with pytest.raises(cls) as ei:
        client.services.list()
    e = ei.value
    assert type(e) is cls
    assert (e.status, e.code, e.message, e.request_id, e.field, e.body) == (status, "SOME_CODE", "boom", "rid-9", "pan", body)
    assert "rid-9" in str(e)


@respx.mock
@pytest.mark.parametrize(
    "status,cls", [(502, UpstreamError), (404, NotFoundError), (401, AuthenticationError), (429, RateLimitError)]
)
def test_non_json_error_bodies_map_by_status(client, status, cls):
    client._core.max_retries = 0
    respx.get(f"{BASE}/v1/services").mock(
        return_value=httpx.Response(status, text="<html>Bad Gateway</html>", headers={"x-request-id": "hdr-id"})
    )
    with pytest.raises(cls) as ei:
        client.services.list()
    assert ei.value.request_id == "hdr-id" and "Bad Gateway" in ei.value.message


@respx.mock
def test_empty_error_body(client):
    respx.get(f"{BASE}/v1/services").mock(return_value=httpx.Response(404))
    with pytest.raises(NotFoundError) as ei:
        client.services.list()
    assert ei.value.message.startswith("HTTP 404")


@respx.mock
def test_403_message_verbatim(client):
    msg = "Passport verification requires an IP-allowlisted API key"
    respx.post(f"{BASE}/v1/verify/passport").mock(
        return_value=httpx.Response(403, json={"error": {"code": "FORBIDDEN", "message": msg, "requestId": "r"}})
    )
    with pytest.raises(PermissionDeniedError) as ei:
        client.verify.passport("PA1079341954215", "1990-01-01")
    assert ei.value.message == msg


@respx.mock
def test_rate_limit_retry_after_seconds(client):
    client._core.max_retries = 0
    respx.get(f"{BASE}/v1/services").mock(
        return_value=httpx.Response(
            429, json={"error": {"code": "TOO_MANY_REQUESTS", "message": "slow", "requestId": "r"}}, headers={"Retry-After": "7"}
        )
    )
    with pytest.raises(RateLimitError) as ei:
        client.services.list()
    assert ei.value.retry_after == 7.0


@respx.mock
def test_connection_and_timeout_errors(client):
    client._core.max_retries = 0
    respx.get(f"{BASE}/v1/services").mock(side_effect=httpx.ConnectError("refused"))
    with pytest.raises(APIConnectionError):
        client.services.list()
    respx.get(f"{BASE}/v1/services").mock(side_effect=httpx.ReadTimeout("slow"))
    with pytest.raises(APITimeoutError):
        client.services.list()


@respx.mock
async def test_async_error_mapping(aclient):
    respx.get(f"{BASE}/v1/orders/o1").mock(
        return_value=httpx.Response(404, json={"error": {"code": "NOT_FOUND", "message": "no", "requestId": "r"}})
    )
    with pytest.raises(NotFoundError):
        await aclient.orders.get("o1")
