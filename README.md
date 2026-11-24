# stampmitra

[![CI](https://github.com/Bani-Global-Industries-LLP/stampmitra-developer-python/actions/workflows/ci.yml/badge.svg)](https://github.com/Bani-Global-Industries-LLP/stampmitra-developer-python/actions/workflows/ci.yml) [![PyPI](https://img.shields.io/pypi/v/stampmitra)](https://pypi.org/project/stampmitra/) [![Python](https://img.shields.io/pypi/pyversions/stampmitra)](https://pypi.org/project/stampmitra/) [![License: MIT](https://img.shields.io/badge/license-MIT-green)](https://github.com/Bani-Global-Industries-LLP/stampmitra-developer-python/blob/main/LICENSE) ![typed](https://img.shields.io/badge/typing-strict-informational)

> The PyPI and Python-version badges show "not found" until the first release is published (see [RELEASING.md](https://github.com/Bani-Global-Industries-LLP/stampmitra-developer-python/blob/main/RELEASING.md)).

Official Python SDK for the **StampMitra Developer API**: Indian identity and business verification (PAN, GSTIN, vehicle RC, Voter ID, Driving Licence, Passport, CIN, Udyam, bank account) and e-Stamp Paper orders and wallets. Sync and async clients, typed (`py.typed`, passes `mypy --strict`), `httpx` + `pydantic` v2 only.

> **Status: pre-1.0 (0.2.0).** Minor releases may contain breaking changes until 1.0; see the [CHANGELOG](https://github.com/Bani-Global-Industries-LLP/stampmitra-developer-python/blob/main/CHANGELOG.md). Not yet published to PyPI until the maintainers configure publishing (see [RELEASING.md](https://github.com/Bani-Global-Industries-LLP/stampmitra-developer-python/blob/main/RELEASING.md)).

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
| `client.estamp` | `get_schema`, `list_states`, `list_instruments`, `list_articles`, `calculate_duty`, `add_parties`, `get_states_availability`, `get_state`, `get_state_requirements`, `list_districts`, `list_sros`, `get_wallet` |
| `client.estamp.orders` | `validate`, `create`, `list`, `iter_all`, `get`, `cancel`, `export`, `list_stamps`, `upload_document` |
| `client.estamp.stamps` | `get`, `cancel`, `replace`, `set_pan_card`, `get_certificate` |
| `client.stamp_duty_wallet`, `client.service_fee_wallet` | `get_balance`, `topup`, `list_transactions`, `iter_transactions`, `list_invoices`, `iter_invoices`, `get_invoice` |
| `client.account` | `balance`, `usage` |
| `client.orders` | `create`, `get`, `get_status`, `get_payment`, `list_documents`, `get_document_download` |
| `client.payments.intents` | `create`, `get` |
| `client.usage` | `summary` |
| `client.logs` | `list`, `iter_all` |
| `client.webhooks` | `events.list`, `events.iter_all`, `events.replay`, `verify_signature`, `construct_event` |

`AsyncStampMitra` has the same surface; every method is a coroutine and `iter_all` is an async iterator. All 62 API operations of contract 1.2.0 are covered.

## e-Stamp orders

One order covers exactly one state (up to 5000 stamp lines, `quantity` up to 1000 per line). The flow is validate, create, upload the PAN card, list stamps, fetch the certificate (full script: [`examples/estamp_order.py`](https://github.com/Bani-Global-Industries-LLP/stampmitra-developer-python/blob/main/examples/estamp_order.py)):

```python
from stampmitra import PaymentRequiredError, RequestOptions, StampMitra

order = {
    "reference": "order-2026-0917",
    "stamps": [
        {
            "state": "MH",
            "articleCode": "ART1",  # from client.estamp.list_instruments("MH")
            "denomination": 1000,
            "firstParty": {"name": "Jane Doe", "address": "12 MG Road, Pune"},  # object ...
            "secondParty": "John Smith",  # ... or a bare name string
            "purpose": "Rental Agreement",
        }
    ],
}

with StampMitra() as client:
    check = client.estamp.orders.validate(order)  # dry run: nothing created, not billed
    assert check.valid, [e.message for e in check.errors]

    try:  # the API requires an Idempotency-Key: pass your own (stable per logical order) or let the SDK generate one
        created = client.estamp.orders.create(order, options=RequestOptions(idempotency_key="lease-2026-0412-v1"))
    except PaymentRequiredError as e:
        raise SystemExit(f"top up the {e.wallet} wallet")  # e.wallet is "STAMP_DUTY" or "SERVICE_FEE"

    client.estamp.orders.upload_document(created.id, "pan-card.pdf")  # multipart: PDF, JPEG or PNG, up to 10 MB
    for stamp in client.estamp.orders.list_stamps(created.id).items:
        cert = client.estamp.stamps.get_certificate(stamp.id)
        print(stamp.id, stamp.status, cert.download_url if cert.available else "not issued yet")
```

- **Parties.** `firstParty` / `secondParty` is a name string or an object `{name, address, phone, fatherHusbandName, gender}` (`gender` is `MALE`, `FEMALE` or `OTHER`); use the object when the state asks for an address or a father's / husband's name (`client.estamp.get_state_requirements("MH", article_code="ART1")` tells you, and its `example_body` is a ready-to-edit order). `propertyArea` is `{"unit": "Square Feet" | "Square Yard" | "Square Meters" | "Not Applicable", "value": 850}`. Typed dict shapes: `EstampOrderRequest`, `EstampStampLine`, `EstampParty`, `EstampPropertyArea`.
- **PAN card is advisory.** It is recommended for the stamp-duty payer but never blocks an order. Send it per order with `orders.upload_document(order_id, file)` (a path, bytes or a binary file object; multipart part `file`, optional part `type` = `pan_card`), or link it per stamp with `stamps.set_pan_card(stamp_id, "https://...")` (HTTP 202; checked afterwards, read `stamps.get(...).pan_card.status`).
- **Errors.** A rejected order body raises `ValidationError` with `e.errors`, a list of `FieldIssue(field, code, message, index)`; a short wallet raises `PaymentRequiredError` with `e.wallet`. `create` checks the contract's hard limits locally first (no network call, nothing billed); `validate` leaves the findings to the API.
- **Retries.** `create` and `upload_document` are keyed and retried on 429/502/503/504, connection errors and `409 IDEMPOTENCY_IN_PROGRESS` (honouring `Retry-After`) with the same key and body; `validate` and all reads are retried too. Order cancel, stamp cancel, stamp replace, PAN-card link, both wallet top-ups and webhook replay are **never** retried automatically.

### Wallets

An order draws on two wallets: the **Stamp Duty** wallet (the duty paid to the state) and the **Service Fee** wallet. Read both with `client.estamp.get_wallet()`, or each with `client.stamp_duty_wallet` / `client.service_fee_wallet` (`get_balance`, `topup`, `list_transactions`, `list_invoices`, `get_invoice`).

- **Stamp Duty top-up** (`client.stamp_duty_wallet.topup(1000)`): a 6% processing fee plus 18% GST on that fee is charged on top, and the wallet is credited the amount you add (here 1000). A GST tax invoice for the fee is available from `list_invoices()` / `get_invoice(id)`. The SDK computes nothing: show the payer `base_amount`, `processing_fee_amount`, `gst_amount`, `total_charged` and `credit_amount` from the response (the rates can change). `base_amount`, `gst_amount` and `total_charged` are numbers; the other amounts are strings; `topup_id` (the invoice id) is only returned for live keys.
- **Service Fee top-up**: GST is added on `base_amount`; every amount in the response is a string.

See [`examples/estamp_wallets.py`](https://github.com/Bani-Global-Industries-LLP/stampmitra-developer-python/blob/main/examples/estamp_wallets.py).

## Authentication

Pass `api_key="sk_test_..."` or set `STAMPMITRA_API_KEY`. Sandbox keys are `sk_test_...` (free); production keys `sk_live_...` (metered). The constructor rejects keys that do not match `^sk_(test|live)_[A-Za-z0-9_-]{8,}$` unless you pass `allow_custom_key=True`. `client.environment` is `"test"` or `"live"`.

**Security: server-side only.** Never ship `sk_` keys in browsers, mobile apps or public repositories. Do not log keys; the SDK never logs by default and always redacts `Authorization` / `x-api-key`.

`base_url` must be `https://` (plain `http://` is accepted only for `localhost`, `127.0.0.1` and `::1`, e.g. a local mock server); the `STAMPMITRA_BASE_URL` environment variable is also honoured. Redirects are never followed.

Constructor options: `base_url`, `timeout` (30 s), `max_retries` (2), `http_client` / `transport` (your own `httpx` client or transport), `default_headers`, `app_info={"name","version","url"}`, `logger`, `debug`, `validate_input` (True), `allow_custom_key`.

Every method takes `options=RequestOptions(timeout=..., max_retries=..., idempotency_key=..., headers={...})` (`from stampmitra import RequestOptions`). Async cancellation uses normal `asyncio` task cancellation; for sync calls use `timeout`.

## Resources

All field names in JSON are camelCase; model attributes are snake_case (`registered_name`). Unknown fields are preserved (`model.model_extra`, `model.to_dict()`). Request bodies for e-Stamp/orders are passed as dicts exactly as the API documents them (the e-Stamp order bodies also have `TypedDict` shapes, see `stampmitra.params`).

```python
# verify (every call is billed, including negative results; HTTP 200 with valid=False;
# auto-keyed with an Idempotency-Key and safely retried on 429/502/503/504)
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

# e-Stamp orders, stamps, wallets, account (see "e-Stamp orders" above)
client.estamp.orders.validate(body)
client.estamp.orders.create(body)
client.estamp.stamps.get_certificate(stamp_id)
client.stamp_duty_wallet.topup(1000)
client.account.balance()

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
| 409 | `ConflictError` (`IDEMPOTENCY_IN_PROGRESS` carries `.retry_after`) |
| 429 | `RateLimitError` (`.retry_after` seconds) |
| 5xx | `UpstreamError` |
| network / timeout | `APIConnectionError` / `APITimeoutError` |

Non-JSON error bodies still map by status. The API error body is `{"error": {"code", "message", "requestId", "field?", "details?"}}`; `details` is exposed as typed attributes on every exception: `e.errors` (a list of `FieldIssue(field, code, message, index)`, empty when absent), `e.wallet` (`"STAMP_DUTY"` or `"SERVICE_FEE"` on a 402 from an e-Stamp order), `e.details` (the raw mapping) and `e.retry_after` (the `Retry-After` header in seconds, when sent).

## Retries and idempotency

Default `max_retries=2` with exponential backoff and full jitter (base 0.5 s, cap 8 s); `Retry-After` (seconds or HTTP date, capped at 60 s) is honoured when present, otherwise the jittered backoff is used. Retried: 429 (except `SANDBOX_ESTAMP_ORDER_LIMIT`, a quota), 502, 503, 504, connection errors and timeouts, and 409 `IDEMPOTENCY_IN_PROGRESS` for keyed POSTs (resend the identical request after `Retry-After`).

The backend honours `Idempotency-Key` on **every** metered call, so the SDK auto-generates a CSPRNG UUIDv4 key for **every POST** (all `verify.*` calls, `estamp.calculate_duty`, `estamp.add_parties`, `orders.create`, `payments.intents.create`) unless you pass `options=RequestOptions(idempotency_key=...)`, which always wins. The same key is reused across automatic retries, so a retried verification is replayed by the server instead of being billed twice. Each separate call gets a fresh key; reuse your own key to make several calls one logical operation. GET requests carry no key.

**Never retried:** order cancel, stamp cancel, stamp replace, the PAN-card link, both wallet top-ups (they take no `Idempotency-Key`; not even when you pass one, not even on a connection error). `estamp.orders.validate` is a dry run (not keyed, safe to retry) and is retried. `estamp.orders.create` requires a key, so one is always sent. `estamp.orders.upload_document` is keyed like the other creating POSTs.

**Exception: `webhooks.events.replay`** is never auto-keyed and is never retried after a response was received (it is retried only if the TCP connection could not be established). Supply an explicit `idempotency_key` if you want it keyed.

> Changed in 0.2.0: verification POSTs previously carried no key and were never retried after a response; they are now keyed and retried as described above.

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

Constant-time comparison; timestamps more than `tolerance_seconds` (default 300) from now are rejected. Also available as `client.webhooks.verify_signature` / `construct_event`. Examples: [`examples/flask_webhook.py`](https://github.com/Bani-Global-Industries-LLP/stampmitra-developer-python/blob/main/examples/flask_webhook.py), [`examples/fastapi_webhook.py`](https://github.com/Bani-Global-Industries-LLP/stampmitra-developer-python/blob/main/examples/fastapi_webhook.py).

## Client-side validation

Inputs are normalised (trimmed, upper-cased; bank account numbers trimmed only) and checked against the same patterns as the backend before sending; failures raise `ValidationError` locally with **no network call and no billing**. Disable with `StampMitra(validate_input=False)`.

## Logging

Off by default. `StampMitra(debug=True)` logs to the `stampmitra` logger (or pass `logger=`). Authorization / `x-api-key` are redacted and PAN, GSTIN, account numbers and names are masked in logged bodies.

## Pricing

The SDK is free and MIT-licensed. You pay only for successful API calls, from one prepaid wallet. Sandbox is free: mock data on every endpoint, and it never debits your wallet.

Per-call rates by plan, in rupees, excluding 18% GST:

| Product | Pay-as-you-go | Growth | Scale | Startup | Enterprise |
|---|---|---|---|---|---|
| Standard verification (PAN, GSTIN, Voter ID, Driving Licence, CIN, Udyam, cross-lookups) | ₹5 | ₹4 | ₹3.50 | ₹4 | Custom |
| Passport and Vehicle RC | ₹9 | ₹8.50 | ₹8 | ₹8.50 | Custom |
| Bank account (penny-drop) | ₹4 | ₹4 | ₹4 | ₹4 | Custom |
| e-Stamp API fee (StampMitra's charge only) | ₹5 | ₹4 | ₹3 | ₹4 | Custom |

| | Sandbox | Pay-as-you-go | Growth | Scale | Startup | Enterprise |
|---|---|---|---|---|---|---|
| Plan fee | Free | ₹0 / month | ₹999 / month | ₹4,999 / month | Free for 6 months, then 50% off for 6 | Custom |
| Seats / API keys / webhooks | 1 / 2 / 1 | 3 / 5 / 3 | 10 / 20 / 10 | 25 / 50 / 25 | 10 / 20 / 10 | Custom |
| Requests per minute | 20 | 60 | 300 | 1,000 | 300 | Custom |
| Log retention | 7 days | 30 days | 90 days | 365 days | 90 days | Custom |
| IP allowlisting | No | No | Yes | Yes | Yes | Yes |
| White-label and custom domain | No | No | No | Yes | No | Yes |

Growth and Scale are also available yearly (₹9,990 and ₹49,990, two months free). There are separate Startup and NGO programmes. Plans, rates and limits can change, and [developer.stampmitra.in/pricing](https://developer.stampmitra.in/pricing) is the source of truth; see it for how an e-Stamp order is priced in total. API e-Stamp orders are charged per paper as a procurement charge plus an API charge (excluding GST); see [developer.stampmitra.in/pricing](https://developer.stampmitra.in/pricing) for the current rates.

## Security

Server-side use only: `sk_` keys are secrets (see above). The SDK requires `https://` base URLs, never disables TLS verification, does not follow redirects, never puts the key in exception messages or `repr()`, and verifies webhooks in constant time. Report vulnerabilities privately per [SECURITY.md](https://github.com/Bani-Global-Industries-LLP/stampmitra-developer-python/blob/main/SECURITY.md) (security@stampmitra.in).

## Development and contributing

See [CONTRIBUTING.md](https://github.com/Bani-Global-Industries-LLP/stampmitra-developer-python/blob/main/CONTRIBUTING.md) (setup, lint, type-check, tests, conformance suite). Changes are listed in the [CHANGELOG](https://github.com/Bani-Global-Industries-LLP/stampmitra-developer-python/blob/main/CHANGELOG.md). Please follow the [Code of Conduct](https://github.com/Bani-Global-Industries-LLP/stampmitra-developer-python/blob/main/CODE_OF_CONDUCT.md).

## License

MIT, see [LICENSE](https://github.com/Bani-Global-Industries-LLP/stampmitra-developer-python/blob/main/LICENSE).
