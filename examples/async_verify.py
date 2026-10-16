"""Run several verifications concurrently. Run: STAMPMITRA_API_KEY=sk_test_... python examples/async_verify.py"""

import asyncio

from stampmitra import AsyncStampMitra


async def main() -> None:
    async with AsyncStampMitra() as client:
        pan, gstin, rc = await asyncio.gather(
            client.verify.pan("ABCDE1234F"),
            client.verify.gstin("07AAAAA1111A1Z1"),
            client.verify.rc("MH12AB1234"),
        )
        print(pan.valid, gstin.valid, rc.registration_status)
        async for entry in client.logs.iter_all(service="pan.verify", limit=50):
            print(entry.id, entry.created_at)


asyncio.run(main())
