from __future__ import annotations

import httpx
import pytest
import respx

from stampmitra import APIConnectionError, RateLimitError, RequestOptions, UpstreamError
from tests.conftest import BASE

OK = httpx.Response(200, json=[])


@respx.mock
def test_get_retries_5xx_with_exponential_backoff(client, clock):
    route = respx.get(f"{BASE}/v1/services").mock(side_effect=[httpx.Response(502), httpx.Response(503), OK])
    assert client.services.list() == []
    assert route.call_count == 3
    assert clock.sleeps == [0.5, 1.0]  # random()==1 -> full window: base*2**attempt


@respx.mock
def test_backoff_is_capped_and_jittered(client, clock):
    client._core.random = lambda: 0.5
    respx.get(f"{BASE}/v1/services").mock(return_value=httpx.Response(503))
    with pytest.raises(UpstreamError):
        client.services.list(options=RequestOptions(max_retries=6))
    assert clock.sleeps == [0.25, 0.5, 1.0, 2.0, 4.0, 4.0]


@respx.mock
def test_retry_after_is_honoured(client, clock):
    respx.get(f"{BASE}/v1/services").mock(side_effect=[httpx.Response(429, headers={"Retry-After": "3"}), OK])
    client.services.list()
    assert clock.sleeps == [3.0]


@respx.mock
def test_exhausted_retries_raise_last_error(client, clock):
    route = respx.get(f"{BASE}/v1/services").mock(return_value=httpx.Response(429, headers={"Retry-After": "1"}))
    with pytest.raises(RateLimitError):
        client.services.list()
    assert route.call_count == 3 and len(clock.sleeps) == 2


@respx.mock
def test_get_retries_connection_errors(client, clock):
    route = respx.get(f"{BASE}/v1/services").mock(side_effect=[httpx.ReadTimeout("t"), httpx.ConnectError("c"), OK])
    client.services.list()
    assert route.call_count == 3


@respx.mock
def test_no_retry_on_400_401_404_for_get(client, clock):
    route = respx.get(f"{BASE}/v1/services").mock(return_value=httpx.Response(404))
    with pytest.raises(Exception):  # noqa: B017
        client.services.list()
    assert route.call_count == 1 and clock.sleeps == []


@respx.mock
@pytest.mark.parametrize("status", [429, 502, 503, 504])
def test_verification_post_is_retried_with_same_key(client, clock, status):
    route = respx.post(f"{BASE}/v1/verify/pan").mock(
        side_effect=[httpx.Response(status), httpx.Response(200, json={"referenceId": "r"})]
    )
    assert client.verify.pan("ABCDE1234F").reference_id == "r"
    keys = [c.request.headers["idempotency-key"] for c in route.calls]
    assert route.call_count == 2 and len(keys) == 2 and keys[0] == keys[1]


@respx.mock
def test_verification_post_503_503_200_three_attempts_same_key(client, clock):
    route = respx.post(f"{BASE}/v1/verify/pan").mock(
        side_effect=[httpx.Response(503), httpx.Response(503), httpx.Response(200, json={"referenceId": "r"})]
    )
    client.verify.pan("ABCDE1234F")
    keys = {c.request.headers["idempotency-key"] for c in route.calls}
    assert route.call_count == 3 and len(keys) == 1


@respx.mock
async def test_async_verification_post_503_503_200_three_attempts_same_key(aclient, clock):
    route = respx.post(f"{BASE}/v1/verify/pan").mock(
        side_effect=[httpx.Response(503), httpx.Response(503), httpx.Response(200, json={"referenceId": "r"})]
    )
    await aclient.verify.pan("ABCDE1234F")
    keys = {c.request.headers["idempotency-key"] for c in route.calls}
    assert route.call_count == 3 and len(keys) == 1


@respx.mock
def test_verification_post_retried_on_ambiguous_transport_error_with_same_key(client, clock):
    route = respx.post(f"{BASE}/v1/verify/pan").mock(side_effect=[httpx.ReadTimeout("t"), httpx.Response(200, json={})])
    client.verify.pan("ABCDE1234F")
    assert route.call_count == 2
    assert len({c.request.headers["idempotency-key"] for c in route.calls}) == 1


@respx.mock
def test_verification_post_not_retried_on_4xx(client, clock):
    route = respx.post(f"{BASE}/v1/verify/pan").mock(return_value=httpx.Response(400))
    with pytest.raises(Exception):  # noqa: B017
        client.verify.pan("ABCDE1234F")
    assert route.call_count == 1


@respx.mock
def test_caller_key_preserved_across_verification_retries(client, clock):
    route = respx.post(f"{BASE}/v1/verify/gstin").mock(side_effect=[httpx.Response(503), httpx.Response(200, json={})])
    client.verify.gstin("07AAAAA1111A1Z1", options=RequestOptions(idempotency_key="caller-key"))
    assert [c.request.headers["idempotency-key"] for c in route.calls] == ["caller-key", "caller-key"]


