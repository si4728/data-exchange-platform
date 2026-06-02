from __future__ import annotations

import secrets
import sys
import uuid
from pathlib import Path

from werkzeug.security import generate_password_hash

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app import app, _hash_token
from data_marketplace.database import (
    create_api_key,
    create_order_for_purchase,
    create_purchase_request,
    create_user,
    get_api_key_usage_summary,
    get_purchase_request,
    list_products,
    record_api_usage,
    update_order_payment_status,
    update_purchase_request_status,
)
from data_marketplace.seed_demo import seed_demo_data


def main() -> None:
    seed = seed_demo_data()
    products = list_products(per_page=1)
    if not products:
        raise AssertionError("demo product is missing")
    buyer = create_user(
        name="API Limit Buyer",
        email=f"api-limit-{uuid.uuid4().hex}@example.com",
        password_hash=generate_password_hash("test1234"),
        company="OBDM QA",
        role="USER",
        status="ACTIVE",
    )
    purchase = create_purchase_request(
        product_id=products[0]["id"],
        buyer_id=buyer["id"],
        message="API limit test purchase",
    )
    update_purchase_request_status(purchase["id"], "APPROVED", "")
    order = create_order_for_purchase(purchase["id"])
    if order:
        update_order_payment_status(order["id"], "PAID", "API limit test payment.")
    purchase = get_purchase_request(purchase["id"])
    if purchase is None:
        raise AssertionError("purchase is missing")

    token = f"limit_test_{secrets.token_urlsafe(12)}"
    api_key = create_api_key(
        purchase_request_id=purchase["id"],
        token_hash=_hash_token(token),
        token_prefix=token[:12],
        total_request_limit=1,
        monthly_request_limit=1,
    )
    summary = get_api_key_usage_summary(api_key["id"])
    if summary["is_exceeded"]:
        raise AssertionError(summary)

    record_api_usage(
        api_key_id=api_key["id"],
        product_id=purchase["product_id"],
        user_id=buyer["id"],
        endpoint="/api/v1/products/test/sample",
        ip_address="127.0.0.1",
    )
    exceeded = get_api_key_usage_summary(api_key["id"])
    if not exceeded["is_exceeded"]:
        raise AssertionError(exceeded)

    client = app.test_client()
    response = client.get(
        f"/api/v1/products/{purchase['product_id']}/sample",
        headers={"X-API-Key": token},
    )
    if response.status_code != 429:
        raise AssertionError(f"expected 429 after limit exceeded, got {response.status_code}: {response.data!r}")

    print("API_LIMIT_TEST_PASS")


if __name__ == "__main__":
    main()
