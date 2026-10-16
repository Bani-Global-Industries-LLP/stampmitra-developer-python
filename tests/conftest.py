from __future__ import annotations

from typing import Any, List

import pytest

from stampmitra import AsyncStampMitra, StampMitra

KEY = "sk_test_abcdefgh12345678"
BASE = "https://api-b2b.stampmitra.in"


class Clock:
    """Fake sleep + deterministic jitter (random() == 1.0 -> full backoff window)."""

    def __init__(self) -> None:
        self.sleeps: List[float] = []

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)

    async def async_sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)


@pytest.fixture
def clock() -> Clock:
    return Clock()


def _wire(client: Any, clock: Clock) -> Any:
    client._core.sleep = clock.sleep
    client._core.async_sleep = clock.async_sleep
    client._core.random = lambda: 1.0
    return client


@pytest.fixture
def client(clock: Clock) -> Any:
    c = _wire(StampMitra(KEY), clock)
    yield c
    c.close()


@pytest.fixture
async def aclient(clock: Clock) -> Any:
    c = _wire(AsyncStampMitra(KEY), clock)
    yield c
    await c.aclose()
