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
        raise AssertionError(f"missing admin review phrases: {missing}")


def main() -> None:
    bootstrap_admin()
    seed = seed_demo_data()
    admin = get_user_by_email("admin@example.com")
    if admin is None:
        raise AssertionError("default admin account is missing")

    client = app.test_client()
    with client.session_transaction() as session:
        session["user_id"] = admin["id"]
        session["csrf_token"] = "admin-review-ui-token"

    list_response = client.get("/web/admin/datasets")
    if list_response.status_code != 200:
        raise AssertionError(f"admin dataset list returned {list_response.status_code}")
    list_text = list_response.data.decode("utf-8")
    assert_contains(
        list_text,
        "판단 근거",
        "평균 NULL",
        "PII 컬럼",
        "주요 컬럼",
        "APPROVE_CANDIDATE",
    )

    report_response = client.get(f"/web/datasets/{seed['dataset_id']}")
    if report_response.status_code != 200:
        raise AssertionError(f"dataset report returned {report_response.status_code}")
    report_text = report_response.data.decode("utf-8")
    assert_contains(
        report_text,
        "관리자 승인 판단 요약",
        "승인 전 확인 체크리스트",
        "개인정보 위험",
        "품질 점수",
    )

    print("ADMIN_REVIEW_UI_TEST_PASS")


if __name__ == "__main__":
    main()
