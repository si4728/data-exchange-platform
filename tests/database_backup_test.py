from __future__ import annotations

import sys
from pathlib import Path

from werkzeug.security import generate_password_hash

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app import app, bootstrap_admin
from data_marketplace.database import create_user, get_user_by_email, list_audit_logs


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
        session["csrf_token"] = "database-backup-token"


def main() -> None:
    bootstrap_admin()
    admin = get_user_by_email("admin@example.com")
    if admin is None:
        raise AssertionError("default admin account is missing")
    user = get_or_create_user("database-backup-user@example.com", "Database Backup User")

    client = app.test_client()

    anonymous_response = client.get("/web/admin/database-backup.sqlite")
    if anonymous_response.status_code not in {302, 308}:
        raise AssertionError(f"anonymous backup access should redirect, got {anonymous_response.status_code}")

    login_as(client, user["id"])
    user_response = client.get("/web/admin/database-backup.sqlite")
    if user_response.status_code != 403:
        raise AssertionError(f"normal user backup access should be forbidden, got {user_response.status_code}")

    login_as(client, admin["id"])
    admin_response = client.get("/web/admin/database-backup.sqlite")
    if admin_response.status_code != 200:
        raise AssertionError(f"admin backup download returned {admin_response.status_code}")
    if admin_response.data[:16] != b"SQLite format 3\x00":
        raise AssertionError("backup response is not a SQLite database file")
    if "obdm_sqlite_backup_" not in admin_response.headers.get("Content-Disposition", ""):
        raise AssertionError("backup filename is missing from response headers")

    audit_logs = list_audit_logs(action="DATABASE_BACKUP_DOWNLOADED", actor_user_id=admin["id"])
    if not audit_logs:
        raise AssertionError("database backup audit log was not recorded")
    latest_log = audit_logs[0]
    if latest_log["target_type"] != "DATABASE":
        raise AssertionError(f"unexpected backup audit target type: {latest_log['target_type']}")
    if "obdm_sqlite_backup_" not in latest_log["detail_json"]:
        raise AssertionError("backup audit log does not include generated filename")

    print("DATABASE_BACKUP_TEST_PASS")


if __name__ == "__main__":
    main()
