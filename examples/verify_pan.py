"""Verify a PAN (sync). Run: STAMPMITRA_API_KEY=sk_test_... python examples/verify_pan.py"""

from stampmitra import PermissionDeniedError, StampMitra, StampMitraError, ValidationError

with StampMitra() as client:  # reads STAMPMITRA_API_KEY
    try:
        result = client.verify.pan("ABCDE1234F", name="Rahul Kumar")
        print(result.reference_id, result.valid, result.registered_name, result.name_match_result)
        print("request id:", result.response.request_id if result.response else None)
    except ValidationError as err:
        print("bad input:", err.field, err.message)
    except PermissionDeniedError as err:
        print("not allowed:", err.message)
    except StampMitraError as err:
        print("API error:", err)
