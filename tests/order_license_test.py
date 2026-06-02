from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app import app
from data_marketplace.database import (
    create_order_for_purchase,
    get_product,
    get_seller_revenue_summary,
    get_user_by_email,
    list_orders,
)
from data_marketplace.seed_demo import DEMO_SELLER_EMAIL, seed_demo_data


def main() -> None:
    seed = seed_demo_data()
    product = get_product(seed["product_id"], include_inactive=True)
    if product is None:
        raise AssertionError("demo product is missing")
    if not product.get("license_name"):
        raise AssertionError("product license name is missing")
    if not product.get("usage_terms"):
        raise AssertionError("product usage terms are missing")

    order = create_order_for_purchase(seed["purchase_request_id"])
    if order is None:
        raise AssertionError("order was not created for approved purchase")
    if order["payment_status"] not in {"PENDING", "PAYMENT_REQUESTED", "PAID", "FAILED", "CANCELED"}:
        raise AssertionError(f"unexpected order state: {order}")
    if int(order["amount"]) < 0:
        raise AssertionError(f"order amount should not be negative: {order['amount']}")

    seller = get_user_by_email(DEMO_SELLER_EMAIL)
    if seller is None:
        raise AssertionError("demo seller is missing")
    seller_orders = list_orders(seller_id=seller["id"])
    if not seller_orders:
        raise AssertionError("seller order list is empty")
    revenue = get_seller_revenue_summary(seller["id"])
    if int(revenue["order_count"]) < 1:
        raise AssertionError(f"seller revenue summary is empty: {revenue}")

    client = app.test_client()
    with client.session_transaction() as session:
        session["user_id"] = seller["id"]
        session["csrf_token"] = "order-license-token"

    response = client.get(f"/web/products/{product['id']}")
    if response.status_code != 200:
        raise AssertionError(f"product detail returned {response.status_code}")
    text = response.data.decode("utf-8")
    for phrase in ["라이선스 및 사용 조건", "컬럼 통계", "샘플 미리보기"]:
        if phrase not in text:
            raise AssertionError(f"missing product detail phrase: {phrase}")

    dashboard = client.get("/user/dashboard")
    if dashboard.status_code != 200:
        raise AssertionError(f"user dashboard returned {dashboard.status_code}")
    dashboard_text = dashboard.data.decode("utf-8")
    for phrase in ["판매 예상 매출", "내 주문 준비 현황", "결제 대기액"]:
        if phrase not in dashboard_text:
            raise AssertionError(f"missing dashboard phrase: {phrase}")

    print("ORDER_LICENSE_TEST_PASS")


if __name__ == "__main__":
    main()
