from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app import app, bootstrap_admin
from data_marketplace.database import (
    create_order_for_purchase,
    get_product,
    get_user_by_email,
    list_orders,
    update_product,
)
from data_marketplace.seed_demo import DEMO_BUYER_EMAIL, seed_demo_data


def main() -> None:
    bootstrap_admin()
    seed = seed_demo_data()
    product = get_product(seed["product_id"], include_inactive=True)
    if product is None:
        raise AssertionError("demo product missing")

    updated = update_product(
        product["id"],
        product["title"],
        product["description"] or "",
        0,
        product["category"] or "Commerce",
        product["tags"] or "demo",
        product["license_name"] or "Standard Data License",
        product["usage_terms"] or "",
        "FREE",
    )
    if not updated:
        raise AssertionError("product pricing update failed")

    free_product = get_product(product["id"], include_inactive=True)
    if free_product is None or free_product["pricing_model"] != "FREE" or int(free_product["price"]) != 0:
        raise AssertionError(f"free pricing model was not applied: {free_product}")

    order = create_order_for_purchase(seed["purchase_request_id"])
    if order is None:
        raise AssertionError("buyer order missing")

    buyer = get_user_by_email(DEMO_BUYER_EMAIL)
    if buyer is None:
        raise AssertionError("demo buyer missing")
    buyer_orders = list_orders(buyer_id=buyer["id"])
    if not buyer_orders:
        raise AssertionError("buyer orders are empty")

    client = app.test_client()
    with client.session_transaction() as session:
        session["user_id"] = buyer["id"]
        session["csrf_token"] = "pricing-buyer-orders-token"

    orders_response = client.get("/web/orders")
    if orders_response.status_code != 200:
        raise AssertionError(f"buyer orders page returned {orders_response.status_code}")
    orders_text = orders_response.data.decode("utf-8")
    for phrase in ["내 주문/결제 내역", "가격 정책", "무료", "API 키"]:
        if phrase not in orders_text:
            raise AssertionError(f"missing buyer orders phrase: {phrase}")

    edit_response = client.get(f"/web/products/{product['id']}/edit")
    if edit_response.status_code not in {200, 403}:
        raise AssertionError(f"unexpected edit response: {edit_response.status_code}")

    print("PRICING_BUYER_ORDERS_TEST_PASS")


if __name__ == "__main__":
    main()
