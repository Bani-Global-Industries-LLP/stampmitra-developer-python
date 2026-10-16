from __future__ import annotations

import json

import httpx
import pytest
import respx

from stampmitra import AsyncStampMitra, ConfigurationError, PanVerification, StampMitra, ValidationError
from tests.conftest import BASE, KEY

PAN_OK = {"referenceId": "SMV-1", "pan": "ABCDE1234F", "valid": True, "registeredName": "RAHUL KUMAR", "brandNewField": 7}


@respx.mock
def test_pan_success_models_aliases_and_extras(client):
    route = respx.post(f"{BASE}/v1/verify/pan").mock(
        return_value=httpx.Response(200, json=PAN_OK, headers={"x-request-id": "req-1"})
    )
    res = client.verify.pan(" abcde1234f ", name="Rahul Kumar")
    assert isinstance(res, PanVerification)
    assert res.reference_id == "SMV-1" and res.registered_name == "RAHUL KUMAR" and res.valid is True
    assert getattr(res, "brandNewField") == 7  # unknown field preserved  # noqa: B009
    assert res.model_extra == {"brandNewField": 7}
    assert res.to_dict()["referenceId"] == "SMV-1"
    assert res.response is not None
    assert res.response.status_code == 200 and res.response.request_id == "req-1"
    req = route.calls.last.request
    assert json.loads(req.content) == {"pan": "ABCDE1234F", "name": "Rahul Kumar"}  # normalised
    assert req.headers["authorization"] == f"Bearer {KEY}"
    assert req.headers["accept"] == "application/json" and req.headers["content-type"] == "application/json"
    assert req.headers["user-agent"].startswith("stampmitra-python/0.1.0 (python/")
    assert "idempotency-key" not in req.headers


@respx.mock
def test_negative_result_is_200_and_returned(client):
    respx.post(f"{BASE}/v1/verify/gstin").mock(
        return_value=httpx.Response(200, json={"referenceId": "x", "GSTIN": "07AAAAA1111A1Z1", "valid": False})
    )
    res = client.verify.gstin("07AAAAA1111A1Z1")
    assert res.valid is False and res.gstin == "07AAAAA1111A1Z1"


@respx.mock
def test_type_mismatch_does_not_fail(client):
    respx.post(f"{BASE}/v1/verify/voter-id").mock(return_value=httpx.Response(200, json={"age": "forty", "valid": True}))
    res = client.verify.voter_id("ABC1234567")
    assert res.valid is True


@respx.mock
def test_non_object_body_wrapped(client):
    respx.get(f"{BASE}/v1/estamp/states").mock(return_value=httpx.Response(200, json=[{"code": "MH"}]))
    assert client.estamp.list_states().data == [{"code": "MH"}]


@respx.mock
def test_path_params_are_quoted(client):
    route = respx.get(f"{BASE}/v1/services/a%2Fb").mock(return_value=httpx.Response(200, json={}))
    client.services.get("a/b")
    assert route.called


def test_environment_and_key_rules(monkeypatch):
    assert StampMitra(KEY).environment == "test"
    assert StampMitra("sk_live_abcdefgh12345678").environment == "live"
    with pytest.raises(ConfigurationError):
        StampMitra("not-a-key")
    assert StampMitra("custom", allow_custom_key=True).environment == "test"
    monkeypatch.delenv("STAMPMITRA_API_KEY", raising=False)
    with pytest.raises(ConfigurationError):
        StampMitra()
    monkeypatch.setenv("STAMPMITRA_API_KEY", KEY)
    assert StampMitra().environment == "test"
    assert KEY not in repr(StampMitra(KEY))


@respx.mock
def test_options_headers_timeout_app_info():
    route = respx.get(f"{BASE}/v1/usage/summary").mock(
        return_value=httpx.Response(200, json={"totalApiRequests": 3, "callsByService": {"pan.verify": 3}})
    )
    c = StampMitra(KEY, app_info={"name": "MyApp", "version": "2.0", "url": "https://x.example"}, default_headers={"X-A": "1"})
    from stampmitra import RequestOptions

    res = c.usage.summary(options=RequestOptions(headers={"X-B": "2"}, timeout=5))
    assert res.total_api_requests == 3 and res.calls_by_service == {"pan.verify": 3}
    h = route.calls.last.request.headers
    assert h["x-a"] == "1" and h["x-b"] == "2" and "MyApp/2.0 (+https://x.example)" in h["user-agent"]


@respx.mock
def test_x_api_key_not_needed_and_base_url_override():
    route = respx.get("https://sandbox.example/v1/services").mock(
        return_value=httpx.Response(200, json=[{"serviceCode": "estamp.x", "name": "X", "isActive": True, "entitled": True}])
    )
    res = StampMitra(KEY, base_url="https://sandbox.example/").services.list()
    assert route.called and res[0].service_code == "estamp.x"


