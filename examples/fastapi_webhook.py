"""FastAPI webhook receiver. Run: STAMPMITRA_WEBHOOK_SECRET=... uvicorn examples.fastapi_webhook:app"""

import os

from fastapi import FastAPI, HTTPException, Request

from stampmitra import WebhookSignatureError, webhooks

app = FastAPI()
SECRET = os.environ.get("STAMPMITRA_WEBHOOK_SECRET", "")


@app.post("/webhooks/stampmitra")
async def receive(request: Request) -> "dict[str, bool]":
    raw = await request.body()  # the RAW body, not request.json()
    try:
        event = webhooks.construct_event(
            raw,
            request.headers.get(webhooks.TIMESTAMP_HEADER, ""),
            request.headers.get(webhooks.SIGNATURE_HEADER, ""),
            SECRET,
        )
    except WebhookSignatureError as err:
        raise HTTPException(status_code=400, detail=str(err)) from err
    print("event", event.core_order_id, event.core_event_type, event.occurred_at)
    return {"ok": True}
