from __future__ import annotations

import copy
import io
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app import app, bootstrap_admin
from data_marketplace.database import get_user_by_email, save_validation_result, update_dataset_status, update_report_json
from data_marketplace.seed_demo import _build_demo_report, seed_demo_data


def assert_contains(text: str, *phrases: str) -> None:
    missing = [phrase for phrase in phrases if phrase not in text]
    if missing:
        raise AssertionError(f"missing admin resubmission phrases: {missing}")


def main() -> None:
    bootstrap_admin()
    seed = seed_demo_data()
    seller = get_user_by_email(seed["seller_email"])
    admin = get_user_by_email("admin@example.com")
    if seller is None or admin is None:
        raise AssertionError("demo seller or admin account is missing")

    report = copy.deepcopy(_build_demo_report(seller["id"]))
    report["metadata"]["data_name"] = "Admin Resubmission Source"
    report["format"]["filename"] = "admin_resubmission_source.csv"
    report["duplicate"]["file_hash"] = "admin-resubmission-source-hash"
    rejected_id = save_validation_result(report)
    report["dataset_id"] = rejected_id
    update_report_json(rejected_id, report)
    update_dataset_status(rejected_id, "REJECTED", "관리자 재검토용 반려 사유입니다.")

    seller_client = app.test_client()
    with seller_client.session_transaction() as session:
        session["user_id"] = seller["id"]
        session["csrf_token"] = "admin-resubmission-seller-token"

    upload_response = seller_client.post(
        "/web/datasets/upload",
        data={
            "csrf_token": "admin-resubmission-seller-token",
            "accepted_terms": "on",
            "parent_dataset_id": str(rejected_id),
            "data_name": "Admin Resubmission Source v2",
            "description": "관리자 재검토용 보완 제출입니다.",
            "format": "CSV",
            "delimiter": ",",
            "file": (io.BytesIO(b"id,value\nA,1\nB,2\n"), "admin_resubmission_v2.csv"),
        },
        content_type="multipart/form-data",
    )
    if upload_response.status_code != 302:
        raise AssertionError(f"seller resubmission upload should redirect, got {upload_response.status_code}")

    job_id = upload_response.headers.get("Location", "").rstrip("/").split("/")[-2]
    for _ in range(40):
        payload = seller_client.get(f"/web/uploads/{job_id}/status").get_json()
        if payload and payload.get("status") == "DONE":
            break
        time.sleep(0.1)
    else:
        raise AssertionError("seller resubmission upload did not finish")

    admin_client = app.test_client()
    with admin_client.session_transaction() as session:
        session["user_id"] = admin["id"]
        session["csrf_token"] = "admin-resubmission-admin-token"

    list_response = admin_client.get("/web/admin/datasets")
    if list_response.status_code != 200:
        raise AssertionError(f"admin dataset list returned {list_response.status_code}")
    list_text = list_response.data.decode("utf-8")
    assert_contains(
        list_text,
        "보완 제출",
        "원본 반려 사유",
        "관리자 재검토용 반려 사유입니다.",
        "후속 보완 제출",
        "Admin Resubmission Source v2",
    )

    print("ADMIN_RESUBMISSION_REVIEW_TEST_PASS")


if __name__ == "__main__":
    main()
