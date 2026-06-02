from __future__ import annotations

import sqlite3
import sys
import time
import uuid
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from data_marketplace.database import get_schema_status, init_db, list_schema_migrations


def table_names(db_path: Path) -> set[str]:
    with sqlite3.connect(db_path) as connection:
        rows = connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()
    return {row[0] for row in rows}


def column_names(db_path: Path, table_name: str) -> set[str]:
    with sqlite3.connect(db_path) as connection:
        rows = connection.execute(f"PRAGMA table_info({table_name})").fetchall()
    return {row[1] for row in rows}


def main() -> None:
    db_path = PROJECT_ROOT / "database" / f"schema_migration_test_{uuid.uuid4().hex}.db"
    if db_path.exists():
        db_path.unlink()

    init_db(db_path)

    expected_tables = {
        "datasets",
        "dataset_columns",
        "dataset_reports",
        "dataset_row_hashes",
        "products",
        "users",
        "purchase_requests",
        "download_logs",
        "api_keys",
        "api_usage_logs",
        "audit_logs",
        "notifications",
        "dataset_processing_steps",
        "product_favorites",
        "orders",
        "payment_events",
        "schema_migrations",
    }
    missing_tables = expected_tables - table_names(db_path)
    if missing_tables:
        raise AssertionError(f"missing tables: {sorted(missing_tables)}")

    required_columns = {
        "datasets": {"seller_id", "data_name", "description", "review_note", "parent_dataset_id"},
        "products": {"category", "tags", "pricing_model", "license_name", "usage_terms"},
        "purchase_requests": {"review_note", "sample_download_limit"},
        "orders": {
            "purchase_request_id",
            "product_id",
            "buyer_id",
            "seller_id",
            "amount",
            "currency",
            "payment_status",
            "order_status",
            "payment_note",
            "payment_provider",
            "payment_reference",
            "paid_at",
            "canceled_at",
        },
        "payment_events": {"order_id", "event_type", "payment_status", "provider", "provider_reference", "detail_json"},
        "api_keys": {"total_request_limit", "monthly_request_limit"},
        "schema_migrations": {"version", "description", "applied_at"},
    }
    for table_name, expected_columns in required_columns.items():
        missing_columns = expected_columns - column_names(db_path, table_name)
        if missing_columns:
            raise AssertionError(f"{table_name} missing columns: {sorted(missing_columns)}")

    migrations = list_schema_migrations(db_path)
    status = get_schema_status(db_path)
    if len(migrations) < 11:
        raise AssertionError(f"migration records are missing: {migrations}")
    if not status["is_current"]:
        raise AssertionError(status)

    for _ in range(5):
        try:
            db_path.unlink()
            break
        except PermissionError:
            time.sleep(0.2)
    print("SCHEMA_MIGRATION_TEST_PASS")


if __name__ == "__main__":
    main()
