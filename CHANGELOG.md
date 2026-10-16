# Changelog

All notable changes are documented here. Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versioning: [SemVer](https://semver.org/) (pre-1.0: minor versions may break).

## [Unreleased]

### Changed
- Idempotency/retry semantics aligned with the PHP, Go, Java and .NET SDKs. The backend honours `Idempotency-Key` on every metered call, so a CSPRNG UUIDv4 key is now auto-generated for **all** POSTs (verification, `estamp.calculate_duty` included) when the caller gives none, reused across automatic retries, and POSTs are retried on 429/502/503/504 and connection errors (`Retry-After` honoured, else jittered exponential backoff). Previously verification POSTs carried no key and were never retried after a response. A caller-supplied key still wins; GET is unchanged; `webhooks.events.replay` stays unkeyed and is never retried after a response.

### Added
- Conformance test driving the shared `retry-scenarios.json` under the keyed-retry rule.

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
