from __future__ import annotations

import csv
import io
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
    get_product,
    get_purchase_request,
    get_user_by_email,
    update_order_payment_status,
    update_product,
    update_purchase_request_status,
)
from data_marketplace.seed_demo import seed_demo_data


def login_as(client, user_id: int, csrf: str = "security-token") -> None:
    with client.session_transaction() as session:
        session["user_id"] = user_id
        session["csrf_token"] = csrf


def main() -> None:
    seed = seed_demo_data()
    admin = get_user_by_email("admin@example.com")
    seller = get_user_by_email(seed["seller_email"])
    if admin is None or seller is None:
        raise AssertionError("required accounts are missing")

    product = get_product(seed["product_id"], include_inactive=True)
    if product is None:
        raise AssertionError("demo product is missing")

    update_product(
        product["id"],
        "=Formula Product",
        product["description"] or "",
        10000,
        product["category"] or "Commerce",
        product["tags"] or "demo",
        product["license_name"] or "Standard Data License",
        product["usage_terms"] or "",
        "ONE_TIME",
    )

    buyer = create_user(
        name="Security Buyer",
        email=f"security-buyer-{uuid.uuid4().hex}@example.com",
        password_hash=generate_password_hash("test1234"),
        company="OBDM QA",
        role="USER",
        status="ACTIVE",
    )
    other_user = create_user(
        name="Security Other User",
        email=f"security-other-{uuid.uuid4().hex}@example.com",
        password_hash=generate_password_hash("test1234"),
        company="OBDM QA",
        role="USER",
        status="ACTIVE",
    )

    purchase = create_purchase_request(product["id"], buyer["id"], "Security regression")
    update_purchase_request_status(purchase["id"], "APPROVED", "")
    order = create_order_for_purchase(purchase["id"])
    if order is None:
        raise AssertionError("order was not created")

    client = app.test_client()

    anonymous_csv = client.get("/web/admin/reports/orders.csv")
    if anonymous_csv.status_code not in {302, 308}:
        raise AssertionError(f"anonymous CSV export should redirect, got {anonymous_csv.status_code}")

    login_as(client, other_user["id"])
    user_csv = client.get("/web/admin/reports/orders.csv")
    if user_csv.status_code != 403:
        raise AssertionError(f"non-admin CSV export should be forbidden, got {user_csv.status_code}")

    hidden_purchase = client.get(f"/web/purchases/{purchase['id']}")
    if hidden_purchase.status_code != 403:
        raise AssertionError(f"other user's purchase detail should be forbidden, got {hidden_purchase.status_code}")

    missing_csrf = client.post(f"/web/products/{product['id']}/favorite")
    if missing_csrf.status_code != 400:
        raise AssertionError(f"missing CSRF should be rejected, got {missing_csrf.status_code}")

    login_as(client, admin["id"])
    csv_response = client.get("/web/admin/reports/orders.csv")
    if csv_response.status_code != 200:
        raise AssertionError(f"admin CSV export failed: {csv_response.status_code}")
    if csv_response.headers.get("X-Frame-Options") != "DENY":
        raise AssertionError("security headers were not applied")
    rows = list(csv.DictReader(io.StringIO(csv_response.data.decode("utf-8-sig"))))
    if not rows:
        raise AssertionError("orders CSV should contain at least one row")
    if any(row.get("product_title") == "=Formula Product" for row in rows):
        raise AssertionError("CSV formula value was not escaped")
    if any("token_hash" in row for row in rows):
        raise AssertionError("CSV export exposed token_hash")

    update_order_payment_status(order["id"], "PAID", "Security test payment.")
    token = f"security_{secrets.token_urlsafe(12)}"
    api_key = create_api_key(
        purchase_request_id=purchase["id"],
        token_hash=_hash_token(token),
        token_prefix=token[:12],
    )
    if api_key["token_hash"] == token:
        raise AssertionError("API key token was stored in plaintext")

    query_key_response = client.get(f"/api/v1/products/{product['id']}/sample?api_key={token}")
    if query_key_response.status_code != 401:
        raise AssertionError(f"query string API key should be rejected, got {query_key_response.status_code}")
    header_key_response = client.get(
        f"/api/v1/products/{product['id']}/sample",
        headers={"X-API-Key": token},
    )
    if header_key_response.status_code != 200:
        raise AssertionError(f"header API key should work, got {header_key_response.status_code}")

    refreshed_purchase = get_purchase_request(purchase["id"])
    if refreshed_purchase is None or refreshed_purchase["buyer_id"] != buyer["id"]:
        raise AssertionError("purchase ownership changed unexpectedly")

    print("SECURITY_REGRESSION_TEST_PASS")


if __name__ == "__main__":
    main()
