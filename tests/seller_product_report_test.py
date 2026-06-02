from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app import app
from data_marketplace.database import (
    create_order_for_purchase,
    get_purchase_request,
    get_user_by_email,
    list_seller_product_reports,
    record_api_usage,
    record_download_log,
    update_order_payment_status,
)
from data_marketplace.seed_demo import seed_demo_data


def assert_contains(text: str, *phrases: str) -> None:
    missing = [phrase for phrase in phrases if phrase not in text]
    if missing:
        raise AssertionError(f"missing seller report phrases: {missing}")


def main() -> None:
    seed = seed_demo_data()
    seller = get_user_by_email(seed["seller_email"])
    buyer = get_user_by_email(seed["buyer_email"])
    purchase = get_purchase_request(seed["purchase_request_id"])
    if seller is None or buyer is None or purchase is None:
        raise AssertionError("demo seller, buyer, or purchase is missing")

    order = create_order_for_purchase(purchase["id"])
    if order:
        update_order_payment_status(order["id"], "PAID", "Seller report QA payment.")

    record_download_log(
        product_id=purchase["product_id"],
        user_id=buyer["id"],
        file_name="seller_report_sample.csv",
        ip_address="127.0.0.1",
    )
    record_api_usage(
        api_key_id=None,
        product_id=purchase["product_id"],
        user_id=buyer["id"],
        endpoint="/api/v1/products/report/sample",
        ip_address="127.0.0.1",
    )

    reports = list_seller_product_reports(seller["id"])
    demo_report = next((item for item in reports if item["product_id"] == purchase["product_id"]), None)
    if demo_report is None:
        raise AssertionError("demo product report is missing")
    if int(demo_report["purchase_request_count"] or 0) < 1:
        raise AssertionError(f"purchase count missing: {demo_report}")
    if int(demo_report["sample_download_count"] or 0) < 1:
        raise AssertionError(f"download count missing: {demo_report}")
    if int(demo_report["api_usage_count"] or 0) < 1:
        raise AssertionError(f"api usage count missing: {demo_report}")

    client = app.test_client()
    with client.session_transaction() as session:
        session["user_id"] = seller["id"]
        session["csrf_token"] = "seller-product-report-token"

    response = client.get("/web/seller/reports")
    if response.status_code != 200:
        raise AssertionError(f"seller report page returned {response.status_code}")
    assert_contains(
        response.data.decode("utf-8"),
        "판매자 상품 운영 리포트",
        "상품별 운영 현황",
        "구매 요청",
        "샘플 다운로드",
        "API 호출",
        "Demo Customer Orders Dataset",
    )

    print("SELLER_PRODUCT_REPORT_TEST_PASS")


if __name__ == "__main__":
    main()