VALID_CASES = [
    ("pan", ("ABCDE1234F",), {}),
    ("gstin", ("07AAAAA1111A1Z1",), {}),
    ("rc", ("MH12AB1234",), {}),
    ("voter_id", ("ABC1234567",), {}),
    ("driving_license", ("MH1420110012345", "1990-01-01"), {}),
    ("passport", ("PA1079341954215", "1990-01-01"), {}),
    ("cin", ("U74999DL2015PTC284009",), {}),
    ("udyam", ("UDYAM-MH-12-1234567",), {}),
    ("pan_to_gstin", ("ABCDE1234F",), {}),
    ("pan_to_udyam", ("ABCDE1234F",), {}),
    ("bank_account", ("000123456789", "ICIC0001234"), {"phone": "9876543210"}),
]
INVALID_CASES = [
    ("pan", ("ABCDE12345",), "pan"),
    ("pan", ("abcde1234",), "pan"),
    ("pan", (123,), "pan"),
    ("gstin", ("07AAAAA1111A1Y1",), "gstin"),
    ("rc", ("12AB1234",), "vehicleNumber"),
    ("voter_id", ("AB12345678",), "voterId"),
    ("driving_license", ("MH14", "1990-01-01"), "dlNumber"),
    ("driving_license", ("MH1420110012345", "01-01-1990"), "dob"),
    ("passport", ("PA123", "1990-01-01"), "fileNumber"),
    ("cin", ("X74999DL2015PTC284009",), "cin"),
    ("udyam", ("UDYAM-MH-12-123",), "udyamNumber"),
    ("pan_to_gstin", ("nope",), "pan"),
    ("pan_to_udyam", ("nope",), "pan"),
    ("bank_account", ("12345", "ICIC0001234"), "accountNumber"),
    ("bank_account", ("000123456789", "ICIC1001234"), "ifsc"),
    (
        "bank_account",
        (
            "000123456789",
            "ICIC0001234",
        ),
        "phone",
    ),
]


@respx.mock
@pytest.mark.parametrize("method,args,kwargs", VALID_CASES)
def test_valid_inputs_pass_validation(client, method, args, kwargs):
    route = respx.route(method="POST").mock(return_value=httpx.Response(200, json={"referenceId": "r"}))
    getattr(client.verify, method)(*args, **kwargs)
    assert route.call_count == 1


@respx.mock
@pytest.mark.parametrize("method,args,field", INVALID_CASES)
def test_invalid_inputs_fail_locally_without_network(client, method, args, field):
    route = respx.route().mock(return_value=httpx.Response(200, json={}))
    kwargs = {"phone": "123"} if (method, field) == ("bank_account", "phone") else {}
    with pytest.raises(ValidationError) as ei:
        getattr(client.verify, method)(*args, **kwargs)
    assert ei.value.field == field and ei.value.status is None
    assert route.call_count == 0


@respx.mock
def test_name_too_long_and_order_missing_fields(client):
    respx.route().mock(return_value=httpx.Response(200, json={}))
    with pytest.raises(ValidationError):
        client.verify.pan("ABCDE1234F", name="x" * 257)
    with pytest.raises(ValidationError) as ei:
        client.orders.create({"externalOrderId": "a"})
    assert ei.value.field == "externalCustomerId"


@respx.mock
def test_validation_can_be_disabled():
    route = respx.post(f"{BASE}/v1/verify/pan").mock(
        return_value=httpx.Response(400, json={"error": {"code": "BAD_REQUEST", "message": "pan must match", "requestId": "r"}})
    )
    c = StampMitra(KEY, validate_input=False)
    with pytest.raises(ValidationError) as ei:
        c.verify.pan("bad")
    assert ei.value.status == 400 and json.loads(route.calls.last.request.content) == {"pan": "bad"}


@respx.mock
async def test_async_client_basic(aclient):
    respx.post(f"{BASE}/v1/verify/pan").mock(return_value=httpx.Response(200, json=PAN_OK))
    res = await aclient.verify.pan("ABCDE1234F")
    assert res.valid is True
    with pytest.raises(ValidationError):
        await aclient.verify.pan("bad")


async def test_async_context_manager():
    async with AsyncStampMitra(KEY) as c:
        assert c.environment == "test"
    with StampMitra(KEY) as s:
        assert s.base_url == BASE


@pytest.mark.parametrize(
    "url", ["http://api-b2b.stampmitra.in", "ftp://x.example", "api-b2b.stampmitra.in", "https://", "http://localhost.evil.com"]
)
def test_base_url_must_be_https(url):
    with pytest.raises(ConfigurationError):
        StampMitra("sk_test_abcdefgh12345678", base_url=url)


@pytest.mark.parametrize(
    "url", ["https://api-b2b.stampmitra.in/", "http://localhost:4010", "http://127.0.0.1:1", "http://[::1]:8"]
)
def test_base_url_allowed(url):
    assert StampMitra("sk_test_abcdefgh12345678", base_url=url).base_url == url.rstrip("/")
