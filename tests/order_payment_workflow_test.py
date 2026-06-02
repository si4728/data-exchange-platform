from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app import app, bootstrap_admin
from data_marketplace.database import (
    create_order_for_purchase,
    get_order_by_purchase_request,
    get_purchase_request,
    get_seller_revenue_summary,
    get_user_by_email,
    update_order_payment_status,
)
from data_marketplace.seed_demo import DEMO_SELLER_EMAIL, seed_demo_data


def main() -> None:
    bootstrap_admin()
    seed = seed_demo_data()
    order = create_order_for_purchase(seed["purchase_request_id"])
    if order is None:
        raise AssertionError("order was not created")

    requested = update_order_payment_status(order["id"], "PAYMENT_REQUESTED", "Invoice sent for QA.")
    if requested is None or requested["payment_status"] != "PAYMENT_REQUESTED":
        raise AssertionError(f"payment request transition failed: {requested}")

    paid = update_order_payment_status(order["id"], "PAID", "Manual payment confirmed for QA.")
    if paid is None:
        raise AssertionError("paid transition returned no order")
    if paid["payment_status"] != "PAID" or paid["order_status"] != "COMPLETED":
        raise AssertionError(f"paid transition failed: {paid}")
    if not paid["paid_at"]:
        raise AssertionError("paid_at was not recorded")

    purchase = get_purchase_request(seed["purchase_request_id"])
    if purchase is None or purchase["status"] != "COMPLETED":
        raise AssertionError(f"purchase status was not completed: {purchase}")

    seller = get_user_by_email(DEMO_SELLER_EMAIL)
    if seller is None:
        raise AssertionError("demo seller missing")
    revenue = get_seller_revenue_summary(seller["id"])
    if int(revenue["paid_amount"]) < int(paid["amount"]):
        raise AssertionError(f"paid revenue was not reflected: {revenue}")

    fetched = get_order_by_purchase_request(seed["purchase_request_id"])
    if fetched is None or fetched["payment_note"] != "Manual payment confirmed for QA.":
        raise AssertionError(f"order detail was not fetched correctly: {fetched}")

    admin = get_user_by_email("admin@example.com")
    if admin is None:
        raise AssertionError("admin account missing")
    client = app.test_client()
    with client.session_transaction() as session:
        session["user_id"] = admin["id"]
        session["csrf_token"] = "order-payment-token"

    detail = client.get(f"/web/purchases/{seed['purchase_request_id']}")
    if detail.status_code != 200:
        raise AssertionError(f"purchase detail returned {detail.status_code}")
    text = detail.data.decode("utf-8")
    for phrase in ["주문 및 결제 상태", "결제 상태 저장", "결제 완료일"]:
        if phrase not in text:
            raise AssertionError(f"missing payment workflow phrase: {phrase}")

    print("ORDER_PAYMENT_WORKFLOW_TEST_PASS")


if __name__ == "__main__":
    main()
