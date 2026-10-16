"""Behaviour verified against the real backend: 201 on POSTs, no Retry-After / X-Request-Id, bare-array services."""

from __future__ import annotations

import httpx
import pytest
import respx

from stampmitra import AuthenticationError, RateLimitError, Service
from tests.conftest import BASE


@respx.mock
def test_any_2xx_is_success_201_for_post(client):
    respx.post(f"{BASE}/v1/orders").mock(
        return_value=httpx.Response(201, json={"externalOrderId": "o1", "createdAt": "t", "serviceCode": "s"})
    )
    respx.post(f"{BASE}/v1/verify/pan").mock(return_value=httpx.Response(201, json={"referenceId": "r", "valid": True}))
    respx.get(f"{BASE}/v1/orders/o1/status").mock(
        return_value=httpx.Response(202, json={"externalOrderId": "o1", "status": {"x": 1}})
    )
    ref = client.orders.create({"externalOrderId": "o1", "externalCustomerId": "c", "serviceCode": "s"})
    assert ref.external_order_id == "o1" and ref.response.status_code == 201
    assert client.verify.pan("ABCDE1234F").valid is True
    assert client.orders.get_status("o1").status == {"x": 1}


@respx.mock
def test_services_list_is_a_list_of_models(client):
    respx.get(f"{BASE}/v1/services").mock(
        return_value=httpx.Response(
            200, json=[{"serviceCode": "estamp.a", "name": "A", "isActive": True, "uiSchema": {"fields": []}, "extra": 1}]
        )
    )
    out = client.services.list()
    assert isinstance(out, list) and isinstance(out[0], Service)
    assert out[0].service_code == "estamp.a" and out[0].is_active is True and out[0].ui_schema == {"fields": []}


@respx.mock
def test_request_id_comes_from_error_body_without_headers(client):
    respx.get(f"{BASE}/v1/usage/summary").mock(
        return_value=httpx.Response(
            401, json={"error": {"code": "UNAUTHORIZED", "message": "missing scope", "requestId": "body-rid"}}
        )
    )
    with pytest.raises(AuthenticationError) as ei:
        client.usage.summary()
    assert ei.value.request_id == "body-rid"


@respx.mock
def test_429_without_retry_after_uses_jittered_backoff(client, clock):
    route = respx.get(f"{BASE}/v1/logs").mock(
        side_effect=[
            httpx.Response(429, json={"error": {"code": "X", "message": "m", "requestId": "r"}}),
            httpx.Response(200, json={"items": [], "nextCursor": None}),
        ]
    )
    client.logs.list()
    assert route.call_count == 2 and clock.sleeps == [0.5]
    route.side_effect = [httpx.Response(429)] * 3
    with pytest.raises(RateLimitError) as ei:
        client.logs.list()
    assert ei.value.retry_after is None


@respx.mock
def test_typed_usage_and_bank_models(client):
    respx.get(f"{BASE}/v1/usage/summary").mock(
        return_value=httpx.Response(
            200,
            json={
                "currentPeriod": {"start": "a", "end": "b"},
                "totalApiRequests": 2,
                "callsByService": {"pan.verify": 2},
                "callsByPeriod": [{"period": "p", "count": 2}],
                "callsByDay": [{"day": "d", "count": 2}],
            },
        )
    )
    u = client.usage.summary()
    assert u.current_period.start == "a" and u.calls_by_day[0].count == 2
    respx.post(f"{BASE}/v1/verify/bank-account").mock(
        return_value=httpx.Response(
            200, json={"referenceId": "r", "valid": True, "nameAtBank": "X", "ifscDetails": {"bank": "ICICI", "swiftCode": "S"}}
        )
    )
    b = client.verify.bank_account("000123456789", "ICIC0001234")
    assert b.name_at_bank == "X" and b.ifsc_details.swift_code == "S"
