from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from werkzeug.security import generate_password_hash

from app import app, bootstrap_admin
from data_marketplace.database import (
    create_purchase_request,
    create_user,
    get_user_by_email,
    list_products,
    update_purchase_request_status,
)


def get_or_create_buyer():
    email = "purchase-flow-buyer@example.com"
    user = get_user_by_email(email)
    if user:
        return user
    return create_user(
        name="Purchase Flow Buyer",
        email=email,
        password_hash=generate_password_hash("test1234"),
        company="OBDM QA",
        role="USER",
        status="ACTIVE",
    )


def main() -> None:
    bootstrap_admin()
    products = list_products(per_page=1)
    if not products:
        print("PURCHASE_FLOW_TEST_SKIPPED_NO_PRODUCTS")
        return

    product = products[0]
    buyer = get_or_create_buyer()
    purchase = create_purchase_request(
        product_id=product["id"],
        buyer_id=buyer["id"],
        message="Smoke test purchase request",
    )
    update_purchase_request_status(purchase["id"], "REQUESTED", "")

    client = app.test_client()
    with client.session_transaction() as session:
        session["user_id"] = buyer["id"]
        session["csrf_token"] = "purchase-flow-token"

    detail_response = client.get(f"/web/purchases/{purchase['id']}")
    if detail_response.status_code != 200:
        raise AssertionError(f"buyer detail returned {detail_response.status_code}")
    detail_text = detail_response.data.decode("utf-8")
    for phrase in ["구매 요청 상세", "접근 권한", "관리자 승인 대기"]:
        if phrase not in detail_text:
            raise AssertionError(f"missing buyer detail phrase: {phrase}")

    with client.session_transaction() as session:
        session["user_id"] = product["seller_id"]
        session["csrf_token"] = "seller-flow-token"

    seller_response = client.get("/web/seller/purchases")
    if seller_response.status_code != 200:
        raise AssertionError(f"seller purchase list returned {seller_response.status_code}")
    seller_text = seller_response.data.decode("utf-8")
    for phrase in ["내 상품 구매 요청", "요청 목록"]:
        if phrase not in seller_text:
            raise AssertionError(f"missing seller phrase: {phrase}")

    print("PURCHASE_FLOW_TEST_PASS")


if __name__ == "__main__":
    main()
