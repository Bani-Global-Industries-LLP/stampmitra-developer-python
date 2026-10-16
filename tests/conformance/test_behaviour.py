"""Error mapping, retries, idempotency, timeouts, pagination against the mock server."""

from __future__ import annotations

import asyncio
import contextlib
import json
import re
import socket
from typing import Any, Dict, List

import httpx
import pytest

from stampmitra import (
    APIConnectionError,
    APITimeoutError,
    AsyncStampMitra,
    AuthenticationError,
    ConflictError,
    NotFoundError,
    PaymentRequiredError,
    PermissionDeniedError,
    RateLimitError,
    RequestOptions,
    StampMitra,
    StampMitraError,
    UpstreamError,
    ValidationError,
)
from stampmitra import _ops as ops
from tests.conformance.conftest import KEY

ERRORS = [
    (400, ValidationError),
    (401, AuthenticationError),
    (402, PaymentRequiredError),
    (403, PermissionDeniedError),
    (404, NotFoundError),
    (409, ConflictError),
    (429, RateLimitError),
    (500, UpstreamError),
    (502, UpstreamError),
    (503, UpstreamError),
    (504, UpstreamError),
]


def hdr(scenario: str) -> RequestOptions:
    return RequestOptions(headers={"x-mock-scenario": scenario}, max_retries=0)


@pytest.mark.parametrize(("status", "exc"), ERRORS)
def test_error_status_mapping_sync(client: Any, status: int, exc: type[StampMitraError]) -> None:
    with pytest.raises(exc) as ei:
        client.verify.pan("ABCDE1234F", options=hdr(f"error-{status}"))
    assert ei.value.status == status
    assert ei.value.request_id
    assert isinstance(ei.value, StampMitraError)
    assert KEY not in str(ei.value) and KEY not in repr(ei.value)


@pytest.mark.parametrize(("status", "exc"), ERRORS)
async def test_error_status_mapping_async(aclient: Any, status: int, exc: type[StampMitraError]) -> None:
    with pytest.raises(exc) as ei:
        await aclient.verify.pan("ABCDE1234F", options=hdr(f"error-{status}"))
    assert ei.value.status == status


def test_422_maps_to_validation_error(mock: Any) -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(422, json={"error": {"code": "UNPROCESSABLE", "message": "bad", "field": "pan"}})

    c = StampMitra(KEY, transport=httpx.MockTransport(handler))
    with pytest.raises(ValidationError) as ei:
        c.verify.pan("ABCDE1234F")
    assert ei.value.field == "pan"


def test_429_retry_after_with_and_without(client: Any, sleeps: Any) -> None:
    with pytest.raises(RateLimitError):
        client.verify.pan("ABCDE1234F", options=hdr("error-429"))
    with pytest.raises(RateLimitError) as ei:  # generic 429 carries Retry-After: 1
        client.services.list(options=hdr("error-429"))
    assert ei.value.retry_after == 1.0
    # GET 429 with Retry-After: 1 -> retried honouring it, then success (seq repeats the last item).
    client.services.list(options=RequestOptions(headers={"x-mock-scenario": "seq:ra:429,200"}))
    assert sleeps.values == [1.0]


def test_429_without_retry_after(mock: Any, sleeps: Any) -> None:
    calls: List[int] = []

    def handler(req: httpx.Request) -> httpx.Response:
        calls.append(1)
        return (
            httpx.Response(429, json={"error": {"code": "TOO_MANY_REQUESTS", "message": "slow"}})
            if len(calls) < 2
            else httpx.Response(200, json=[])
        )

    c = StampMitra(KEY, transport=httpx.MockTransport(handler))
    c._core.sleep = sleeps.sleep
    c._core.random = lambda: 1.0
    c.services.list()
    assert len(calls) == 2 and sleeps.values == [0.5]  # full-jitter window at attempt 0 with random()==1.0


