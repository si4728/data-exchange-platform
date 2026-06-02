from __future__ import annotations

import sys
import uuid
from pathlib import Path

from werkzeug.security import generate_password_hash

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app import app
from data_marketplace.database import (
    create_order_for_purchase,
    create_purchase_request,
    create_user,
    get_product,
    get_user_by_email,
    update_order_payment_status,
    update_purchase_request_status,
    update_product,
)
from data_marketplace.seed_demo import seed_demo_data


def main() -> None:
    seed = seed_demo_data()
    product = get_product(seed["product_id"], include_inactive=True)
    if product is None:
        raise AssertionError("demo product missing")
    update_product(
        product["id"],
        product["title"],
        product["description"] or "",
        10000,
        product["category"] or "Commerce",
        product["tags"] or "demo",
        product["license_name"] or "Standard Data License",
        product["usage_terms"] or "",
    )

    buyer_email = f"payment.gate.{uuid.uuid4().hex}@obdm.local"
    buyer = create_user(
        name="Payment Gate Buyer",
        email=buyer_email,
        password_hash=generate_password_hash("demo1234"),
        company="OBDM QA",
        role="USER",
        status="ACTIVE",
    )
    purchase = create_purchase_request(product["id"], buyer["id"], "Payment gate QA")
    update_purchase_request_status(purchase["id"], "APPROVED", "")
    order = create_order_for_purchase(purchase["id"])
    if order is None or order["payment_status"] != "PENDING":
        raise AssertionError(f"pending order missing: {order}")

    client = app.test_client()
    with client.session_transaction() as session:
        session["user_id"] = buyer["id"]
        session["csrf_token"] = "payment-access-token"

    blocked_sample = client.get(f"/products/{product['id']}/sample")
    if blocked_sample.status_code != 403:
        raise AssertionError(f"paid product sample should be blocked before payment: {blocked_sample.status_code}")

    blocked_key = client.post(
        f"/web/purchases/{purchase['id']}/api-key",
        data={"csrf_token": "payment-access-token"},
    )
    if blocked_key.status_code != 400:
        raise AssertionError(f"paid product API key should be blocked before payment: {blocked_key.status_code}")

    update_order_payment_status(order["id"], "PAID", "Payment gate QA paid.")

    paid_sample = client.get(f"/products/{product['id']}/sample")
    if paid_sample.status_code != 200:
        raise AssertionError(f"paid product sample should be available after payment: {paid_sample.status_code}")

    paid_key = client.post(
        f"/web/purchases/{purchase['id']}/api-key",
        data={"csrf_token": "payment-access-token"},
    )
    if paid_key.status_code not in {302, 303}:
        raise AssertionError(f"paid product API key should be issued after payment: {paid_key.status_code}")

    seller = get_user_by_email(seed["seller_email"])
    if seller is None:
        raise AssertionError("seller missing")

    print("PAYMENT_ACCESS_GATE_TEST_PASS")


if __name__ == "__main__":
    main()
