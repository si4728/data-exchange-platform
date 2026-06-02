from __future__ import annotations

import sys
from pathlib import Path

from werkzeug.security import generate_password_hash

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app import app, bootstrap_admin
from data_marketplace.database import create_user, get_user_by_email


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
        session["csrf_token"] = "operations-checklist-token"


def main() -> None:
    bootstrap_admin()
    admin = get_user_by_email("admin@example.com")
    if admin is None:
        raise AssertionError("default admin account is missing")
    user = get_or_create_user("operations-checklist-user@example.com", "Operations Checklist User")

    client = app.test_client()

    anonymous_response = client.get("/web/admin/operations-checklist")
    if anonymous_response.status_code not in {302, 308}:
        raise AssertionError(f"anonymous access should redirect, got {anonymous_response.status_code}")

    login_as(client, user["id"])
    user_response = client.get("/web/admin/operations-checklist")
    if user_response.status_code != 403:
        raise AssertionError(f"normal user access should be forbidden, got {user_response.status_code}")

    login_as(client, admin["id"])
    admin_response = client.get("/web/admin/operations-checklist")
    if admin_response.status_code != 200:
        raise AssertionError(f"admin checklist returned {admin_response.status_code}")

    text = admin_response.data.decode("utf-8")
    required_phrases = [
        "운영 점검표",
        "SECRET_KEY",
        "SQLite",
        "파일 보관 정책",
        "테스트 실행 기준",
        "PG 연동 준비",
        "DB 백업",
    ]
    missing = [phrase for phrase in required_phrases if phrase not in text]
    if missing:
        raise AssertionError(f"missing operations checklist phrases: {missing}")

    print("OPERATIONS_CHECKLIST_TEST_PASS")


if __name__ == "__main__":
    main()