def test_get_retry_sequence_503_503_200(client: Any, mock: Any, sleeps: Any) -> None:
    client.services.list(options=RequestOptions(headers={"x-mock-scenario": "seq:a:503,503,200"}))
    assert len(mock.requests()) == 3
    assert sleeps.values == [0.5, 1.0]


def test_get_retries_exhausted(client: Any, mock: Any) -> None:
    with pytest.raises(UpstreamError) as ei:
        client.services.list(options=RequestOptions(headers={"x-mock-scenario": "seq:b:503,503,503,200"}))
    assert ei.value.status == 503 and len(mock.requests()) == 3


@pytest.mark.parametrize("status", [400, 401, 403, 404])
def test_non_retryable_not_retried(client: Any, mock: Any, status: int) -> None:
    with pytest.raises(StampMitraError):
        client.services.list(options=RequestOptions(headers={"x-mock-scenario": f"seq:nr{status}:{status},200"}))
    assert len(mock.requests()) == 1


def test_verify_retried_with_same_key(client: Any, mock: Any, sleeps: Any) -> None:
    client.verify.pan("ABCDE1234F", options=RequestOptions(headers={"x-mock-scenario": "seq:v:503,503,200"}))
    reqs = mock.requests()
    keys = [r["headers"].get("idempotency-key") for r in reqs]
    assert len(reqs) == 3 and keys[0] and len(set(keys)) == 1
    assert sleeps.values == [0.5, 1.0]


async def test_async_verify_retried_with_same_key(aclient: Any, mock: Any) -> None:
    await aclient.verify.pan("ABCDE1234F", options=RequestOptions(headers={"x-mock-scenario": "seq:va:503,503,200"}))
    keys = [r["headers"].get("idempotency-key") for r in mock.requests()]
    assert len(keys) == 3 and keys[0] and len(set(keys)) == 1


def test_verify_caller_key_preserved(client: Any, mock: Any) -> None:
    client.verify.pan(
        "ABCDE1234F", options=RequestOptions(idempotency_key="my-key-1", headers={"x-mock-scenario": "seq:vk:503,200"})
    )
    assert [r["headers"]["idempotency-key"] for r in mock.requests()] == ["my-key-1", "my-key-1"]


def test_idempotency_key_reused_across_retries(client: Any, mock: Any) -> None:
    body = {"externalOrderId": "o1", "externalCustomerId": "c1", "serviceCode": "s", "details": {}}
    client.orders.create(body, options=RequestOptions(headers={"x-mock-scenario": "seq:o:503,502,201"}))
    keys = [r["headers"].get("idempotency-key") for r in mock.requests()]
    assert len(keys) == 3 and keys[0] and len(set(keys)) == 1
    mock.reset()
    client.orders.create(body, options=RequestOptions(idempotency_key="my-key-1", headers={"x-mock-scenario": "seq:o2:503,200"}))
    assert [r["headers"]["idempotency-key"] for r in mock.requests()] == ["my-key-1", "my-key-1"]
    # Two separate logical calls get different auto keys.
    mock.reset()
    client.orders.create(body)
    client.orders.create(body)
    k = [r["headers"]["idempotency-key"] for r in mock.requests()]
    assert k[0] != k[1]


def test_replay_never_keyed_or_retried(client: Any, mock: Any) -> None:
    with pytest.raises(UpstreamError):
        client.webhooks.events.replay("evt_1", options=RequestOptions(headers={"x-mock-scenario": "seq:rp:503,200"}))
    reqs = mock.requests()
    assert len(reqs) == 1 and "idempotency-key" not in reqs[0]["headers"]


def test_duty_calculate_keyed_and_retried(client: Any, mock: Any) -> None:
    client.estamp.calculate_duty({"a": 1}, options=RequestOptions(headers={"x-mock-scenario": "seq:du:503,200"}))
    keys = [r["headers"].get("idempotency-key") for r in mock.requests()]
    assert len(keys) == 2 and keys[0] and keys[0] == keys[1]


