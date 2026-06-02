from __future__ import annotations

import csv
import io
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app import app, bootstrap_admin
from data_marketplace.database import create_order_for_purchase, get_user_by_email, update_order_payment_status
from data_marketplace.seed_demo import seed_demo_data


def read_csv_response(response) -> list[dict[str, str]]:
    text = response.data.decode("utf-8-sig")
    return list(csv.DictReader(io.StringIO(text)))


def main() -> None:
    bootstrap_admin()
    seed = seed_demo_data()
    order = create_order_for_purchase(seed["purchase_request_id"])
    if order:
        update_order_payment_status(order["id"], "PAID", "CSV export QA payment.")

    admin = get_user_by_email("admin@example.com")
    if admin is None:
        raise AssertionError("admin missing")

    client = app.test_client()
    with client.session_transaction() as session:
        session["user_id"] = admin["id"]
        session["csrf_token"] = "csv-export-token"

    reports = {
        "datasets": ["id", "filename", "status"],
        "orders": ["id", "purchase_request_id", "payment_status"],
        "settlements": ["seller_id", "paid_amount", "settlement_due_amount"],
        "api-usage": ["id", "endpoint", "created_at"],
        "downloads": ["id", "file_name", "created_at"],
    }
    for report_name, required_columns in reports.items():
        response = client.get(f"/web/admin/reports/{report_name}.csv")
        if response.status_code != 200:
            raise AssertionError(f"{report_name} export returned {response.status_code}")
        content_type = response.headers.get("Content-Type", "")
        if "text/csv" not in content_type:
            raise AssertionError(f"{report_name} content type is not csv: {content_type}")
        disposition = response.headers.get("Content-Disposition", "")
        if "attachment" not in disposition or ".csv" not in disposition:
            raise AssertionError(f"{report_name} disposition invalid: {disposition}")
        text = response.data.decode("utf-8-sig")
        header = text.splitlines()[0].split(",")
        for column in required_columns:
            if column not in header:
                raise AssertionError(f"{report_name} missing column {column}: {header}")

    orders = read_csv_response(client.get("/web/admin/reports/orders.csv"))
    if not orders:
        raise AssertionError("orders export should contain at least one row")

    missing = client.get("/web/admin/reports/not-supported.csv")
    if missing.status_code != 404:
        raise AssertionError(f"unsupported report should return 404, got {missing.status_code}")

    print("ADMIN_CSV_EXPORT_TEST_PASS")


if __name__ == "__main__":
    main()
