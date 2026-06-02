from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app import app, bootstrap_admin
from data_marketplace.database import (
    create_order_for_purchase,
    get_user_by_email,
    list_seller_settlement_summaries,
    update_order_payment_status,
)
from data_marketplace.seed_demo import seed_demo_data


def main() -> None:
    bootstrap_admin()
    seed = seed_demo_data()
    order = create_order_for_purchase(seed["purchase_request_id"])
    if order is None:
        raise AssertionError("order missing")
    paid_order = update_order_payment_status(order["id"], "PAID", "Settlement QA payment.")
    if paid_order is None:
        raise AssertionError("paid order missing")

    summaries = list_seller_settlement_summaries(fee_rate=0.1)
    if not summaries:
        raise AssertionError("settlement summaries are empty")
    seller_summary = next((item for item in summaries if item["seller_email"] == seed["seller_email"]), None)
    if seller_summary is None:
        raise AssertionError("demo seller settlement summary missing")
    if int(seller_summary["paid_amount"]) < int(paid_order["amount"]):
        raise AssertionError(f"paid amount not reflected: {seller_summary}")
    expected_fee = round(int(seller_summary["paid_amount"]) * 0.1)
    if int(seller_summary["platform_fee"]) != expected_fee:
        raise AssertionError(f"platform fee mismatch: {seller_summary}")
    if int(seller_summary["settlement_due_amount"]) != int(seller_summary["paid_amount"]) - expected_fee:
        raise AssertionError(f"settlement due mismatch: {seller_summary}")

    admin = get_user_by_email("admin@example.com")
    if admin is None:
        raise AssertionError("admin missing")

    client = app.test_client()
    with client.session_transaction() as session:
        session["user_id"] = admin["id"]
        session["csrf_token"] = "settlement-token"

    response = client.get("/web/admin/settlements")
    if response.status_code != 200:
        raise AssertionError(f"settlement page returned {response.status_code}")
    text = response.data.decode("utf-8")
    for phrase in ["관리자 정산 화면", "플랫폼 수수료", "정산 예정액", "판매자별 정산 요약"]:
        if phrase not in text:
            raise AssertionError(f"missing settlement phrase: {phrase}")

    print("ADMIN_SETTLEMENT_TEST_PASS")


if __name__ == "__main__":
    main()
