# Changelog

All notable changes are documented here. Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versioning: [SemVer](https://semver.org/) (pre-1.0: minor versions may break).

## [Unreleased]

## [0.2.0] - 2026-11-24

Aligned with StampMitra API contract 1.2.0 (bundled `spec/openapi.json`): 62 operations (was 31).

### Added
- **e-Stamp orders** (`client.estamp.orders`): `validate`, `create` (the API requires an `Idempotency-Key`; auto-generated when you pass none), `list`, `iter_all`, `get`, `cancel`, `export`, `list_stamps`, `upload_document` (`multipart/form-data`: part `file` = PAN card PDF/JPEG/PNG up to 10 MB, optional part `type` = `pan_card`; keyed and retried with the same body and key).
- **Stamps** (`client.estamp.stamps`): `get`, `cancel`, `replace`, `set_pan_card` (HTTP 202, `https://` link), `get_certificate`.
- **Catalogue** (`client.estamp`): `get_states_availability`, `get_state`, `get_state_requirements` (`article_code`, `denomination`, `category`; response has `example_body`), `list_districts`, `list_sros`, `get_wallet`.
- **Wallets**: `client.stamp_duty_wallet` and `client.service_fee_wallet` with `get_balance`, `topup`, `list_transactions`, `list_invoices`, `get_invoice` (+ `iter_transactions` / `iter_invoices`); `client.account.balance()` / `usage()`. Sync and async.
- Typed response models for all of the above (`EstampOrder`, `EstampStamp`, `StampDutyWalletTopup`, `ServiceFeeWalletTopup`, `AccountBalance`, ...) and request `TypedDict` s in `stampmitra.params` (`EstampOrderRequest`, `EstampStampLine`, `EstampParty`, `EstampPropertyArea`; `firstParty` / `secondParty` accept a name string or a party object).
- Error envelope `details` as typed attributes on every exception: `errors` (`FieldIssue(field, code, message, index)` list), `wallet` (`STAMP_DUTY` / `SERVICE_FEE` on a 402), `details`, and `retry_after` (now set on every response that carries `Retry-After`, not only 429). Existing attributes are unchanged.
- `estamp.orders.create` checks the contract's hard limits locally (1 to 5000 stamps, `quantity` 1 to 1000, one state per order, party shape, `propertyArea.unit`, `https://` `panCardImage`) and raises `ValidationError` with `errors` before any network call; `validate_input=False` skips it.
- Debug logs also mask party names, father/husband names, payer phone numbers and PAN-card links.
- Conformance test driving the shared `retry-scenarios.json` under the keyed-retry rule.
- Tests: golden-fixture replay of every new operation (sync and async, offline: `tests/fixtures/operations`, vendored from the spec repo), conformance against the spec repo's mock server (all 62 operations, multipart, idempotency, `Retry-After`, the never-retry set), all 54 shared retry scenarios, and a drift check between the vendored files and the spec repo.

### Changed
- Idempotency/retry semantics aligned with the PHP, Go, Java and .NET SDKs. The backend honours `Idempotency-Key` on every metered call, so a CSPRNG UUIDv4 key is now auto-generated for **all** POSTs (verification, `estamp.calculate_duty` included) when the caller gives none, reused across automatic retries, and POSTs are retried on 429/502/503/504 and connection errors (`Retry-After` honoured, else jittered exponential backoff). Previously verification POSTs carried no key and were never retried after a response. A caller-supplied key still wins; GET is unchanged; `webhooks.events.replay` stays unkeyed and is never retried after a response.
- Retries honour `Retry-After` on 429, 503 and 409 `IDEMPOTENCY_IN_PROGRESS` (the latter is retried for keyed POSTs). Order cancel, stamp cancel, stamp replace, PAN-card link and both wallet top-ups are never retried automatically (not even with a caller key); `estamp.orders.validate` is retried although un-keyed. A 429 `SANDBOX_ESTAMP_ORDER_LIMIT` (a quota, not a rate limit) is not retried.
- Query booleans are sent as `true` / `false`, and whole-number floats without `.0`. Requests without a body (every GET, order/stamp cancel and replace) no longer send a `Content-Type` header.
- Refreshed the vendored `tests/fixtures/webhook-signatures.json` (24 vectors, was 16) and the conformance retry harness now reads the vendored `retry-scenarios.json` and runs the optional scenarios as well.

## [0.1.0] - 2026-10-16

Aligned with the hardened OpenAPI v1 contract (bundled `spec/openapi.json`): any 2xx is success, `services.list()` returns `list[Service]`, typed order/payment/usage models, spec webhook envelope (`coreOrderId`, `coreEventType`, `occurredAt`).

### Security
- `base_url` must be `https://` (plain `http://` only for localhost).

### Fixed
- Client-side validators no longer strip spaces/hyphens from vehicle, passport and driving-licence numbers (matches the shared validator vectors and the backend patterns).

### Added
- `tests/conformance/`: runs both clients against the spec repo's mock server for all 31 operations, error mapping, retries/idempotency, timeouts, pagination, webhook and validator vectors (`STAMPMITRA_SPEC_DIR`).
- Sync `StampMitra` and async `AsyncStampMitra` clients covering all 31 operations of the Developer API snapshot.
- Resources: `verify`, `services`, `estamp`, `orders`, `payments.intents`, `usage`, `logs`, `webhooks.events`.
- Typed pydantic v2 models (snake_case attributes, camelCase wire aliases, unknown fields preserved, `.response` metadata).
- Typed exceptions per HTTP status; retries with full-jitter backoff and `Retry-After`; automatic `Idempotency-Key` on `orders.create`, `payments.intents.create`, `estamp.add_parties`.
- Client-side validators, `logs.iter_all` / `webhooks.events.iter_all`, webhook `verify_signature` / `construct_event`, redacting debug logger.
- `scripts/check_spec_coverage.py` and bundled `spec/openapi.json` snapshot.
