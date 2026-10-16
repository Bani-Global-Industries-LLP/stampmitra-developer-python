# Contributing

Thanks for helping improve the StampMitra Python SDK. There is no `make`; these are the commands.

```bash
python -m venv .venv && source .venv/bin/activate      # keep the venv out of git (it is ignored)
pip install -e ".[dev]"
pip install flask fastapi                              # only to type-check examples/

ruff format .                                          # format
ruff check .                                           # lint
mypy                                                   # strict type check (src, scripts, examples, tests)
pytest --cov=stampmitra                                # tests (HTTP mocked with respx; no network)
python scripts/check_spec_coverage.py                  # every spec METHOD+path must have an SDK method
pip-audit                                              # dependency audit
python -m build                                        # sdist + wheel
```

## Keeping in sync with the API

`spec/openapi.json` is a snapshot of the OpenAPI document. To update it, replace the file, then run `python scripts/check_spec_coverage.py`; it fails for any new operation lacking an SDK method. Add the operation to `src/stampmitra/_ops.py`, then add methods to **both** `_resources_sync.py` and `_resources_async.py` (the async file mirrors the sync one), plus a row in `tests/test_spec_coverage.py`.

## Guidelines

- Only `httpx` and `pydantic` as runtime dependencies. No postinstall hooks.
- Never log or commit API keys; tests use fake `sk_test_` keys and mocked HTTP.
- Billed verification POSTs must never be retried after a response (see `Core.should_retry_*`).
- Add tests and a CHANGELOG entry for behaviour changes. Run all commands above before opening a PR.