def test_connection_drop_get_retried(client: Any, mock: Any) -> None:
    client.orders.get_status("ord_1", options=RequestOptions(headers={"x-mock-scenario": "seq:cd:conn,200"}))
    assert len(mock.requests()) == 2


def test_connection_drop_verify_retried_with_same_key(client: Any, mock: Any) -> None:
    client.verify.pan("ABCDE1234F", options=RequestOptions(headers={"x-mock-scenario": "seq:cv:conn,200"}))
    keys = [r["headers"].get("idempotency-key") for r in mock.requests()]
    assert len(keys) == 2 and keys[0] and keys[0] == keys[1]


def test_connection_drop_replay_not_retried(client: Any, mock: Any) -> None:
    with pytest.raises(APIConnectionError):
        client.webhooks.events.replay("evt_1", options=RequestOptions(headers={"x-mock-scenario": "seq:cr:conn,200"}))
    assert len(mock.requests()) == 1


def test_timeout_sync(mock: Any) -> None:
    c = StampMitra(KEY, base_url=mock.url, max_retries=0, timeout=0.2)
    with pytest.raises(APITimeoutError):
        c.services.list(options=RequestOptions(headers={"x-mock-scenario": "delay:1500"}))
    c.close()


async def test_timeout_async(mock: Any) -> None:
    async with AsyncStampMitra(KEY, base_url=mock.url, max_retries=0, timeout=0.2) as c:
        with pytest.raises(APITimeoutError):
            await c.services.list(options=RequestOptions(headers={"x-mock-scenario": "delay:1500"}))


def test_timeout_get_retried_then_ok(mock: Any, sleeps: Any) -> None:
    c = StampMitra(KEY, base_url=mock.url, max_retries=1, timeout=5)
    c._core.sleep = sleeps.sleep
    state = {"n": 0}
    real = c._http.request

    def flaky(*a: Any, **k: Any) -> Any:
        state["n"] += 1
        if state["n"] == 1:
            raise httpx.ReadTimeout("boom")
        return real(*a, **k)

    c._http.request = flaky  # type: ignore[method-assign]
    assert c.services.list() is not None and state["n"] == 2
    c.close()


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def test_connection_refused() -> None:
    c = StampMitra(KEY, base_url=f"http://127.0.0.1:{_free_port()}", max_retries=1)
    c._core.sleep = lambda s: None
    with pytest.raises(APIConnectionError):
        c.services.list()
    with pytest.raises(APIConnectionError):
        c.verify.pan("ABCDE1234F")


async def test_connection_refused_async() -> None:
    async with AsyncStampMitra(KEY, base_url=f"http://127.0.0.1:{_free_port()}", max_retries=0) as c:
        with pytest.raises(APIConnectionError):
            await c.services.list()


@pytest.mark.parametrize(
    ("status", "body", "ctype", "exc"),
    [
        (500, "<html>oops</html>", "text/html", UpstreamError),
        (502, "Bad Gateway", "text/plain", UpstreamError),
        (404, "", "text/plain", NotFoundError),
        (403, "not json", "text/plain", PermissionDeniedError),
        (401, "{not-json", "application/json", AuthenticationError),
    ],
)
def test_non_json_error_body(status: int, body: str, ctype: str, exc: type[StampMitraError]) -> None:
    c = StampMitra(
        KEY,
        transport=httpx.MockTransport(lambda r: httpx.Response(status, text=body, headers={"content-type": ctype})),
        max_retries=0,
    )
    with pytest.raises(exc) as ei:
        c.usage.summary()
    assert ei.value.status == status and ei.value.message


def test_unknown_extra_response_fields_preserved() -> None:
    payload = {"referenceId": "r1", "valid": True, "brandNewField": {"a": 1}, "another": [1, 2]}
    c = StampMitra(KEY, transport=httpx.MockTransport(lambda r: httpx.Response(200, json=payload)))
    res = c.verify.pan("ABCDE1234F")
    assert res.valid is True and res.reference_id == "r1"
    assert res.model_extra is not None and res.model_extra["brandNewField"] == {"a": 1}
    assert res.to_dict()["another"] == [1, 2]


