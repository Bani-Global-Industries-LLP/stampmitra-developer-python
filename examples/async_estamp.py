"""Async e-Stamp catalogue lookups. Run: STAMPMITRA_API_KEY=sk_test_... python examples/async_estamp.py"""

import asyncio

from stampmitra import AsyncStampMitra


async def main() -> None:
    async with AsyncStampMitra() as client:
        states = await client.estamp.get_states_availability(active=True)
        print([s.code for s in states.data])
        reqs = await client.estamp.get_state_requirements("MH", article_code="ART1", denomination=1000)
        print(reqs.example_body)  # a ready-to-edit order body
        async for order in client.estamp.orders.iter_all(limit=50):
            print(order.id, order.status)


asyncio.run(main())
