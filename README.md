# stampmitra

[![CI](https://github.com/Bani-Global-Industries-LLP/stampmitra-developer-python/actions/workflows/ci.yml/badge.svg)](https://github.com/Bani-Global-Industries-LLP/stampmitra-developer-python/actions/workflows/ci.yml) [![PyPI](https://img.shields.io/pypi/v/stampmitra)](https://pypi.org/project/stampmitra/) [![Python](https://img.shields.io/pypi/pyversions/stampmitra)](https://pypi.org/project/stampmitra/) [![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE) ![typed](https://img.shields.io/badge/typing-strict-informational)

> The PyPI and Python-version badges show "not found" until the first release is published (see [RELEASING.md](RELEASING.md)).

Official Python SDK for the **StampMitra Developer API**: Indian identity and business verification (PAN, GSTIN, vehicle RC, Voter ID, Driving Licence, Passport, CIN, Udyam, bank account) and e-Stamp Paper orders. Sync and async clients, typed (`py.typed`, passes `mypy --strict`), `httpx` + `pydantic` v2 only.

> **Status: pre-1.0 (0.1.0).** Minor releases may contain breaking changes until 1.0; see the [CHANGELOG](CHANGELOG.md). Not yet published to PyPI until the maintainers configure publishing (see [RELEASING.md](RELEASING.md)).

Docs: <https://developer.stampmitra.in/docs> | Python SDK page: <https://developer.stampmitra.in/sdks/python> | OpenAPI: <https://developer.stampmitra.in/openapi.json>

## Install

```bash
pip install stampmitra
```

Supported: CPython 3.9, 3.10, 3.11, 3.12 and 3.13 (tested in CI). Runtime dependencies: `httpx>=0.27,<1`, `pydantic>=2.5,<3`.

## Quickstart

```python
from stampmitra import StampMitra

client = StampMitra()  # reads STAMPMITRA_API_KEY
result = client.verify.pan("ABCDE1234F", name="Rahul Kumar")
print(result.valid, result.registered_name, result.reference_id)
```

Async:

```python
import asyncio
from stampmitra import AsyncStampMitra


async def main() -> None:
    async with AsyncStampMitra() as client:
        print((await client.verify.gstin("07AAAAA1111A1Z1")).valid)


asyncio.run(main())
```

## Usage at a glance

| Resource | Methods |
| --- | --- |
| `client.verify` | `pan`, `gstin`, `rc`, `voter_id`, `driving_license`, `passport`, `cin`, `udyam`, `pan_to_gstin`, `pan_to_udyam`, `bank_account` |
| `client.services` | `list`, `get` |
| `client.estamp` | `get_schema`, `list_states`, `list_instruments`, `list_articles`, `calculate_duty`, `add_parties` |
| `client.orders` | `create`, `get`, `get_status`, `get_payment`, `list_documents`, `get_document_download` |
| `client.payments.intents` | `create`, `get` |
| `client.usage` | `summary` |
| `client.logs` | `list`, `iter_all` |
| `client.webhooks` | `events.list`, `events.iter_all`, `events.replay`, `verify_signature`, `construct_event` |

`AsyncStampMitra` has the same surface; every method is a coroutine and `iter_all` is an async iterator. All 31 API operations are covered.

## Authentication

Pass `api_key="sk_test_..."` or set `STAMPMITRA_API_KEY`. Sandbox keys are `sk_test_...` (free); production keys `sk_live_...` (metered). The constructor rejects keys that do not match `^sk_(test|live)_[A-Za-z0-9_-]{8,}$` unless you pass `allow_custom_key=True`. `client.environment` is `"test"` or `"live"`.

**Security: server-side only.** Never ship `sk_` keys in browsers, mobile apps or public repositories. Do not log keys; the SDK never logs by default and always redacts `Authorization` / `x-api-key`.

`base_url` must be `https://` (plain `http://` is accepted only for `localhost`, `127.0.0.1` and `::1`, e.g. a local mock server); the `STAMPMITRA_BASE_URL` environment variable is also honoured. Redirects are never followed.

Constructor options: `base_url`, `timeout` (30 s), `max_retries` (2), `http_client` / `transport` (your own `httpx` client or transport), `default_headers`, `app_info={"name","version","url"}`, `logger`, `debug`, `validate_input` (True), `allow_custom_key`.

Every method takes `options=RequestOptions(timeout=..., max_retries=..., idempotency_key=..., headers={...})` (`from stampmitra import RequestOptions`). Async cancellation uses normal `asyncio` task cancellation; for sync calls use `timeout`.

## Resources

All field names in JSON are camelCase; model attributes are snake_case (`registered_name`). Unknown fields are preserved (`model.model_extra`, `model.to_dict()`). Request bodies for e-Stamp/orders are passed as dicts exactly as the API documents them.

```python
# verify (every call is billed, including negative results; HTTP 200 with valid=False)
client.verify.pan("ABCDE1234F", name="Rahul Kumar")
client.verify.gstin("07AAAAA1111A1Z1", business_name="Acme")
client.verify.rc("MH12AB1234")
client.verify.voter_id("ABC1234567")
client.verify.driving_license("MH1420110012345", "1990-01-01")  # IP-allowlisted key
client.verify.passport("PA1079341954215", "1990-01-01")  # IP-allowlisted key
client.verify.cin("U74999DL2015PTC284009")
client.verify.udyam("UDYAM-MH-12-1234567")
client.verify.pan_to_gstin("ABCDE1234F")
client.verify.pan_to_udyam("ABCDE1234F")
client.verify.bank_account("000123456789", "ICIC0001234", name="Jane Doe")

# services and e-Stamp
client.services.list()
client.services.get("estamp.instrument.rent_agreement")
client.estamp.get_schema(code)
client.estamp.list_states()
client.estamp.list_instruments("MH")
client.estamp.list_articles(instrument_code)
client.estamp.calculate_duty({...})
client.estamp.add_parties(order_id, {...})

# orders and payments
order = client.orders.create({"externalOrderId": "o1", "externalCustomerId": "c1", "serviceCode": code, "details": {}})
client.orders.get(id)
client.orders.get_status(id)
client.orders.get_payment(id)
client.orders.list_documents(id)
client.orders.get_document_download(id, document_id)
client.payments.intents.create({...})
client.payments.intents.get(intent_id)

# usage, logs, webhook events
client.usage.summary()
client.logs.list(from_="2026-10-01", to="2026-10-16", service="pan.verify", status="200", limit=50)
client.webhooks.events.list(limit=20)
client.webhooks.events.replay(event_id)
```

Endpoints the spec leaves unconstrained (the proxied e-Stamp schema, states, instruments, articles, duty calculation, parties, webhook events and replay) return an `ApiObject` (all keys as attributes; a non-object body is wrapped as `.data`). Raw-response access: every returned model has `.response` with `status_code`, `headers`, `request_id` and `content`.

## Error handling

```python
from stampmitra import StampMitraError, ValidationError, RateLimitError, PermissionDeniedError

try:
    client.verify.pan("ABCDE1234F")
except ValidationError as e:  # 400 (or local validation, e.status is None)
    print(e.field, e.message)
except RateLimitError as e:  # 429
    print(e.retry_after)
except StampMitraError as e:  # base class: status, code, message, request_id, body
    print(e.status, e.code, e.request_id)
```

| HTTP | Exception |
| --- | --- |
| 400 / 422 | `ValidationError` (has `.field`) |
| 401 | `AuthenticationError` |
| 402 | `PaymentRequiredError` |
| 403 | `PermissionDeniedError` (server message verbatim, e.g. passport / driving licence need an IP-allowlisted key) |
| 404 | `NotFoundError` |
| 409 | `ConflictError` |
| 429 | `RateLimitError` (`.retry_after` seconds) |
| 5xx | `UpstreamError` |
| network / timeout | `APIConnectionError` / `APITimeoutError` |

Non-JSON error bodies still map by status. The API error body is `{"error": {"code", "message", "requestId", "field?"}}`.

## Retries and idempotency

Default `max_retries=2` with exponential backoff and full jitter (base 0.5 s, cap 8 s); `Retry-After` is honoured (capped at 60 s). Retried: 429, 502, 503, 504, connection errors and timeouts, for **GET** and for **POST requests that carry an `Idempotency-Key`**.

`orders.create`, `payments.intents.create` and `estamp.add_parties` auto-generate a UUIDv4 `Idempotency-Key` (reused across retries) unless you pass `options=RequestOptions(idempotency_key=...)`. **Verification calls are metered and have no idempotency key, so they are never retried after a response is received**; they are retried only when the TCP connection could not be established (nothing was sent).

## Pagination

```python
for entry in client.logs.iter_all(service="pan.verify", limit=100):  # follows nextCursor
    print(entry.id)

async for entry in async_client.logs.iter_all(limit=100):
    ...
```

`client.webhooks.events.iter_all()` works the same way (assumes the `items` / `nextCursor` shape, like `/v1/logs`).

## Webhooks

Deliveries carry `X-Webhook-Signature` (hex HMAC-SHA256 of `"<timestamp>.<raw body>"` with your endpoint secret), `X-Webhook-Timestamp` (Unix seconds) and `X-Webhook-Event-Id`. Verify against the **raw** request body:

```python
from stampmitra import webhooks, WebhookSignatureError

event = webhooks.construct_event(raw_body, headers["X-Webhook-Timestamp"], headers["X-Webhook-Signature"], secret)
# or webhooks.verify_signature(...) -> True, raising WebhookSignatureError (e.code in
# signature_mismatch | timestamp_outside_tolerance | invalid_timestamp | missing_secret)
```

Constant-time comparison; timestamps more than `tolerance_seconds` (default 300) from now are rejected. Also available as `client.webhooks.verify_signature` / `construct_event`. Examples: [`examples/flask_webhook.py`](examples/flask_webhook.py), [`examples/fastapi_webhook.py`](examples/fastapi_webhook.py).

## Client-side validation

Inputs are normalised (trimmed, upper-cased; bank account numbers trimmed only) and checked against the same patterns as the backend before sending; failures raise `ValidationError` locally with **no network call and no billing**. Disable with `StampMitra(validate_input=False)`.

## Logging

Off by default. `StampMitra(debug=True)` logs to the `stampmitra` logger (or pass `logger=`). Authorization / `x-api-key` are redacted and PAN, GSTIN, account numbers and names are masked in logged bodies.

## Security

Server-side use only: `sk_` keys are secrets (see above). The SDK requires `https://` base URLs, never disables TLS verification, does not follow redirects, never puts the key in exception messages or `repr()`, and verifies webhooks in constant time. Report vulnerabilities privately per [SECURITY.md](SECURITY.md) (security@stampmitra.in).

## Development and contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) (setup, lint, type-check, tests, conformance suite). Changes are listed in the [CHANGELOG](CHANGELOG.md). Please follow the [Code of Conduct](CODE_OF_CONDUCT.md).

## License

MIT, see [LICENSE](LICENSE).
