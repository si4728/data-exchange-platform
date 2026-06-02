from __future__ import annotations

import io
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app import app, bootstrap_admin
from data_marketplace.database import get_user_by_email


def main() -> None:
    bootstrap_admin()
    admin = get_user_by_email("admin@example.com")
    if admin is None:
        raise AssertionError("default admin account is missing")

    client = app.test_client()
    with client.session_transaction() as session:
        session["user_id"] = admin["id"]
        session["csrf_token"] = "upload-failure-token"

    malformed_csv = b"name,amount\nalpha,10\nbeta,20,unexpected\n"
    response = client.post(
        "/web/datasets/upload",
        data={
            "csrf_token": "upload-failure-token",
            "accepted_terms": "on",
            "data_name": "Malformed upload UX test",
            "description": "This intentionally malformed CSV should fail gracefully.",
            "format": "CSV",
            "delimiter": ",",
            "file": (io.BytesIO(malformed_csv), "malformed_upload.csv"),
        },
        content_type="multipart/form-data",
    )
    if response.status_code != 302:
        raise AssertionError(f"upload should redirect to processing page, got {response.status_code}")

    location = response.headers.get("Location", "")
    job_id = location.rstrip("/").split("/")[-2]
    status_payload = None
    for _ in range(30):
        status_response = client.get(f"/web/uploads/{job_id}/status")
        if status_response.status_code != 200:
            raise AssertionError(f"status endpoint returned {status_response.status_code}")
        status_payload = status_response.get_json()
        if status_payload["status"] == "FAILED":
            break
        time.sleep(0.1)

    if status_payload is None or status_payload["status"] != "FAILED":
        raise AssertionError(f"upload job should fail gracefully, got {status_payload}")
    if "파일 구조를 표 형식으로 읽을 수 없습니다." not in status_payload.get("error_title", ""):
        raise AssertionError(f"friendly error title is missing: {status_payload}")
    if "다시 업로드" not in status_payload.get("error_action", ""):
        raise AssertionError(f"friendly error action is missing: {status_payload}")

    processing_page = client.get(location)
    page_text = processing_page.data.decode("utf-8")
    for phrase in ["파일 구조를 표 형식으로 읽을 수 없습니다.", "다시 업로드", "내 대시보드"]:
        if phrase not in page_text:
            raise AssertionError(f"processing page missing phrase: {phrase}")

    print("UPLOAD_FAILURE_UX_TEST_PASS")


if __name__ == "__main__":
    main()