@respx.mock
def test_duty_calculate_is_auto_keyed_and_retried(client, clock):
    route = respx.post(f"{BASE}/v1/estamp/duty/calculate").mock(side_effect=[httpx.Response(503), httpx.Response(200, json={})])
    client.estamp.calculate_duty({"a": 1})
    assert route.call_count == 2 and len({c.request.headers["idempotency-key"] for c in route.calls}) == 1


@respx.mock
def test_replay_is_never_auto_keyed_or_retried(client, clock):
    route = respx.post(f"{BASE}/v1/webhooks/events/evt_1/replay").mock(
        side_effect=[httpx.Response(503), httpx.Response(200, json={})]
    )
    with pytest.raises(UpstreamError):
        client.webhooks.events.replay("evt_1")
    assert route.call_count == 1 and "idempotency-key" not in route.calls.last.request.headers


@respx.mock
def test_replay_retried_only_on_connect_failure(client, clock):
    route = respx.post(f"{BASE}/v1/webhooks/events/evt_1/replay").mock(
        side_effect=[httpx.ReadTimeout("t"), httpx.Response(200, json={})]
    )
    with pytest.raises(Exception):  # noqa: B017
        client.webhooks.events.replay("evt_1")
    assert route.call_count == 1


@respx.mock
async def test_async_replay_never_auto_keyed_or_retried(aclient, clock):
    route = respx.post(f"{BASE}/v1/webhooks/events/evt_1/replay").mock(return_value=httpx.Response(503))
    with pytest.raises(UpstreamError):
        await aclient.webhooks.events.replay("evt_1")
    assert route.call_count == 1 and "idempotency-key" not in route.calls.last.request.headers


@respx.mock
def test_verification_connect_failure_retried_with_same_key(client, clock):
    route = respx.post(f"{BASE}/v1/verify/pan").mock(
        side_effect=[httpx.ConnectError("refused"), httpx.Response(200, json={"referenceId": "r"})]
    )
    assert client.verify.pan("ABCDE1234F").reference_id == "r"
    assert route.call_count == 2
    keys = {c.request.headers.get("idempotency-key") for c in route.calls}
    assert len(keys) == 1 and None not in keys


@respx.mock
def test_connect_failure_exhausts_into_connection_error(client, clock):
    respx.post(f"{BASE}/v1/verify/pan").mock(side_effect=httpx.ConnectError("refused"))
    with pytest.raises(APIConnectionError):
        client.verify.pan("ABCDE1234F")


ORDER = {"externalOrderId": "o", "externalCustomerId": "c", "serviceCode": "estamp.x"}


@respx.mock
def test_idempotency_key_generated_and_reused_across_retries(client, clock):
    route = respx.post(f"{BASE}/v1/orders").mock(
        side_effect=[httpx.Response(503), httpx.Response(502), httpx.Response(200, json={"id": "ord_1"})]
    )
    res = client.orders.create(ORDER)
    assert res.id == "ord_1" and route.call_count == 3
    keys = [c.request.headers["idempotency-key"] for c in route.calls]
    assert len(set(keys)) == 1 and len(keys[0]) == 36  # one UUIDv4 reused
    # a second call gets a fresh key
    route.side_effect = [httpx.Response(200, json={})]
    client.orders.create(ORDER)
    assert route.calls.last.request.headers["idempotency-key"] != keys[0]


@respx.mock
def test_caller_supplied_idempotency_key_is_used(client):
    route = respx.post(f"{BASE}/v1/payments/intents").mock(return_value=httpx.Response(200, json={}))
    client.payments.intents.create({"orderId": "o"}, options=RequestOptions(idempotency_key="my-key-1"))
    assert route.calls.last.request.headers["idempotency-key"] == "my-key-1"


@respx.mock
def test_parties_has_idempotency_key_and_orders_get_has_none(client):
    p = respx.post(f"{BASE}/v1/estamp/orders/o1/parties").mock(return_value=httpx.Response(200, json={}))
    g = respx.get(f"{BASE}/v1/orders/o1").mock(return_value=httpx.Response(200, json={}))
    client.estamp.add_parties("o1", {"parties": []})
    client.orders.get("o1")
    assert "idempotency-key" in p.calls.last.request.headers
    assert "idempotency-key" not in g.calls.last.request.headers


@respx.mock
def test_max_retries_zero_and_per_request_override(client, clock):
    route = respx.get(f"{BASE}/v1/services").mock(return_value=httpx.Response(503))
    with pytest.raises(UpstreamError):
        client.services.list(options=RequestOptions(max_retries=0))
    assert route.call_count == 1


@respx.mock
async def test_async_retry_and_idempotency(aclient, clock):
    route = respx.post(f"{BASE}/v1/orders").mock(side_effect=[httpx.Response(503), httpx.Response(200, json={"id": "a"})])
    res = await aclient.orders.create(ORDER)
    assert res.id == "a" and clock.sleeps == [0.5]
    assert len({c.request.headers["idempotency-key"] for c in route.calls}) == 1
