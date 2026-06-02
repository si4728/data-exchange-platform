from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app import app
from data_marketplace.database import (
    get_purchase_request,
    get_sample_download_summary,
    get_user_by_email,
    record_download_log,
    update_purchase_download_limit,
)
from data_marketplace.seed_demo import DEMO_BUYER_EMAIL, seed_demo_data


def main() -> None:
    seed = seed_demo_data()
    purchase = get_purchase_request(seed["purchase_request_id"])
    buyer = get_user_by_email(DEMO_BUYER_EMAIL)
    if purchase is None or buyer is None:
        raise AssertionError("demo purchase or buyer is missing")

    update_purchase_download_limit(purchase["id"], 1)
    record_download_log(
        product_id=purchase["product_id"],
        user_id=buyer["id"],
        file_name="demo_customer_orders_sample.csv",
        ip_address="127.0.0.1",
    )
    summary = get_sample_download_summary(purchase["product_id"], buyer["id"])
    if not summary["is_exceeded"]:
        raise AssertionError(summary)

    client = app.test_client()
    with client.session_transaction() as session:
        session["user_id"] = buyer["id"]
        session["csrf_token"] = "download-limit-token"

    response = client.get(f"/products/{purchase['product_id']}/sample")
    if response.status_code != 429:
        raise AssertionError(f"expected 429, got {response.status_code}: {response.data!r}")

    print("DOWNLOAD_LIMIT_TEST_PASS")


if __name__ == "__main__":
    main()
