"""Create an e-Stamp order. Run: STAMPMITRA_API_KEY=sk_test_... python examples/create_order.py

The Idempotency-Key is generated for you and reused across automatic retries;
pass RequestOptions(idempotency_key=...) to supply your own.
"""

from stampmitra import RequestOptions, StampMitra

with StampMitra() as client:
    services = client.services.list()  # a list of Service
    code = next((s.service_code for s in services if s.service_code), "estamp.instrument.rent_agreement")
    order = client.orders.create(
        {
            "externalOrderId": "ord_ext_123",
            "externalCustomerId": "cust_ext_456",
            "serviceCode": code,
            "details": {"state": "MH", "stampValue": 500},
        },
        options=RequestOptions(idempotency_key="ord_ext_123-create"),
    )
    print(order.to_dict())
    order_id = order.external_order_id or "ord_ext_123"
    print(client.orders.get_status(order_id).to_dict())
