from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app import app, bootstrap_admin
from data_marketplace.database import get_user_by_email
from data_marketplace.seed_demo import seed_demo_data


def assert_contains(text: str, *phrases: str) -> None:
    missing = [phrase for phrase in phrases if phrase not in text]
    if missing:
        raise AssertionError(f"missing seller progress phrases: {missing}")


def main() -> None:
    bootstrap_admin()
    seed = seed_demo_data()
    seller = get_user_by_email(seed["seller_email"])
    if seller is None:
        raise AssertionError("demo seller account is missing")

    client = app.test_client()
    with client.session_transaction() as session:
        session["user_id"] = seller["id"]
        session["csrf_token"] = "seller-progress-token"

    response = client.get("/user/dashboard")
    if response.status_code != 200:
        raise AssertionError(f"seller dashboard returned {response.status_code}")

    text = response.data.decode("utf-8")
    assert_contains(
        text,
        "내가 올린 데이터",
        "진행 상태",
        "단계",
        "다음 행동",
        "마켓 게시",
        "마켓 상품 보기",
        "리포트 보기",
    )

    print("SELLER_DATASET_PROGRESS_TEST_PASS")


if __name__ == "__main__":
    main()