def test_logs_pagination_across_pages(mock: Any) -> None:
    seen: List[Dict[str, str]] = []

    def handler(req: httpx.Request) -> httpx.Response:
        q = dict(req.url.params)
        seen.append(q)
        cur = q.get("cursor")
        pages = {None: ("c1", ["a", "b"]), "c1": ("c2", ["c"]), "c2": (None, ["d", "e"])}
        nxt, ids = pages[cur]
        return httpx.Response(
            200,
            json={"items": [{"id": i, "createdAt": "t", "service": "pan.verify", "extra": 1} for i in ids], "nextCursor": nxt},
        )

    c = StampMitra(KEY, transport=httpx.MockTransport(handler))
    assert [e.id for e in c.logs.iter_all(limit=2, service="pan.verify")] == list("abcde")
    assert [q.get("cursor") for q in seen] == [None, "c1", "c2"]
    assert all(q["limit"] == "2" and q["service"] == "pan.verify" for q in seen)


async def test_logs_pagination_async() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        cur = req.url.params.get("cursor")
        if cur is None:
            return httpx.Response(200, json={"items": [{"id": "a"}], "nextCursor": "n"})
        return httpx.Response(200, json={"items": [{"id": "b"}], "nextCursor": None})

    async with AsyncStampMitra(KEY, transport=httpx.MockTransport(handler)) as c:
        assert [e.id async for e in c.logs.iter_all()] == ["a", "b"]


def test_logs_pagination_against_mock_single_page(client: Any, mock: Any) -> None:
    items = list(client.logs.iter_all(limit=50, from_="2026-10-01", to="2026-10-16", service="pan.verify", status="200"))
    assert len(items) >= 1
    q = mock.requests()[0]["query"]
    assert q["from"] == "2026-10-01" and q["to"] == "2026-10-16" and q["limit"] == "50"


async def test_async_concurrent_calls(mock: Any) -> None:
    async with AsyncStampMitra(KEY, base_url=mock.url) as c:
        results = await asyncio.gather(
            *[c.verify.pan("ABCDE1234F") for _ in range(25)],
            *[c.services.list() for _ in range(25)],
            *[c.orders.get(f"ord_{i}") for i in range(10)],
            *[c.usage.summary() for _ in range(10)],
        )
        assert len(results) == 70 and all(r is not None for r in results)
        # mixed failures do not poison siblings
        out = await asyncio.gather(
            c.verify.pan("ABCDE1234F", options=hdr("error-402")),
            c.services.list(),
            c.orders.get("x", options=hdr("error-404")),
            return_exceptions=True,
        )
        assert isinstance(out[0], PaymentRequiredError) and isinstance(out[2], NotFoundError) and isinstance(out[1], list)
    assert len(mock.requests()) == 73


async def test_async_cancellation(mock: Any) -> None:
    async with AsyncStampMitra(KEY, base_url=mock.url, max_retries=0) as c:
        task = asyncio.create_task(c.services.list(options=RequestOptions(headers={"x-mock-scenario": "delay:3000"})))
        await asyncio.sleep(0.2)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert (await c.usage.summary()) is not None


def test_redirect_not_followed(mock: Any) -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(302, headers={"location": "https://evil.example/steal"})

    c = StampMitra(KEY, transport=httpx.MockTransport(handler), max_retries=0)
    with pytest.raises(StampMitraError) as ei:
        c.usage.summary()
    assert ei.value.status == 302


def test_request_body_json_shape(client: Any, mock: Any) -> None:
    client.verify.pan(" abcde1234f ", name="Rahul")
    r = mock.requests()[0]
    assert r["body"] == {"pan": "ABCDE1234F", "name": "Rahul"}
    assert json.loads(json.dumps(r["body"]))


