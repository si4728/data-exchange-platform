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
from data_marketplace.database import (
    get_user_by_email,
    list_datasets_by_seller,
    save_validation_result,
    update_dataset_status,
    update_report_json,
)
from data_marketplace.seed_demo import _build_demo_report, seed_demo_data


def assert_contains(text: str, *phrases: str) -> None:
    missing = [phrase for phrase in phrases if phrase not in text]
    if missing:
        raise AssertionError(f"missing resubmission phrases: {missing}")


def main() -> None:
    bootstrap_admin()
    seed = seed_demo_data()
    seller = get_user_by_email(seed["seller_email"])
    if seller is None:
        raise AssertionError("demo seller account is missing")

    report = copy.deepcopy(_build_demo_report(seller["id"]))
    report["metadata"]["data_name"] = "Rejected Resubmission Source"
    report["format"]["filename"] = "rejected_resubmission_source.csv"
    report["duplicate"]["file_hash"] = "rejected-resubmission-source-hash"
    rejected_id = save_validation_result(report)
    report["dataset_id"] = rejected_id
    update_report_json(rejected_id, report)
    update_dataset_status(rejected_id, "REJECTED", "컬럼 설명과 샘플 파일 보완이 필요합니다.")

    client = app.test_client()
    with client.session_transaction() as session:
        session["user_id"] = seller["id"]
        session["csrf_token"] = "dataset-resubmission-token"

    dashboard_response = client.get("/user/dashboard")
    if dashboard_response.status_code != 200:
        raise AssertionError(f"dashboard returned {dashboard_response.status_code}")
    assert_contains(
        dashboard_response.data.decode("utf-8"),
        "보완 필요",
        "보완 재업로드",
        "컬럼 설명과 샘플 파일 보완이 필요합니다.",
    )

    form_response = client.get(f"/web/datasets/{rejected_id}/resubmit")
    if form_response.status_code != 200:
        raise AssertionError(f"resubmit form returned {form_response.status_code}")
    assert_contains(
        form_response.data.decode("utf-8"),
        "보완 재업로드",
        "반려 사유",
        "보완 검증 시작",
        f'value="{rejected_id}"',
    )

    csv_bytes = b"order_id,region,amount\nR-1,Seoul,100\nR-2,Busan,200\n"
    upload_response = client.post(
        "/web/datasets/upload",
        data={
            "csrf_token": "dataset-resubmission-token",
            "accepted_terms": "on",
            "parent_dataset_id": str(rejected_id),
            "data_name": "Rejected Resubmission Source v2",
            "description": "보완된 컬럼 설명과 새 샘플을 포함한 재제출입니다.",
            "format": "CSV",
            "delimiter": ",",
            "file": (io.BytesIO(csv_bytes), "rejected_resubmission_v2.csv"),
        },
        content_type="multipart/form-data",
    )
    if upload_response.status_code != 302:
        raise AssertionError(f"resubmission upload should redirect, got {upload_response.status_code}")

    location = upload_response.headers.get("Location", "")
    job_id = location.rstrip("/").split("/")[-2]
    for _ in range(40):
        status_response = client.get(f"/web/uploads/{job_id}/status")
        payload = status_response.get_json()
        if payload and payload.get("status") == "DONE":
            break
        time.sleep(0.1)
    else:
        raise AssertionError("resubmission upload did not finish")

    seller_datasets = list_datasets_by_seller(seller["id"])
    linked = [
        dataset
        for dataset in seller_datasets
        if dataset.get("parent_dataset_id") == rejected_id
        and dataset.get("data_name") == "Rejected Resubmission Source v2"
    ]
    if not linked:
        raise AssertionError("resubmitted dataset was not linked to the rejected source")

    rejected_report = client.get(f"/web/datasets/{rejected_id}")
    if rejected_report.status_code != 200:
        raise AssertionError(f"rejected source report returned {rejected_report.status_code}")
    assert_contains(
        rejected_report.data.decode("utf-8"),
        "보완 제출 이력",
        "Rejected Resubmission Source v2",
    )

    child_report = client.get(f"/web/datasets/{linked[0]['id']}")
    if child_report.status_code != 200:
        raise AssertionError(f"resubmitted child report returned {child_report.status_code}")
    assert_contains(
        child_report.data.decode("utf-8"),
        "보완 제출 이력",
        "원본 반려 데이터",
        "컬럼 설명과 샘플 파일 보완이 필요합니다.",
    )

    print("DATASET_RESUBMISSION_TEST_PASS")


if __name__ == "__main__":
    main()
