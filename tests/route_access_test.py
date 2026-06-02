from __future__ import annotations

import sys
from pathlib import Path

from werkzeug.security import generate_password_hash

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app import app, bootstrap_admin
from data_marketplace.database import create_user, get_user_by_email, list_products


def get_or_create_user(email: str, name: str):
    user = get_user_by_email(email)
    if user:
        return user
    return create_user(
        name=name,
        email=email,
        password_hash=generate_password_hash("test1234"),
        company="OBDM QA",
        role="USER",
        status="ACTIVE",
    )


def login_as(client, user_id: int) -> None:
    with client.session_transaction() as session:
        session["user_id"] = user_id
        session["csrf_token"] = "route-access-token"


def assert_get(client, path: str, expected: int) -> None:
    response = client.get(path)
    if response.status_code != expected:
        raise AssertionError(f"{path} returned {response.status_code}, expected {expected}")


def main() -> None:
    bootstrap_admin()
    admin = get_user_by_email("admin@example.com")
    if admin is None:
        raise AssertionError("default admin account is missing")
    user = get_or_create_user("route-access-user@example.com", "Route Access User")

    client = app.test_client()

    public_paths = [
        "/login",
        "/register",
        "/policies/privacy",
        "/policies/data-retention",
        "/policies/seller-terms",
        "/health",
    ]
    for path in public_paths:
        assert_get(client, path, 200)

    protected_paths = [
        "/",
        "/user/dashboard",
        "/market",
        "/web/admin",
        "/web/admin/datasets",
        "/web/seller/purchases",
        "/web/seller/reports",
    ]
    for path in protected_paths:
        response = client.get(path)
        if response.status_code not in {302, 308}:
            raise AssertionError(f"{path} should redirect anonymous users, got {response.status_code}")

    login_as(client, user["id"])
    user_paths = [
        "/",
        "/user/dashboard",
        "/market",
        "/web/orders",
        "/web/seller/purchases",
        "/web/seller/reports",
    ]
    for path in user_paths:
        assert_get(client, path, 200)

    for path in ["/web/admin", "/web/admin/datasets", "/web/admin/products", "/web/admin/purchases", "/web/admin/settlements", "/web/admin/operations-checklist", "/web/admin/database-backup.sqlite", "/web/admin/reports/orders.csv", "/web/admin/access-logs"]:
        assert_get(client, path, 403)

    login_as(client, admin["id"])
    admin_paths = [
        "/web/admin",
        "/web/admin/datasets",
        "/web/admin/products",
        "/web/admin/purchases",
        "/web/admin/settlements",
        "/web/admin/operations-checklist",
        "/web/admin/database-backup.sqlite",
        "/web/admin/reports/orders.csv",
        "/web/admin/users",
        "/web/admin/downloads",
        "/web/admin/api-usage",
        "/web/admin/api-keys",
        "/web/admin/access-logs",
        "/web/admin/audit-logs",
    ]
    for path in admin_paths:
        assert_get(client, path, 200)

    products = list_products(per_page=1)
    if products:
        assert_get(client, f"/web/products/{products[0]['id']}", 200)
        assert_get(client, f"/products/{products[0]['id']}", 200)

    print("ROUTE_ACCESS_TEST_PASS")


if __name__ == "__main__":
    main()