def test_path_params_encoded(mock: Any) -> None:
    seen: List[str] = []

    def handler(req: httpx.Request) -> httpx.Response:
        seen.append(req.url.raw_path.decode())
        return httpx.Response(200, json={})

    c = StampMitra(KEY, transport=httpx.MockTransport(handler))
    c.orders.get("a/b?c=d#e")
    assert seen == ["/v1/orders/a%2Fb%3Fc%3Dd%23e"]


def _fixture_scenarios(spec_dir: Any) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = json.loads((spec_dir / "fixtures" / "retry-scenarios.json").read_text())["scenarios"]
    return [s for s in out if not s.get("optional")]


def _expected_attempts(scn: Dict[str, Any], retry_safe: bool) -> int:
    """Attempts under the keyed-retry rule (the shared fixture encodes the older keyless-verify rule)."""
    max_retries = scn.get("maxRetries", 2)
    attempts = 0
    for item in scn["sequence"]:
        attempts += 1
        status = item["status"] if isinstance(item, dict) else item
        # un-keyed POST (webhook replay): only a failed connect is retried
        retryable = status in (429, 502, 503, 504, "connection_error", "timeout") if retry_safe else status == "connection_error"
        if not retryable or attempts > max_retries:
            break
    return attempts


def _find_op(method: str, path: str) -> Any:
    for op in vars(ops).values():
        if isinstance(op, ops.Op) and op.method == method:
            rx = re.sub(r"\\\{[^}]+\\\}", "[^/]+", re.escape(op.path))
            if re.fullmatch(rx, path):
                return op
    raise AssertionError(f"no op for {method} {path}")


def _path_params(template: str, path: str) -> Dict[str, str]:
    names = re.findall(r"\{([^}]+)\}", template)
    m = re.fullmatch(re.sub(r"\\\{[^}]+\\\}", "([^/]+)", re.escape(template)), path)
    return dict(zip(names, m.groups())) if m else {}


def test_retry_scenarios_fixture_under_keyed_rule(spec_dir: Any) -> None:
    """Drive every shared retry scenario; keyless verify/duty POSTs now follow the keyed-retry rule."""
    for scn in _fixture_scenarios(spec_dir):
        seq = list(scn["sequence"])
        calls: List[httpx.Request] = []

        def handler(req: httpx.Request, seq: List[Any] = seq, calls: List[httpx.Request] = calls) -> httpx.Response:
            item = seq[min(len(calls), len(seq) - 1)]
            calls.append(req)
            if item == "connection_error":
                raise httpx.ConnectError("refused", request=req)
            if item == "timeout":
                raise httpx.ReadTimeout("t", request=req)
            if isinstance(item, dict):
                return httpx.Response(item["status"], headers=item.get("headers"), json=item.get("body", {}))
            return httpx.Response(item, json={} if item < 400 else {"error": {"code": "X", "message": "m"}})

        op = _find_op(scn["method"], scn["path"])
        c = StampMitra(KEY, transport=httpx.MockTransport(handler), max_retries=scn.get("maxRetries", 2))
        c._core.sleep = lambda _s: None
        c._core.random = lambda: 0.0
        caller_key = scn["idempotencyKey"] is True
        opts = RequestOptions(idempotency_key="k-1") if caller_key else None
        with contextlib.suppress(StampMitraError):
            c._send(op, path_params=_path_params(op.path, scn["path"]), body={} if op.method == "POST" else None, options=opts)
        keyed = op.method == "POST" and (op.auto_idempotency or caller_key)
        assert len(calls) == _expected_attempts(scn, op.method == "GET" or keyed), scn["name"]
        if keyed:
            assert len({r.headers["idempotency-key"] for r in calls}) == 1, scn["name"]
        if op.method == "POST" and not keyed:
            assert all("idempotency-key" not in r.headers for r in calls), scn["name"]
        c.close()
