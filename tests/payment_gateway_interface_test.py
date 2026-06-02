from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app import app, bootstrap_admin
from data_marketplace.database import create_order_for_purchase, get_user_by_email, list_payment_events
from data_marketplace.payments import confirm_payment, request_payment
from data_marketplace.seed_demo import seed_demo_data


def main() -> None:
    bootstrap_admin()
    seed = seed_demo_data()
    order = create_order_for_purchase(seed["purchase_request_id"])
    if order is None:
        raise AssertionError("order was not created")

    reference = f"PG-READY-{order['id']}"
    requested = request_payment(
        order["id"],
        note="PG request prepared.",
        provider="MANUAL_PG",
        provider_reference=reference,
        detail={"channel": "admin"},
    )
    if requested is None or requested["payment_status"] != "PAYMENT_REQUESTED":
        raise AssertionError(f"payment request transition failed: {requested}")
    if requested["payment_provider"] != "MANUAL_PG" or requested["payment_reference"] != reference:
        raise AssertionError(f"provider reference was not stored: {requested}")

    paid = confirm_payment(
        order["id"],
        note="PG callback confirmed.",
        provider="MANUAL_PG",
        provider_reference=reference,
        detail={"callback": "success"},
    )
    if paid is None or paid["payment_status"] != "PAID" or paid["order_status"] != "COMPLETED":
        raise AssertionError(f"payment confirmation failed: {paid}")

    events = list_payment_events(order["id"])
    event_types = {event["event_type"] for event in events}
    if {"PAYMENT_REQUESTED", "PAYMENT_CONFIRMED"} - event_types:
        raise AssertionError(f"payment events were not recorded: {events}")

    admin = get_user_by_email("admin@example.com")
    if admin is None:
        raise AssertionError("admin missing")
    client = app.test_client()
    with client.session_transaction() as session:
        session["user_id"] = admin["id"]
        session["csrf_token"] = "payment-gateway-interface-token"

    detail = client.get(f"/web/purchases/{seed['purchase_request_id']}")
    if detail.status_code != 200:
        raise AssertionError(f"purchase detail returned {detail.status_code}")
    text = detail.data.decode("utf-8")
    for phrase in ["결제 Provider", "결제 참조번호", "결제 이벤트 이력", "MANUAL_PG", reference]:
        if phrase not in text:
            raise AssertionError(f"missing payment interface phrase: {phrase}")

    print("PAYMENT_GATEWAY_INTERFACE_TEST_PASS")


if __name__ == "__main__":
    main()
