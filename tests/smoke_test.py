from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app import app, bootstrap_admin
from data_marketplace.database import (
    get_user_by_email,
    is_product_favorited,
    list_products,
    remove_product_favorite,
)


def assert_status(client, path: str, expected: int = 200) -> None:
    response = client.get(path)
    if response.status_code != expected:
        raise AssertionError(f"{path} returned {response.status_code}, expected {expected}")


def assert_text(response_data: bytes, *phrases: str) -> None:
    text = response_data.decode("utf-8")
    missing = [phrase for phrase in phrases if phrase not in text]
    if missing:
        raise AssertionError(f"missing phrases: {missing}")


def main() -> None:
    bootstrap_admin()
    admin = get_user_by_email("admin@example.com")
    if admin is None:
        raise AssertionError("default admin account is missing")

    client = app.test_client()
    with client.session_transaction() as session:
        session["user_id"] = admin["id"]
        session["csrf_token"] = "smoke-test-token"

    public_paths = [
        "/login",
        "/register",
        "/policies/privacy",
        "/policies/data-retention",
        "/policies/seller-terms",
        "/health",
    ]
    for path in public_paths:
        assert_status(client, path)

    authenticated_paths = [
        "/user/dashboard",
        "/market?sort=quality_desc&per_page=5",
        "/web/admin",
        "/web/admin/datasets",
        "/web/admin/products?sort=rows_desc&per_page=10",
        "/web/admin/purchases",
        "/web/seller/purchases",
        "/web/admin/audit-logs",
        "/products?sort=price_asc&per_page=5",
    ]
    for path in authenticated_paths:
        assert_status(client, path)

    assert_text(client.get("/market").data, "데이터 마켓", "검색어", "정렬")
    assert_text(client.get("/user/dashboard").data, "내 대시보드", "관심 데이터")

    products = list_products(per_page=1)
    if products:
        product_id = products[0]["id"]
        remove_product_favorite(product_id, admin["id"])
        assert_status(client, f"/web/products/{product_id}")

        favorite_response = client.post(
            f"/web/products/{product_id}/favorite",
            data={"csrf_token": "smoke-test-token", "next": "/market"},
        )
        if favorite_response.status_code != 302:
            raise AssertionError("favorite action did not redirect")
        if not is_product_favorited(product_id, admin["id"]):
            raise AssertionError("favorite action did not persist")

        remove_response = client.post(
            f"/web/products/{product_id}/favorite/delete",
            data={"csrf_token": "smoke-test-token", "next": "/market"},
        )
        if remove_response.status_code != 302:
            raise AssertionError("favorite removal did not redirect")
        if is_product_favorited(product_id, admin["id"]):
            raise AssertionError("favorite removal did not persist")

    print("SMOKE_TEST_PASS")


if __name__ == "__main__":
    main()
