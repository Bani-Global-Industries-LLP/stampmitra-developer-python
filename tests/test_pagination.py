from __future__ import annotations

import httpx
import respx

from tests.conftest import BASE


def _page(ids, nxt):
    return httpx.Response(
        200, json={"items": [{"id": i, "createdAt": "t", "service": "pan.verify"} for i in ids], "nextCursor": nxt}
    )


@respx.mock
def test_list_params_and_iter_all(client):
    route = respx.get(f"{BASE}/v1/logs").mock(side_effect=[_page(["a", "b"], "c1"), _page(["c"], "c2"), _page([], None)])
    ids = [e.id for e in client.logs.iter_all(from_="2026-01-01", service="pan.verify", status="200", limit=2)]
    assert ids == ["a", "b", "c"]
    q = [dict(c.request.url.params) for c in route.calls]
    assert q[0] == {"from": "2026-01-01", "service": "pan.verify", "status": "200", "limit": "2"}
    assert q[1]["cursor"] == "c1" and q[2]["cursor"] == "c2"


@respx.mock
def test_single_page_stops(client):
    route = respx.get(f"{BASE}/v1/logs").mock(return_value=_page(["a"], None))
    page = client.logs.list()
    assert page.items[0].created_at == "t" and page.next_cursor is None
    assert [e.id for e in client.logs.iter_all()] == ["a"] and route.call_count == 2


@respx.mock
async def test_async_iter_all(aclient):
    respx.get(f"{BASE}/v1/logs").mock(side_effect=[_page(["a"], "n"), _page(["b"], None)])
    got = [e.id async for e in aclient.logs.iter_all(limit=1)]
    assert got == ["a", "b"]


@respx.mock
def test_webhook_events_list_and_replay(client):
    respx.get(f"{BASE}/v1/webhooks/events").mock(
        side_effect=[
            httpx.Response(200, json={"items": [{"id": "e1"}], "nextCursor": "x"}),
            httpx.Response(200, json={"items": [{"id": "e2"}]}),
        ]
    )
    assert [e["id"] for e in client.webhooks.events.iter_all(limit=1)] == ["e1", "e2"]
    r = respx.post(f"{BASE}/v1/webhooks/events/e1/replay").mock(return_value=httpx.Response(200, json={"ok": True}))
    assert client.webhooks.events.replay("e1").ok is True
    assert r.call_count == 1
