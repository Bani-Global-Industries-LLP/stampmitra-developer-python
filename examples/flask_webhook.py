"""Flask webhook receiver. Run: STAMPMITRA_WEBHOOK_SECRET=... flask --app examples/flask_webhook run"""

import os

from flask import Flask, request

from stampmitra import WebhookSignatureError, webhooks

app = Flask(__name__)
SECRET = os.environ["STAMPMITRA_WEBHOOK_SECRET"]


@app.post("/webhooks/stampmitra")
def receive() -> "tuple[str, int]":
    try:
        event = webhooks.construct_event(
            request.get_data(),  # the RAW body, not request.json
            request.headers.get(webhooks.TIMESTAMP_HEADER, ""),
            request.headers.get(webhooks.SIGNATURE_HEADER, ""),
            SECRET,
        )
    except WebhookSignatureError as err:
        return str(err), 400
    print("event", event.core_order_id, event.core_event_type, event.occurred_at)
    return "ok", 200
