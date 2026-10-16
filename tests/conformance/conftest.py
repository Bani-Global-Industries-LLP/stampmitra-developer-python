"""Conformance harness: runs the SDK against the spec repo's mock server (``scripts/mock-server.mjs``).

Set ``STAMPMITRA_SPEC_DIR`` to a checkout of stampmitra-developer-openapi (CI does this). Without it the
suite is skipped, unless a sibling ``../stampmitra-developer-openapi`` checkout exists. Needs ``node``.
"""

from __future__ import annotations

import os
import shutil
import socket
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, Iterator, List

import httpx
import pytest

from stampmitra import AsyncStampMitra, StampMitra

KEY = "sk_test_conformance12345"


def _spec_dir() -> Path:
    env = os.environ.get("STAMPMITRA_SPEC_DIR")
    if env:
        return Path(env)
    return Path(__file__).resolve().parents[3] / "stampmitra-developer-openapi"


@pytest.fixture(scope="session")
def spec_dir() -> Path:
    d = _spec_dir()
    if not (d / "scripts" / "mock-server.mjs").is_file():
        pytest.skip("spec repo not found (set STAMPMITRA_SPEC_DIR)")
    if shutil.which("node") is None:
        pytest.skip("node is required to run the mock server")
    return d


@pytest.fixture(scope="session")
def mock_url(spec_dir: Path) -> Iterator[str]:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    proc = subprocess.Popen(
        ["node", str(spec_dir / "scripts" / "mock-server.mjs"), "--port", str(port)],  # noqa: S607
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    url = f"http://127.0.0.1:{port}"
    try:
        for _ in range(100):
            try:
                if httpx.get(url + "/__mock/health", timeout=1).status_code == 200:
                    break
            except httpx.HTTPError:
                time.sleep(0.1)
        else:
            pytest.fail("mock server did not start")
        yield url
    finally:
        proc.terminate()
        proc.wait(timeout=10)


class Mock:
    def __init__(self, url: str) -> None:
        self.url = url

    def reset(self) -> None:
        httpx.post(self.url + "/__mock/reset")

    def requests(self) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = httpx.get(self.url + "/__mock/requests").json()
        return out


@pytest.fixture
def mock(mock_url: str) -> Mock:
    m = Mock(mock_url)
    m.reset()
    return m


class Sleeps:
    def __init__(self) -> None:
        self.values: List[float] = []

    def sleep(self, s: float) -> None:
        self.values.append(s)

    async def async_sleep(self, s: float) -> None:
        self.values.append(s)


@pytest.fixture
def sleeps() -> Sleeps:
    return Sleeps()


@pytest.fixture
def client(mock: Mock, sleeps: Sleeps) -> Iterator[StampMitra]:
    c = StampMitra(KEY, base_url=mock.url, max_retries=2)
    c._core.sleep = sleeps.sleep
    c._core.random = lambda: 1.0
    yield c
    c.close()


@pytest.fixture
async def aclient(mock: Mock, sleeps: Sleeps) -> Any:
    c = AsyncStampMitra(KEY, base_url=mock.url, max_retries=2)
    c._core.async_sleep = sleeps.async_sleep
    c._core.random = lambda: 1.0
    yield c
    await c.aclose()
