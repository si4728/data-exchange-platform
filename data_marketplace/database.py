import json
import sqlite3
from pathlib import Path
from typing import Any

from data_marketplace.config import DATABASE_PATH


SCHEMA_MIGRATIONS = (
    ("0001_initial_mvp", "Initial dataset, product, user, purchase, API, audit, notification tables"),
    ("0002_marketplace_extensions", "Review notes, discovery metadata, processing steps, favorites, indexes"),
    ("0003_api_key_limits", "API key total and monthly request limits"),
    ("0004_sample_download_limits", "Purchase request sample download limits"),
    ("0005_product_license_and_orders", "Product license fields and order preparation table"),
    ("0006_order_payment_workflow", "Order payment workflow fields and status transitions"),
    ("0007_settlement_summary_view", "Seller settlement summary calculation"),
    ("0008_pricing_and_buyer_orders", "Product pricing model and buyer order views"),
    ("0009_admin_csv_exports", "Admin operational CSV report exports"),
    ("0010_dataset_resubmissions", "Seller rejected dataset resubmission tracking"),
    ("0011_payment_gateway_preparation", "Payment provider reference fields and event log"),
    ("0012_access_logs", "User login, logout, and failed access history"),
)


def get_connection(db_path: str | Path = DATABASE_PATH) -> sqlite3.Connection:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    return connection


def init_db(db_path: str | Path = DATABASE_PATH) -> None:
    with get_connection(db_path) as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS datasets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                seller_id INTEGER,
                filename TEXT,
                file_path TEXT,
                file_type TEXT,
                file_hash TEXT,
                row_count INTEGER,
                column_count INTEGER,
                quality_score REAL,
                pii_risk_score REAL,
                duplicate_status TEXT,
                status TEXT,
                parent_dataset_id INTEGER,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS dataset_columns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                dataset_id INTEGER,
                column_name TEXT,
                detected_type TEXT,
                null_count INTEGER,
                null_rate REAL,
                unique_count INTEGER
            );

            CREATE TABLE IF NOT EXISTS dataset_reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                dataset_id INTEGER,
                report_json TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS dataset_row_hashes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                dataset_id INTEGER,
                row_hash TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE INDEX IF NOT EXISTS idx_dataset_row_hashes_hash
            ON dataset_row_hashes(row_hash);

            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                dataset_id INTEGER UNIQUE,
                title TEXT,
                description TEXT,
                price INTEGER DEFAULT 0,
                pricing_model TEXT DEFAULT 'ONE_TIME',
                category TEXT,
                tags TEXT,
                license_name TEXT DEFAULT 'Standard Data License',
                usage_terms TEXT,
                status TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                email TEXT UNIQUE,
                password_hash TEXT,
                company TEXT,
                phone TEXT,
                role TEXT,
                status TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS purchase_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id INTEGER,
                buyer_id INTEGER,
                status TEXT,
                message TEXT,
                sample_download_limit INTEGER DEFAULT 5,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS download_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id INTEGER,
                user_id INTEGER,
                file_name TEXT,
                ip_address TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS api_keys (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                purchase_request_id INTEGER,
                product_id INTEGER,
                user_id INTEGER,
                token_hash TEXT UNIQUE,
                token_prefix TEXT,
                total_request_limit INTEGER DEFAULT 1000,
                monthly_request_limit INTEGER DEFAULT 300,
                status TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS api_usage_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                api_key_id INTEGER,
                product_id INTEGER,
                user_id INTEGER,
                endpoint TEXT,
                ip_address TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                purchase_request_id INTEGER UNIQUE,
                product_id INTEGER,
                buyer_id INTEGER,
                seller_id INTEGER,
                amount INTEGER DEFAULT 0,
                currency TEXT DEFAULT 'KRW',
                payment_status TEXT DEFAULT 'PENDING',
                order_status TEXT DEFAULT 'CREATED',
                payment_note TEXT,
                payment_provider TEXT DEFAULT 'MANUAL',
                payment_reference TEXT,
                paid_at DATETIME,
                canceled_at DATETIME,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS payment_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id INTEGER,
                event_type TEXT,
                payment_status TEXT,
                provider TEXT,
                provider_reference TEXT,
                detail_json TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS audit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                actor_user_id INTEGER,
                action TEXT,
                target_type TEXT,
                target_id INTEGER,
                detail_json TEXT,
                ip_address TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS access_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                email TEXT,
                event_type TEXT,
                failure_reason TEXT,
                ip_address TEXT,
                user_agent TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                recipient_user_id INTEGER,
                category TEXT,
                title TEXT,
                message TEXT,
                target_type TEXT,
                target_id INTEGER,
                read_at DATETIME,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS dataset_processing_steps (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id TEXT,
                dataset_id INTEGER,
                step_key TEXT,
                step_name TEXT,
                status TEXT,
                message TEXT,
                detail_json TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS product_favorites (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id INTEGER,
                user_id INTEGER,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(product_id, user_id)
            );

            CREATE TABLE IF NOT EXISTS schema_migrations (
                version TEXT PRIMARY KEY,
                description TEXT,
                applied_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        _ensure_column(connection, "datasets", "seller_id", "INTEGER")
        _ensure_column(connection, "datasets", "data_name", "TEXT")
        _ensure_column(connection, "datasets", "description", "TEXT")
        _ensure_column(connection, "datasets", "review_note", "TEXT")
        _ensure_column(connection, "datasets", "parent_dataset_id", "INTEGER")
        _ensure_column(connection, "products", "category", "TEXT")
        _ensure_column(connection, "products", "tags", "TEXT")
        _ensure_column(connection, "products", "pricing_model", "TEXT DEFAULT 'ONE_TIME'")
        _ensure_column(connection, "products", "license_name", "TEXT DEFAULT 'Standard Data License'")
        _ensure_column(connection, "products", "usage_terms", "TEXT")
        _ensure_column(connection, "purchase_requests", "review_note", "TEXT")
        _ensure_column(connection, "purchase_requests", "sample_download_limit", "INTEGER DEFAULT 5")
        _ensure_column(connection, "api_keys", "total_request_limit", "INTEGER DEFAULT 1000")
        _ensure_column(connection, "api_keys", "monthly_request_limit", "INTEGER DEFAULT 300")
        _ensure_column(connection, "orders", "payment_note", "TEXT")
        _ensure_column(connection, "orders", "payment_provider", "TEXT DEFAULT 'MANUAL'")
        _ensure_column(connection, "orders", "payment_reference", "TEXT")
        _ensure_column(connection, "orders", "paid_at", "DATETIME")
        _ensure_column(connection, "orders", "canceled_at", "DATETIME")
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_audit_logs_created_at ON audit_logs(created_at)"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_audit_logs_action ON audit_logs(action)"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_access_logs_created_at ON access_logs(created_at)"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_access_logs_user ON access_logs(user_id, created_at)"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_access_logs_event ON access_logs(event_type, created_at)"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_notifications_recipient ON notifications(recipient_user_id, read_at)"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_processing_steps_job ON dataset_processing_steps(job_id)"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_processing_steps_dataset ON dataset_processing_steps(dataset_id)"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_product_favorites_user ON product_favorites(user_id, created_at)"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_product_favorites_product ON product_favorites(product_id)"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_orders_seller ON orders(seller_id, payment_status)"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_orders_buyer ON orders(buyer_id, payment_status)"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_payment_events_order ON payment_events(order_id, created_at)"
        )
        _record_schema_migrations(connection)
        _backfill_product_discovery_fields(connection)
        _backfill_product_license_fields(connection)
        _backfill_product_pricing_fields(connection)


def _record_schema_migrations(connection: sqlite3.Connection) -> None:
    for version, description in SCHEMA_MIGRATIONS:
        connection.execute(
            """
            INSERT OR IGNORE INTO schema_migrations (version, description)
            VALUES (?, ?)
            """,
            (version, description),
        )


def _ensure_column(connection: sqlite3.Connection, table_name: str, column_name: str, column_type: str) -> None:
    columns = connection.execute(f"PRAGMA table_info({table_name})").fetchall()
    existing_columns = {column["name"] for column in columns}
    if column_name not in existing_columns:
        connection.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}")


def list_schema_migrations(db_path: str | Path = DATABASE_PATH) -> list[dict[str, Any]]:
    init_db(db_path)
    with get_connection(db_path) as connection:
        rows = connection.execute(
            """
            SELECT version, description, applied_at
            FROM schema_migrations
            ORDER BY version
            """
        ).fetchall()

    return [dict(row) for row in rows]


def get_schema_status(db_path: str | Path = DATABASE_PATH) -> dict[str, Any]:
    applied = list_schema_migrations(db_path)
    applied_versions = {migration["version"] for migration in applied}
    expected_versions = [version for version, _ in SCHEMA_MIGRATIONS]
    missing_versions = [version for version in expected_versions if version not in applied_versions]
    return {
        "expected_versions": expected_versions,
        "applied_versions": sorted(applied_versions),
        "missing_versions": missing_versions,
        "is_current": not missing_versions,
    }


def _backfill_product_discovery_fields(connection: sqlite3.Connection) -> None:
    rows = connection.execute(
        """
        SELECT
            products.id,
            products.category,
            products.tags,
            datasets.file_type,
            datasets.column_count,
            datasets.quality_score
        FROM products
        JOIN datasets ON datasets.id = products.dataset_id
        WHERE products.category IS NULL
           OR products.category = ''
           OR products.tags IS NULL
           OR products.tags = ''
        """
    ).fetchall()

    for row in rows:
        category = row["category"] or _category_from_file_type(row["file_type"])
        tags = row["tags"] or _tags_from_product_row(row)
        connection.execute(
            "UPDATE products SET category = ?, tags = ? WHERE id = ?",
            (category, tags, row["id"]),
        )


def _backfill_product_license_fields(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        UPDATE products
        SET license_name = 'Standard Data License'
        WHERE license_name IS NULL OR license_name = ''
        """
    )
    connection.execute(
        """
        UPDATE products
        SET usage_terms = ?
        WHERE usage_terms IS NULL OR usage_terms = ''
        """,
        (_default_usage_terms(),),
    )


def _backfill_product_pricing_fields(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        UPDATE products
        SET pricing_model = CASE
            WHEN COALESCE(price, 0) <= 0 THEN 'FREE'
            ELSE 'ONE_TIME'
        END
        WHERE pricing_model IS NULL OR pricing_model = ''
        """
    )


def _category_from_file_type(file_type: str | None) -> str:
    value = str(file_type or "").upper()
    if "JSON" in value:
        return "Document"
    if "PLAIN_TEXT" in value:
        return "Text"
    return "Tabular"


def _tags_from_product_row(row: sqlite3.Row) -> str:
    tags = []
    if row["file_type"]:
        tags.append(str(row["file_type"]))
    if row["quality_score"] is not None:
        tags.append(f"quality-{round(float(row['quality_score']))}")
    if row["column_count"]:
        tags.append(f"{row['column_count']}-columns")
    return ", ".join(dict.fromkeys(tags))


def _normalize_pricing_model(pricing_model: str | None, price: int | float | None = None) -> str:
    value = str(pricing_model or "").strip().upper()
    if value not in {"FREE", "ONE_TIME"}:
        value = "FREE" if int(price or 0) <= 0 else "ONE_TIME"
    return value


def file_hash_exists(file_hash: str, db_path: str | Path = DATABASE_PATH) -> bool:
    init_db(db_path)
    with get_connection(db_path) as connection:
        row = connection.execute(
            "SELECT id FROM datasets WHERE file_hash = ? LIMIT 1",
            (file_hash,),
        ).fetchone()
    return row is not None


def find_existing_row_hashes(row_hashes: list[str], db_path: str | Path = DATABASE_PATH) -> set[str]:
    init_db(db_path)
    unique_hashes = sorted(set(row_hashes))
    if not unique_hashes:
        return set()

    existing_hashes: set[str] = set()
    batch_size = 900

    with get_connection(db_path) as connection:
        for index in range(0, len(unique_hashes), batch_size):
            batch = unique_hashes[index : index + batch_size]
            placeholders = ",".join("?" for _ in batch)
            rows = connection.execute(
                f"SELECT DISTINCT row_hash FROM dataset_row_hashes WHERE row_hash IN ({placeholders})",
                batch,
            ).fetchall()
            existing_hashes.update(row["row_hash"] for row in rows)

    return existing_hashes


def save_dataset_row_hashes(
    dataset_id: int,
    row_hashes: list[str],
    db_path: str | Path = DATABASE_PATH,
) -> None:
    init_db(db_path)
    unique_hashes = sorted(set(row_hashes))
    if not unique_hashes:
        return

    with get_connection(db_path) as connection:
        connection.executemany(
            "INSERT INTO dataset_row_hashes (dataset_id, row_hash) VALUES (?, ?)",
            [(dataset_id, row_hash) for row_hash in unique_hashes],
        )


def save_validation_result(report: dict[str, Any], db_path: str | Path = DATABASE_PATH) -> int:
    init_db(db_path)
    schema = report["schema"]
    pii = report["pii"]

    with get_connection(db_path) as connection:
        cursor = connection.execute(
            """
            INSERT INTO datasets (
                seller_id,
                data_name,
                description,
                filename,
                file_path,
                file_type,
                file_hash,
                row_count,
                column_count,
                quality_score,
                pii_risk_score,
                duplicate_status,
                status,
                parent_dataset_id
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                report["metadata"].get("seller_id"),
                report["metadata"]["data_name"],
                report["metadata"]["description"],
                report["format"]["filename"],
                report.get("retention", {}).get("stored_file_path"),
                report["format"]["detected_format"],
                report["duplicate"]["file_hash"],
                schema["row_count"],
                schema["column_count"],
                report["quality"]["score"],
                pii["pii_risk_score"],
                report["duplicate"]["status"],
                report["status"],
                report["metadata"].get("parent_dataset_id"),
            ),
        )
        dataset_id = int(cursor.lastrowid)

        for column in schema["columns"]:
            connection.execute(
                """
                INSERT INTO dataset_columns (
                    dataset_id,
                    column_name,
                    detected_type,
                    null_count,
                    null_rate,
                    unique_count
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    dataset_id,
                    column["column_name"],
                    column["detected_type"],
                    column["null_count"],
                    column["null_rate"],
                    column["unique_count"],
                ),
            )

        connection.execute(
            "INSERT INTO dataset_reports (dataset_id, report_json) VALUES (?, ?)",
            (dataset_id, json.dumps(report, ensure_ascii=False)),
        )

    return dataset_id


def update_report_json(dataset_id: int, report: dict[str, Any], db_path: str | Path = DATABASE_PATH) -> None:
    init_db(db_path)
    with get_connection(db_path) as connection:
        connection.execute(
            """
            UPDATE dataset_reports
            SET report_json = ?
            WHERE dataset_id = ?
            """,
            (json.dumps(report, ensure_ascii=False), dataset_id),
        )


def list_datasets(
    query: str | None = None,
    status: str | None = None,
    duplicate_status: str | None = None,
    min_quality_score: float | None = None,
    max_quality_score: float | None = None,
    min_pii_risk_score: float | None = None,
    max_pii_risk_score: float | None = None,
    db_path: str | Path = DATABASE_PATH,
) -> list[dict[str, Any]]:
    init_db(db_path)
    conditions = []
    params: list[Any] = []

    if query:
        like_query = f"%{query.strip()}%"
        conditions.append(
            """
            (
                data_name LIKE ?
                OR description LIKE ?
                OR filename LIKE ?
                OR file_type LIKE ?
                OR duplicate_status LIKE ?
            )
            """
        )
        params.extend([like_query, like_query, like_query, like_query, like_query])

    if status:
        conditions.append("status = ?")
        params.append(status)

    if duplicate_status:
        conditions.append("duplicate_status = ?")
        params.append(duplicate_status)

    if min_quality_score is not None:
        conditions.append("quality_score >= ?")
        params.append(min_quality_score)

    if max_quality_score is not None:
        conditions.append("quality_score <= ?")
        params.append(max_quality_score)

    if min_pii_risk_score is not None:
        conditions.append("pii_risk_score >= ?")
        params.append(min_pii_risk_score)

    if max_pii_risk_score is not None:
        conditions.append("pii_risk_score <= ?")
        params.append(max_pii_risk_score)

    where_clause = ""
    if conditions:
        where_clause = "WHERE " + " AND ".join(conditions)

    with get_connection(db_path) as connection:
        rows = connection.execute(
            f"""
            SELECT
                id,
                seller_id,
                data_name,
                description,
                filename,
                file_type,
                row_count,
                column_count,
                quality_score,
                pii_risk_score,
                duplicate_status,
                status,
                review_note,
                parent_dataset_id,
                created_at
            FROM datasets
            {where_clause}
            ORDER BY id DESC
            """,
            params,
        ).fetchall()

    return [dict(row) for row in rows]


def list_datasets_by_seller(seller_id: int, db_path: str | Path = DATABASE_PATH) -> list[dict[str, Any]]:
    init_db(db_path)
    with get_connection(db_path) as connection:
        rows = connection.execute(
            """
            SELECT
                datasets.id,
                datasets.seller_id,
                datasets.data_name,
                datasets.description,
                datasets.filename,
                datasets.file_type,
                datasets.row_count,
                datasets.column_count,
                datasets.quality_score,
                datasets.pii_risk_score,
                datasets.duplicate_status,
                datasets.status,
                datasets.review_note,
                datasets.parent_dataset_id,
                datasets.created_at,
                products.id AS product_id
            FROM datasets
            LEFT JOIN products ON products.dataset_id = datasets.id
            WHERE datasets.seller_id = ?
            ORDER BY datasets.id DESC
            """,
            (seller_id,),
        ).fetchall()

    return [dict(row) for row in rows]


def get_dataset_summary(dataset_id: int, db_path: str | Path = DATABASE_PATH) -> dict[str, Any] | None:
    init_db(db_path)
    with get_connection(db_path) as connection:
        row = connection.execute(
            """
            SELECT
                datasets.id,
                datasets.seller_id,
                datasets.data_name,
                datasets.description,
                datasets.filename,
                datasets.status,
                datasets.review_note,
                datasets.parent_dataset_id,
                products.id AS product_id
            FROM datasets
            LEFT JOIN products ON products.dataset_id = datasets.id
            WHERE datasets.id = ?
            """,
            (dataset_id,),
        ).fetchone()

    return dict(row) if row else None


def dataset_is_published(dataset_id: int, db_path: str | Path = DATABASE_PATH) -> bool:
    summary = get_dataset_summary(dataset_id, db_path)
    return bool(summary and summary.get("product_id"))


def update_dataset_metadata(
    dataset_id: int,
    data_name: str,
    description: str,
    db_path: str | Path = DATABASE_PATH,
) -> bool:
    init_db(db_path)
    with get_connection(db_path) as connection:
        cursor = connection.execute(
            """
            UPDATE datasets
            SET data_name = ?, description = ?
            WHERE id = ?
            """,
            (data_name, description, dataset_id),
        )

    if cursor.rowcount == 0:
        return False

    report = get_dataset_report(dataset_id, db_path)
    if report is not None:
        report.setdefault("metadata", {})
        report["metadata"]["data_name"] = data_name
        report["metadata"]["description"] = description
        update_report_json(dataset_id, report, db_path)
        report_path = report.get("report_path")
        if report_path:
            Path(report_path).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    return True


def get_dataset_report(dataset_id: int, db_path: str | Path = DATABASE_PATH) -> dict[str, Any] | None:
    init_db(db_path)
    with get_connection(db_path) as connection:
        row = connection.execute(
            """
            SELECT report_json
            FROM dataset_reports
            WHERE dataset_id = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (dataset_id,),
        ).fetchone()

    if row is None:
        return None

    return json.loads(row["report_json"])


def update_dataset_status(
    dataset_id: int,
    status: str,
    review_note: str = "",
    db_path: str | Path = DATABASE_PATH,
) -> bool:
    init_db(db_path)
    with get_connection(db_path) as connection:
        cursor = connection.execute(
            "UPDATE datasets SET status = ?, review_note = ? WHERE id = ?",
            (status, review_note, dataset_id),
        )

    return cursor.rowcount > 0


def deactivate_product_for_dataset(dataset_id: int, db_path: str | Path = DATABASE_PATH) -> None:
    init_db(db_path)
    with get_connection(db_path) as connection:
        connection.execute(
            "UPDATE products SET status = 'INACTIVE' WHERE dataset_id = ?",
            (dataset_id,),
        )


def create_product_from_dataset(
    dataset_id: int,
    title: str | None = None,
    description: str | None = None,
    price: int = 0,
    category: str | None = None,
    tags: str | None = None,
    db_path: str | Path = DATABASE_PATH,
) -> dict[str, Any]:
    init_db(db_path)
    report = get_dataset_report(dataset_id, db_path)
    if report is None:
        raise ValueError("dataset not found")

    with get_connection(db_path) as connection:
        dataset = connection.execute(
            "SELECT id, data_name, description, filename, status FROM datasets WHERE id = ?",
            (dataset_id,),
        ).fetchone()

        if dataset is None:
            raise ValueError("dataset not found")
        if dataset["status"] != "APPROVED":
            raise ValueError("only approved datasets can be registered as products")

        product_title = title or dataset["data_name"] or dataset["filename"]
        product_description = description or dataset["description"] or _build_default_product_description(report)
        product_category = _normalize_product_category(category, report)
        product_tags = _normalize_product_tags(tags, report)
        product_price = max(0, int(price))
        pricing_model = "FREE" if product_price == 0 else "ONE_TIME"

        connection.execute(
            """
            INSERT INTO products (dataset_id, title, description, price, pricing_model, category, tags, license_name, usage_terms, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'Standard Data License', ?, 'ACTIVE')
            ON CONFLICT(dataset_id) DO UPDATE SET
                title = excluded.title,
                description = excluded.description,
                price = excluded.price,
                pricing_model = excluded.pricing_model,
                category = COALESCE(products.category, excluded.category),
                tags = COALESCE(products.tags, excluded.tags),
                status = 'ACTIVE'
            """,
            (
                dataset_id,
                product_title,
                product_description,
                product_price,
                pricing_model,
                product_category,
                product_tags,
                _default_usage_terms(),
            ),
        )

        product = connection.execute(
            """
            SELECT id, dataset_id, title, description, price, pricing_model, category, tags, status, created_at
            FROM products
            WHERE dataset_id = ?
            """,
            (dataset_id,),
        ).fetchone()

    return dict(product)


def sync_approved_datasets_to_products(db_path: str | Path = DATABASE_PATH) -> dict[str, Any]:
    init_db(db_path)
    with get_connection(db_path) as connection:
        rows = connection.execute(
            """
            SELECT datasets.id
            FROM datasets
            LEFT JOIN products ON products.dataset_id = datasets.id
            WHERE datasets.status = 'APPROVED' AND products.id IS NULL
            ORDER BY datasets.id
            """
        ).fetchall()

    created = []
    for row in rows:
        product = create_product_from_dataset(int(row["id"]), db_path=db_path)
        created.append(product["id"])

    return {
        "created_count": len(created),
        "created_product_ids": created,
    }


def list_products(
    query: str | None = None,
    category: str | None = None,
    tag: str | None = None,
    file_type: str | None = None,
    min_quality_score: float | None = None,
    max_pii_risk_score: float | None = None,
    status: str | None = "ACTIVE",
    sort: str = "newest",
    page: int = 1,
    per_page: int = 12,
    include_total: bool = False,
    db_path: str | Path = DATABASE_PATH,
) -> list[dict[str, Any]] | dict[str, Any]:
    init_db(db_path)
    params: list[Any] = []
    where_clause = "datasets.status = 'APPROVED'"

    if status:
        where_clause += " AND products.status = ?"
        params.append(status)

    if query:
        like_query = f"%{query.strip()}%"
        where_clause += """
            AND (
                products.title LIKE ?
                OR products.description LIKE ?
                OR products.category LIKE ?
                OR products.tags LIKE ?
                OR datasets.data_name LIKE ?
                OR datasets.description LIKE ?
                OR datasets.file_type LIKE ?
            )
        """
        params.extend([like_query, like_query, like_query, like_query, like_query, like_query, like_query])

    if category:
        where_clause += " AND products.category = ?"
        params.append(category.strip())

    if tag:
        where_clause += " AND products.tags LIKE ?"
        params.append(f"%{tag.strip()}%")

    if file_type:
        where_clause += " AND datasets.file_type = ?"
        params.append(file_type)

    if min_quality_score is not None:
        where_clause += " AND datasets.quality_score >= ?"
        params.append(min_quality_score)

    if max_pii_risk_score is not None:
        where_clause += " AND datasets.pii_risk_score <= ?"
        params.append(max_pii_risk_score)

    order_by = _product_sort_clause(sort)
    page = max(1, int(page or 1))
    per_page = max(1, min(int(per_page or 12), 60))
    offset = (page - 1) * per_page

    with get_connection(db_path) as connection:
        total = connection.execute(
            f"""
            SELECT COUNT(*) AS count
            FROM products
            JOIN datasets ON datasets.id = products.dataset_id
            WHERE {where_clause}
            """,
            params,
        ).fetchone()["count"]
        rows = connection.execute(
            f"""
            SELECT
                products.id,
                products.dataset_id,
                products.title,
                products.description,
                products.price,
                products.pricing_model,
                products.category,
                products.tags,
                products.license_name,
                products.usage_terms,
                products.status,
                products.created_at,
                datasets.file_type,
                datasets.seller_id,
                datasets.data_name,
                datasets.row_count,
                datasets.column_count,
                datasets.quality_score,
                datasets.pii_risk_score
            FROM products
            JOIN datasets ON datasets.id = products.dataset_id
            WHERE {where_clause}
            ORDER BY {order_by}
            LIMIT ? OFFSET ?
            """,
            [*params, per_page, offset],
        ).fetchall()

    products = [dict(row) for row in rows]
    if not include_total:
        return products

    total_pages = max(1, (int(total) + per_page - 1) // per_page)
    return {
        "items": products,
        "total": int(total),
        "page": page,
        "per_page": per_page,
        "total_pages": total_pages,
        "has_prev": page > 1,
        "has_next": page < total_pages,
    }


def _product_sort_clause(sort: str) -> str:
    sort_map = {
        "newest": "products.id DESC",
        "oldest": "products.id ASC",
        "quality_desc": "datasets.quality_score DESC, products.id DESC",
        "quality_asc": "datasets.quality_score ASC, products.id DESC",
        "rows_desc": "datasets.row_count DESC, products.id DESC",
        "rows_asc": "datasets.row_count ASC, products.id DESC",
        "price_desc": "products.price DESC, products.id DESC",
        "price_asc": "products.price ASC, products.id DESC",
        "title_asc": "products.title COLLATE NOCASE ASC, products.id DESC",
    }
    return sort_map.get(sort or "newest", sort_map["newest"])


def get_product(
    product_id: int,
    db_path: str | Path = DATABASE_PATH,
    include_inactive: bool = False,
) -> dict[str, Any] | None:
    init_db(db_path)
    status_clause = "" if include_inactive else "AND products.status = 'ACTIVE'"
    with get_connection(db_path) as connection:
        row = connection.execute(
            f"""
            SELECT
                products.id,
                products.dataset_id,
                products.title,
                products.description,
                products.price,
                products.pricing_model,
                products.category,
                products.tags,
                products.license_name,
                products.usage_terms,
                products.status,
                products.created_at,
                datasets.file_type,
                datasets.seller_id,
                datasets.data_name,
                datasets.row_count,
                datasets.column_count,
                datasets.quality_score,
                datasets.pii_risk_score
            FROM products
            JOIN datasets ON datasets.id = products.dataset_id
            WHERE products.id = ? {status_clause}
            """,
            (product_id,),
        ).fetchone()

    if row is None:
        return None

    product = dict(row)
    product["report"] = get_dataset_report(product["dataset_id"], db_path)
    return product


def update_product(
    product_id: int,
    title: str,
    description: str,
    price: int,
    category: str = "",
    tags: str = "",
    license_name: str = "Standard Data License",
    usage_terms: str = "",
    pricing_model: str = "ONE_TIME",
    db_path: str | Path = DATABASE_PATH,
) -> bool:
    init_db(db_path)
    normalized_pricing_model = _normalize_pricing_model(pricing_model, price)
    normalized_price = 0 if normalized_pricing_model == "FREE" else max(0, int(price))
    with get_connection(db_path) as connection:
        cursor = connection.execute(
            """
            UPDATE products
            SET title = ?, description = ?, price = ?, pricing_model = ?, category = ?, tags = ?, license_name = ?, usage_terms = ?
            WHERE id = ?
            """,
            (
                title,
                description,
                normalized_price,
                normalized_pricing_model,
                category.strip(),
                tags.strip(),
                license_name.strip() or "Standard Data License",
                usage_terms.strip() or _default_usage_terms(),
                product_id,
            ),
        )

    return cursor.rowcount > 0


def update_product_status(
    product_id: int,
    status: str,
    db_path: str | Path = DATABASE_PATH,
) -> bool:
    init_db(db_path)
    with get_connection(db_path) as connection:
        cursor = connection.execute(
            "UPDATE products SET status = ? WHERE id = ?",
            (status, product_id),
        )

    return cursor.rowcount > 0


def add_product_favorite(
    product_id: int,
    user_id: int,
    db_path: str | Path = DATABASE_PATH,
) -> bool:
    init_db(db_path)
    with get_connection(db_path) as connection:
        cursor = connection.execute(
            """
            INSERT OR IGNORE INTO product_favorites (product_id, user_id)
            VALUES (?, ?)
            """,
            (product_id, user_id),
        )

    return cursor.rowcount > 0


def remove_product_favorite(
    product_id: int,
    user_id: int,
    db_path: str | Path = DATABASE_PATH,
) -> bool:
    init_db(db_path)
    with get_connection(db_path) as connection:
        cursor = connection.execute(
            "DELETE FROM product_favorites WHERE product_id = ? AND user_id = ?",
            (product_id, user_id),
        )

    return cursor.rowcount > 0


def is_product_favorited(
    product_id: int,
    user_id: int,
    db_path: str | Path = DATABASE_PATH,
) -> bool:
    init_db(db_path)
    with get_connection(db_path) as connection:
        row = connection.execute(
            """
            SELECT 1
            FROM product_favorites
            WHERE product_id = ? AND user_id = ?
            """,
            (product_id, user_id),
        ).fetchone()

    return row is not None


def list_favorite_product_ids(
    user_id: int,
    db_path: str | Path = DATABASE_PATH,
) -> set[int]:
    init_db(db_path)
    with get_connection(db_path) as connection:
        rows = connection.execute(
            "SELECT product_id FROM product_favorites WHERE user_id = ?",
            (user_id,),
        ).fetchall()

    return {int(row["product_id"]) for row in rows}


def list_favorite_products(
    user_id: int,
    db_path: str | Path = DATABASE_PATH,
) -> list[dict[str, Any]]:
    init_db(db_path)
    with get_connection(db_path) as connection:
        rows = connection.execute(
            """
            SELECT
                product_favorites.id AS favorite_id,
                product_favorites.created_at AS favorited_at,
                products.id,
                products.dataset_id,
                products.title,
                products.description,
                products.price,
                products.category,
                products.tags,
                products.status,
                products.created_at,
                datasets.file_type,
                datasets.seller_id,
                datasets.row_count,
                datasets.column_count,
                datasets.quality_score
            FROM product_favorites
            JOIN products ON products.id = product_favorites.product_id
            JOIN datasets ON datasets.id = products.dataset_id
            WHERE product_favorites.user_id = ?
              AND datasets.status = 'APPROVED'
            ORDER BY product_favorites.id DESC
            """,
            (user_id,),
        ).fetchall()

    return [dict(row) for row in rows]


def create_user(
    name: str,
    email: str,
    password_hash: str,
    company: str = "",
    phone: str = "",
    role: str = "USER",
    status: str = "PENDING",
    db_path: str | Path = DATABASE_PATH,
) -> dict[str, Any]:
    init_db(db_path)
    with get_connection(db_path) as connection:
        cursor = connection.execute(
            """
            INSERT INTO users (name, email, password_hash, company, phone, role, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (name, email.lower(), password_hash, company, phone, role, status),
        )
        user_id = int(cursor.lastrowid)

    user = get_user_by_id(user_id, db_path)
    if user is None:
        raise ValueError("user creation failed")
    return user


def get_user_by_email(email: str, db_path: str | Path = DATABASE_PATH) -> dict[str, Any] | None:
    init_db(db_path)
    with get_connection(db_path) as connection:
        row = connection.execute(
            "SELECT * FROM users WHERE email = ?",
            (email.lower(),),
        ).fetchone()

    return dict(row) if row else None


def get_user_by_id(user_id: int, db_path: str | Path = DATABASE_PATH) -> dict[str, Any] | None:
    init_db(db_path)
    with get_connection(db_path) as connection:
        row = connection.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()

    return dict(row) if row else None


def list_users(
    query: str = "",
    role: str | None = None,
    status: str | None = None,
    limit: int = 500,
    db_path: str | Path = DATABASE_PATH,
) -> list[dict[str, Any]]:
    init_db(db_path)
    limit = max(1, min(int(limit or 500), 1000))
    clauses: list[str] = []
    params: list[Any] = []
    if query:
        like = f"%{query}%"
        clauses.append("(name LIKE ? OR email LIKE ? OR company LIKE ? OR phone LIKE ?)")
        params.extend([like, like, like, like])
    if role:
        clauses.append("role = ?")
        params.append(role)
    if status:
        clauses.append("status = ?")
        params.append(status)

    where_clause = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    with get_connection(db_path) as connection:
        rows = connection.execute(
            f"""
            SELECT
                id,
                name,
                email,
                company,
                phone,
                role,
                status,
                created_at,
                (
                    SELECT COUNT(*)
                    FROM datasets
                    WHERE datasets.seller_id = users.id
                ) AS dataset_count,
                (
                    SELECT COUNT(*)
                    FROM products
                    JOIN datasets ON datasets.id = products.dataset_id
                    WHERE datasets.seller_id = users.id
                ) AS product_count,
                (
                    SELECT COUNT(*)
                    FROM purchase_requests
                    WHERE purchase_requests.buyer_id = users.id
                ) AS purchase_request_count,
                (
                    SELECT MAX(created_at)
                    FROM access_logs
                    WHERE access_logs.user_id = users.id
                      AND access_logs.event_type = 'LOGIN_SUCCESS'
                ) AS last_login_at,
                (
                    SELECT COUNT(*)
                    FROM access_logs
                    WHERE access_logs.user_id = users.id
                      AND access_logs.event_type = 'LOGIN_FAIL'
                ) AS login_fail_count
            FROM users
            {where_clause}
            ORDER BY id DESC
            LIMIT ?
            """,
            [*params, limit],
        ).fetchall()

    return [dict(row) for row in rows]


def list_admin_user_ids(db_path: str | Path = DATABASE_PATH) -> list[int]:
    init_db(db_path)
    with get_connection(db_path) as connection:
        rows = connection.execute(
            """
            SELECT id
            FROM users
            WHERE role = 'ADMIN' AND status = 'ACTIVE'
            ORDER BY id
            """
        ).fetchall()

    return [int(row["id"]) for row in rows]


def update_user_status(user_id: int, status: str, db_path: str | Path = DATABASE_PATH) -> bool:
    init_db(db_path)
    with get_connection(db_path) as connection:
        cursor = connection.execute("UPDATE users SET status = ? WHERE id = ?", (status, user_id))

    return cursor.rowcount > 0


def update_user_role(user_id: int, role: str, db_path: str | Path = DATABASE_PATH) -> bool:
    init_db(db_path)
    with get_connection(db_path) as connection:
        cursor = connection.execute("UPDATE users SET role = ? WHERE id = ?", (role, user_id))

    return cursor.rowcount > 0


def create_purchase_request(
    product_id: int,
    buyer_id: int,
    message: str = "",
    db_path: str | Path = DATABASE_PATH,
) -> dict[str, Any]:
    init_db(db_path)
    with get_connection(db_path) as connection:
        existing = connection.execute(
            """
            SELECT id FROM purchase_requests
            WHERE product_id = ? AND buyer_id = ? AND status IN ('REQUESTED', 'APPROVED', 'COMPLETED')
            LIMIT 1
            """,
            (product_id, buyer_id),
        ).fetchone()
        if existing:
            request_id = int(existing["id"])
        else:
            cursor = connection.execute(
                """
                INSERT INTO purchase_requests (product_id, buyer_id, status, message)
                VALUES (?, ?, 'REQUESTED', ?)
                """,
                (product_id, buyer_id, message),
            )
            request_id = int(cursor.lastrowid)

    purchase = get_purchase_request(request_id, db_path)
    if purchase is None:
        raise ValueError("purchase request creation failed")
    return purchase


def get_purchase_request(request_id: int, db_path: str | Path = DATABASE_PATH) -> dict[str, Any] | None:
    init_db(db_path)
    with get_connection(db_path) as connection:
        row = connection.execute(
            """
            SELECT
                purchase_requests.*,
                products.title AS product_title,
                products.price AS product_price,
                products.status AS product_status,
                datasets.seller_id AS seller_id,
                datasets.file_type AS file_type,
                datasets.row_count AS row_count,
                datasets.column_count AS column_count,
                datasets.quality_score AS quality_score,
                users.name AS buyer_name,
                users.email AS buyer_email
            FROM purchase_requests
            JOIN products ON products.id = purchase_requests.product_id
            JOIN datasets ON datasets.id = products.dataset_id
            JOIN users ON users.id = purchase_requests.buyer_id
            WHERE purchase_requests.id = ?
            """,
            (request_id,),
        ).fetchone()

    return dict(row) if row else None


def get_purchase_request_by_product_buyer(
    product_id: int,
    buyer_id: int,
    db_path: str | Path = DATABASE_PATH,
) -> dict[str, Any] | None:
    init_db(db_path)
    with get_connection(db_path) as connection:
        row = connection.execute(
            """
            SELECT
                purchase_requests.*,
                products.title AS product_title,
                products.price AS product_price,
                products.status AS product_status
            FROM purchase_requests
            JOIN products ON products.id = purchase_requests.product_id
            WHERE purchase_requests.product_id = ? AND purchase_requests.buyer_id = ?
            ORDER BY purchase_requests.id DESC
            LIMIT 1
            """,
            (product_id, buyer_id),
        ).fetchone()

    return dict(row) if row else None


def user_has_approved_purchase(
    product_id: int,
    buyer_id: int,
    db_path: str | Path = DATABASE_PATH,
) -> bool:
    init_db(db_path)
    with get_connection(db_path) as connection:
        row = connection.execute(
            """
            SELECT purchase_requests.id
            FROM purchase_requests
            JOIN products ON products.id = purchase_requests.product_id
            LEFT JOIN orders ON orders.purchase_request_id = purchase_requests.id
            WHERE purchase_requests.product_id = ?
              AND purchase_requests.buyer_id = ?
              AND (
                  (COALESCE(products.price, 0) <= 0 AND purchase_requests.status IN ('APPROVED', 'COMPLETED'))
                  OR purchase_requests.status = 'COMPLETED'
                  OR orders.payment_status = 'PAID'
              )
            LIMIT 1
            """,
            (product_id, buyer_id),
        ).fetchone()

    return row is not None


def purchase_request_has_data_access(
    request_id: int,
    db_path: str | Path = DATABASE_PATH,
) -> bool:
    init_db(db_path)
    with get_connection(db_path) as connection:
        row = connection.execute(
            """
            SELECT purchase_requests.id
            FROM purchase_requests
            JOIN products ON products.id = purchase_requests.product_id
            LEFT JOIN orders ON orders.purchase_request_id = purchase_requests.id
            WHERE purchase_requests.id = ?
              AND (
                  (COALESCE(products.price, 0) <= 0 AND purchase_requests.status IN ('APPROVED', 'COMPLETED'))
                  OR purchase_requests.status = 'COMPLETED'
                  OR orders.payment_status = 'PAID'
              )
            LIMIT 1
            """,
            (request_id,),
        ).fetchone()

    return row is not None


def get_sample_download_summary(
    product_id: int,
    user_id: int,
    db_path: str | Path = DATABASE_PATH,
) -> dict[str, Any]:
    init_db(db_path)
    with get_connection(db_path) as connection:
        purchase = connection.execute(
            """
            SELECT purchase_requests.id, purchase_requests.sample_download_limit, purchase_requests.status
            FROM purchase_requests
            JOIN products ON products.id = purchase_requests.product_id
            LEFT JOIN orders ON orders.purchase_request_id = purchase_requests.id
            WHERE purchase_requests.product_id = ?
              AND purchase_requests.buyer_id = ?
              AND (
                  (COALESCE(products.price, 0) <= 0 AND purchase_requests.status IN ('APPROVED', 'COMPLETED'))
                  OR purchase_requests.status = 'COMPLETED'
                  OR orders.payment_status = 'PAID'
              )
            ORDER BY purchase_requests.id DESC
            LIMIT 1
            """,
            (product_id, user_id),
        ).fetchone()
        download_count = connection.execute(
            """
            SELECT COUNT(*) AS count
            FROM download_logs
            WHERE product_id = ? AND user_id = ?
            """,
            (product_id, user_id),
        ).fetchone()["count"]

    if purchase is None:
        return {
            "purchase_request_id": None,
            "download_count": int(download_count),
            "sample_download_limit": 0,
            "remaining_downloads": 0,
            "is_exceeded": True,
            "reason": "payment completion is required for paid products",
        }

    limit = int(purchase["sample_download_limit"] or 0)
    remaining = max(0, limit - int(download_count))
    return {
        "purchase_request_id": int(purchase["id"]),
        "download_count": int(download_count),
        "sample_download_limit": limit,
        "remaining_downloads": remaining,
        "is_exceeded": remaining <= 0,
        "reason": "sample download limit exceeded" if remaining <= 0 else "",
    }


def update_purchase_download_limit(
    request_id: int,
    sample_download_limit: int,
    db_path: str | Path = DATABASE_PATH,
) -> bool:
    init_db(db_path)
    with get_connection(db_path) as connection:
        cursor = connection.execute(
            "UPDATE purchase_requests SET sample_download_limit = ? WHERE id = ?",
            (max(0, int(sample_download_limit)), request_id),
        )

    return cursor.rowcount > 0


def create_order_for_purchase(
    request_id: int,
    db_path: str | Path = DATABASE_PATH,
) -> dict[str, Any] | None:
    init_db(db_path)
    purchase = get_purchase_request(request_id, db_path)
    if purchase is None or purchase["status"] not in {"APPROVED", "COMPLETED"}:
        return None

    with get_connection(db_path) as connection:
        existing = connection.execute(
            "SELECT * FROM orders WHERE purchase_request_id = ?",
            (request_id,),
        ).fetchone()
        if existing:
            return dict(existing)

        cursor = connection.execute(
            """
            INSERT INTO orders (
                purchase_request_id,
                product_id,
                buyer_id,
                seller_id,
                amount,
                currency,
                payment_status,
                order_status
            )
            VALUES (?, ?, ?, ?, ?, 'KRW', 'PENDING', 'CREATED')
            """,
            (
                request_id,
                purchase["product_id"],
                purchase["buyer_id"],
                purchase["seller_id"],
                int(purchase["product_price"] or 0),
            ),
        )
        order_id = int(cursor.lastrowid)
        row = connection.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()

    return dict(row) if row else None


def get_order(
    order_id: int,
    db_path: str | Path = DATABASE_PATH,
) -> dict[str, Any] | None:
    orders = list_orders(db_path=db_path)
    for order in orders:
        if int(order["id"]) == int(order_id):
            return order
    return None


def get_order_by_purchase_request(
    request_id: int,
    db_path: str | Path = DATABASE_PATH,
) -> dict[str, Any] | None:
    init_db(db_path)
    with get_connection(db_path) as connection:
        row = connection.execute(
            """
            SELECT
                orders.*,
                products.title AS product_title,
                buyer.name AS buyer_name,
                buyer.email AS buyer_email,
                seller.name AS seller_name,
                seller.email AS seller_email,
                purchase_requests.status AS purchase_status,
                api_keys.id AS api_key_id,
                api_keys.token_prefix AS api_key_prefix,
                api_keys.status AS api_key_status
            FROM orders
            JOIN products ON products.id = orders.product_id
            JOIN purchase_requests ON purchase_requests.id = orders.purchase_request_id
            LEFT JOIN api_keys
                ON api_keys.purchase_request_id = orders.purchase_request_id
               AND api_keys.status = 'ACTIVE'
            JOIN users AS buyer ON buyer.id = orders.buyer_id
            JOIN users AS seller ON seller.id = orders.seller_id
            WHERE orders.purchase_request_id = ?
            """,
            (request_id,),
        ).fetchone()

    return dict(row) if row else None


def update_order_payment_status(
    order_id: int,
    payment_status: str,
    payment_note: str = "",
    payment_provider: str = "MANUAL",
    payment_reference: str = "",
    event_type: str = "PAYMENT_STATUS_UPDATED",
    detail: dict[str, Any] | None = None,
    db_path: str | Path = DATABASE_PATH,
) -> dict[str, Any] | None:
    init_db(db_path)
    normalized_status = payment_status.strip().upper()
    allowed_statuses = {"PENDING", "PAYMENT_REQUESTED", "PAID", "FAILED", "CANCELED"}
    if normalized_status not in allowed_statuses:
        raise ValueError(f"Unsupported payment status: {payment_status}")

    order_status = {
        "PENDING": "CREATED",
        "PAYMENT_REQUESTED": "PAYMENT_REQUESTED",
        "PAID": "COMPLETED",
        "FAILED": "PAYMENT_FAILED",
        "CANCELED": "CANCELED",
    }[normalized_status]

    paid_at_expression = "CURRENT_TIMESTAMP" if normalized_status == "PAID" else "paid_at"
    canceled_at_expression = "CURRENT_TIMESTAMP" if normalized_status == "CANCELED" else "canceled_at"

    with get_connection(db_path) as connection:
        cursor = connection.execute(
            f"""
            UPDATE orders
            SET payment_status = ?,
                order_status = ?,
                payment_note = ?,
                payment_provider = ?,
                payment_reference = ?,
                paid_at = {paid_at_expression},
                canceled_at = {canceled_at_expression}
            WHERE id = ?
            """,
            (
                normalized_status,
                order_status,
                payment_note.strip(),
                (payment_provider or "MANUAL").strip().upper(),
                payment_reference.strip(),
                order_id,
            ),
        )
        if cursor.rowcount == 0:
            return None

        order_row = connection.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
        connection.execute(
            """
            INSERT INTO payment_events (
                order_id,
                event_type,
                payment_status,
                provider,
                provider_reference,
                detail_json
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                order_id,
                event_type,
                normalized_status,
                (payment_provider or "MANUAL").strip().upper(),
                payment_reference.strip(),
                json.dumps(detail or {}, ensure_ascii=False),
            ),
        )
        if order_row and normalized_status == "PAID":
            connection.execute(
                "UPDATE purchase_requests SET status = 'COMPLETED' WHERE id = ?",
                (order_row["purchase_request_id"],),
            )

    return get_order(order_id, db_path)


def list_payment_events(order_id: int, db_path: str | Path = DATABASE_PATH) -> list[dict[str, Any]]:
    init_db(db_path)
    with get_connection(db_path) as connection:
        rows = connection.execute(
            """
            SELECT *
            FROM payment_events
            WHERE order_id = ?
            ORDER BY id DESC
            """,
            (order_id,),
        ).fetchall()
    events = [dict(row) for row in rows]
    for event in events:
        try:
            event["detail"] = json.loads(event.get("detail_json") or "{}")
        except json.JSONDecodeError:
            event["detail"] = {}
    return events


def list_orders(
    seller_id: int | None = None,
    buyer_id: int | None = None,
    db_path: str | Path = DATABASE_PATH,
) -> list[dict[str, Any]]:
    init_db(db_path)
    conditions = []
    params: list[Any] = []
    if seller_id is not None:
        conditions.append("orders.seller_id = ?")
        params.append(seller_id)
    if buyer_id is not None:
        conditions.append("orders.buyer_id = ?")
        params.append(buyer_id)

    where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""
    with get_connection(db_path) as connection:
        rows = connection.execute(
            f"""
            SELECT
                orders.*,
                products.title AS product_title,
                products.price AS product_price,
                products.pricing_model AS pricing_model,
                buyer.name AS buyer_name,
                buyer.email AS buyer_email,
                seller.name AS seller_name,
                seller.email AS seller_email,
                purchase_requests.status AS purchase_status,
                api_keys.id AS api_key_id,
                api_keys.token_prefix AS api_key_prefix,
                api_keys.status AS api_key_status
            FROM orders
            JOIN products ON products.id = orders.product_id
            JOIN purchase_requests ON purchase_requests.id = orders.purchase_request_id
            LEFT JOIN api_keys
                ON api_keys.purchase_request_id = orders.purchase_request_id
               AND api_keys.status = 'ACTIVE'
            JOIN users AS buyer ON buyer.id = orders.buyer_id
            JOIN users AS seller ON seller.id = orders.seller_id
            {where_clause}
            ORDER BY orders.id DESC
            """,
            params,
        ).fetchall()

    return [dict(row) for row in rows]


def get_seller_revenue_summary(
    seller_id: int,
    db_path: str | Path = DATABASE_PATH,
) -> dict[str, Any]:
    init_db(db_path)
    with get_connection(db_path) as connection:
        row = connection.execute(
            """
            SELECT
                COUNT(*) AS order_count,
                COALESCE(SUM(amount), 0) AS gross_amount,
                COALESCE(SUM(CASE WHEN payment_status = 'PAID' THEN amount ELSE 0 END), 0) AS paid_amount,
                COALESCE(SUM(CASE WHEN payment_status = 'PENDING' THEN amount ELSE 0 END), 0) AS pending_amount
            FROM orders
            WHERE seller_id = ?
            """,
            (seller_id,),
        ).fetchone()
        approved_without_order = connection.execute(
            """
            SELECT COUNT(*) AS count
            FROM purchase_requests
            JOIN products ON products.id = purchase_requests.product_id
            JOIN datasets ON datasets.id = products.dataset_id
            LEFT JOIN orders ON orders.purchase_request_id = purchase_requests.id
            WHERE datasets.seller_id = ?
              AND purchase_requests.status IN ('APPROVED', 'COMPLETED')
              AND orders.id IS NULL
            """,
            (seller_id,),
        ).fetchone()["count"]

    summary = dict(row)
    summary["approved_without_order_count"] = int(approved_without_order)
    return summary


def list_seller_settlement_summaries(
    fee_rate: float = 0.1,
    db_path: str | Path = DATABASE_PATH,
) -> list[dict[str, Any]]:
    init_db(db_path)
    normalized_fee_rate = max(0.0, min(float(fee_rate), 1.0))
    with get_connection(db_path) as connection:
        rows = connection.execute(
            """
            SELECT
                seller.id AS seller_id,
                seller.name AS seller_name,
                seller.email AS seller_email,
                seller.company AS seller_company,
                COUNT(orders.id) AS order_count,
                COALESCE(SUM(orders.amount), 0) AS gross_amount,
                COALESCE(SUM(CASE WHEN orders.payment_status = 'PAID' THEN orders.amount ELSE 0 END), 0) AS paid_amount,
                COALESCE(SUM(CASE WHEN orders.payment_status IN ('PENDING', 'PAYMENT_REQUESTED') THEN orders.amount ELSE 0 END), 0) AS pending_amount,
                COALESCE(SUM(CASE WHEN orders.payment_status = 'FAILED' THEN orders.amount ELSE 0 END), 0) AS failed_amount,
                COALESCE(SUM(CASE WHEN orders.payment_status = 'CANCELED' THEN orders.amount ELSE 0 END), 0) AS canceled_amount,
                MAX(orders.paid_at) AS latest_paid_at
            FROM users AS seller
            JOIN orders ON orders.seller_id = seller.id
            GROUP BY seller.id
            ORDER BY paid_amount DESC, gross_amount DESC, seller.id DESC
            """
        ).fetchall()

    summaries = []
    for row in rows:
        item = dict(row)
        platform_fee = round(float(item["paid_amount"] or 0) * normalized_fee_rate)
        item["fee_rate"] = normalized_fee_rate
        item["platform_fee"] = int(platform_fee)
        item["settlement_due_amount"] = int(item["paid_amount"] or 0) - int(platform_fee)
        if int(item["paid_amount"] or 0) > 0:
            item["settlement_status"] = "READY"
        elif int(item["pending_amount"] or 0) > 0:
            item["settlement_status"] = "PENDING_PAYMENT"
        else:
            item["settlement_status"] = "NO_PAID_ORDERS"
        summaries.append(item)

    return summaries


def list_purchase_requests(
    query: str | None = None,
    status: str | None = None,
    db_path: str | Path = DATABASE_PATH,
) -> list[dict[str, Any]]:
    init_db(db_path)
    conditions = []
    params: list[Any] = []

    if query:
        like_query = f"%{query.strip()}%"
        conditions.append(
            """
            (
                products.title LIKE ?
                OR users.name LIKE ?
                OR users.email LIKE ?
                OR purchase_requests.message LIKE ?
            )
            """
        )
        params.extend([like_query, like_query, like_query, like_query])

    if status:
        conditions.append("purchase_requests.status = ?")
        params.append(status)

    where_clause = ""
    if conditions:
        where_clause = "WHERE " + " AND ".join(conditions)

    with get_connection(db_path) as connection:
        rows = connection.execute(
            f"""
            SELECT
                purchase_requests.*,
                products.title AS product_title,
                products.price AS product_price,
                products.status AS product_status,
                datasets.seller_id AS seller_id,
                users.name AS buyer_name,
                users.email AS buyer_email
            FROM purchase_requests
            JOIN products ON products.id = purchase_requests.product_id
            JOIN datasets ON datasets.id = products.dataset_id
            JOIN users ON users.id = purchase_requests.buyer_id
            {where_clause}
            ORDER BY purchase_requests.id DESC
            """,
            params,
        ).fetchall()

    return [dict(row) for row in rows]


def list_purchase_requests_by_buyer(buyer_id: int, db_path: str | Path = DATABASE_PATH) -> list[dict[str, Any]]:
    init_db(db_path)
    with get_connection(db_path) as connection:
        rows = connection.execute(
            """
            SELECT
                purchase_requests.*,
                products.title AS product_title,
                products.price AS product_price,
                api_keys.id AS api_key_id,
                api_keys.token_prefix AS api_key_prefix,
                api_keys.status AS api_key_status,
                (
                    SELECT COUNT(*)
                    FROM download_logs
                    WHERE download_logs.product_id = purchase_requests.product_id
                      AND download_logs.user_id = purchase_requests.buyer_id
                ) AS sample_download_count
            FROM purchase_requests
            JOIN products ON products.id = purchase_requests.product_id
            LEFT JOIN api_keys
                ON api_keys.purchase_request_id = purchase_requests.id
                AND api_keys.status = 'ACTIVE'
            WHERE purchase_requests.buyer_id = ?
            ORDER BY purchase_requests.id DESC
            """,
            (buyer_id,),
        ).fetchall()

    return [dict(row) for row in rows]


def list_purchase_requests_by_seller(
    seller_id: int,
    status: str | None = None,
    db_path: str | Path = DATABASE_PATH,
) -> list[dict[str, Any]]:
    init_db(db_path)
    params: list[Any] = [seller_id]
    status_clause = ""
    if status:
        status_clause = "AND purchase_requests.status = ?"
        params.append(status)

    with get_connection(db_path) as connection:
        rows = connection.execute(
            f"""
            SELECT
                purchase_requests.*,
                products.title AS product_title,
                products.price AS product_price,
                products.status AS product_status,
                users.name AS buyer_name,
                users.email AS buyer_email,
                users.company AS buyer_company
            FROM purchase_requests
            JOIN products ON products.id = purchase_requests.product_id
            JOIN datasets ON datasets.id = products.dataset_id
            JOIN users ON users.id = purchase_requests.buyer_id
            WHERE datasets.seller_id = ?
            {status_clause}
            ORDER BY purchase_requests.id DESC
            """,
            params,
        ).fetchall()

    return [dict(row) for row in rows]


def update_purchase_request_status(
    request_id: int,
    status: str,
    review_note: str = "",
    db_path: str | Path = DATABASE_PATH,
) -> bool:
    init_db(db_path)
    with get_connection(db_path) as connection:
        cursor = connection.execute(
            "UPDATE purchase_requests SET status = ?, review_note = ? WHERE id = ?",
            (status, review_note, request_id),
        )

    return cursor.rowcount > 0


def list_products_by_seller(seller_id: int, db_path: str | Path = DATABASE_PATH) -> list[dict[str, Any]]:
    init_db(db_path)
    with get_connection(db_path) as connection:
        rows = connection.execute(
            """
            SELECT
                products.*,
                datasets.data_name,
                datasets.row_count,
                datasets.column_count,
                datasets.quality_score
            FROM products
            JOIN datasets ON datasets.id = products.dataset_id
            WHERE datasets.seller_id = ?
            ORDER BY products.id DESC
            """,
            (seller_id,),
        ).fetchall()

    return [dict(row) for row in rows]


def list_seller_product_reports(seller_id: int, db_path: str | Path = DATABASE_PATH) -> list[dict[str, Any]]:
    init_db(db_path)
    with get_connection(db_path) as connection:
        rows = connection.execute(
            """
            SELECT
                products.id AS product_id,
                products.dataset_id,
                products.title,
                products.price,
                products.pricing_model,
                products.status AS product_status,
                products.created_at AS product_created_at,
                datasets.data_name,
                datasets.file_type,
                datasets.row_count,
                datasets.column_count,
                datasets.quality_score,
                COUNT(DISTINCT purchase_requests.id) AS purchase_request_count,
                COUNT(DISTINCT CASE WHEN purchase_requests.status = 'REQUESTED' THEN purchase_requests.id END) AS requested_count,
                COUNT(DISTINCT CASE WHEN purchase_requests.status = 'APPROVED' THEN purchase_requests.id END) AS approved_count,
                COUNT(DISTINCT CASE WHEN purchase_requests.status = 'COMPLETED' THEN purchase_requests.id END) AS completed_count,
                COUNT(DISTINCT CASE WHEN purchase_requests.status = 'REJECTED' THEN purchase_requests.id END) AS rejected_count,
                COUNT(DISTINCT orders.id) AS order_count,
                COALESCE(SUM(orders.amount), 0) AS gross_amount,
                COALESCE(SUM(CASE WHEN orders.payment_status = 'PAID' THEN orders.amount ELSE 0 END), 0) AS paid_amount,
                COALESCE(SUM(CASE WHEN orders.payment_status IN ('PENDING', 'PAYMENT_REQUESTED') THEN orders.amount ELSE 0 END), 0) AS pending_amount,
                (
                    SELECT COUNT(*)
                    FROM download_logs
                    WHERE download_logs.product_id = products.id
                ) AS sample_download_count,
                (
                    SELECT COUNT(*)
                    FROM api_usage_logs
                    WHERE api_usage_logs.product_id = products.id
                ) AS api_usage_count,
                (
                    SELECT MAX(api_usage_logs.created_at)
                    FROM api_usage_logs
                    WHERE api_usage_logs.product_id = products.id
                ) AS latest_api_usage_at,
                (
                    SELECT MAX(download_logs.created_at)
                    FROM download_logs
                    WHERE download_logs.product_id = products.id
                ) AS latest_download_at
            FROM products
            JOIN datasets ON datasets.id = products.dataset_id
            LEFT JOIN purchase_requests ON purchase_requests.product_id = products.id
            LEFT JOIN orders ON orders.purchase_request_id = purchase_requests.id
            WHERE datasets.seller_id = ?
            GROUP BY products.id
            ORDER BY paid_amount DESC, purchase_request_count DESC, products.id DESC
            """,
            (seller_id,),
        ).fetchall()

    reports = [dict(row) for row in rows]
    for report in reports:
        report["conversion_rate"] = _percentage(report["completed_count"], report["purchase_request_count"])
        report["paid_rate"] = _percentage(report["paid_amount"], report["gross_amount"])
    return reports


def _percentage(numerator: int | float | None, denominator: int | float | None) -> float:
    denominator_value = float(denominator or 0)
    if denominator_value <= 0:
        return 0.0
    return round(float(numerator or 0) / denominator_value * 100, 2)


def record_download_log(
    product_id: int,
    user_id: int,
    file_name: str,
    ip_address: str = "",
    db_path: str | Path = DATABASE_PATH,
) -> None:
    init_db(db_path)
    with get_connection(db_path) as connection:
        connection.execute(
            """
            INSERT INTO download_logs (product_id, user_id, file_name, ip_address)
            VALUES (?, ?, ?, ?)
            """,
            (product_id, user_id, file_name, ip_address),
        )


def list_download_logs(db_path: str | Path = DATABASE_PATH) -> list[dict[str, Any]]:
    init_db(db_path)
    with get_connection(db_path) as connection:
        rows = connection.execute(
            """
            SELECT
                download_logs.*,
                products.title AS product_title,
                users.name AS user_name,
                users.email AS user_email
            FROM download_logs
            JOIN products ON products.id = download_logs.product_id
            JOIN users ON users.id = download_logs.user_id
            ORDER BY download_logs.id DESC
            LIMIT 200
            """
        ).fetchall()

    return [dict(row) for row in rows]


def create_api_key(
    purchase_request_id: int,
    token_hash: str,
    token_prefix: str,
    total_request_limit: int = 1000,
    monthly_request_limit: int = 300,
    db_path: str | Path = DATABASE_PATH,
) -> dict[str, Any]:
    init_db(db_path)
    purchase = get_purchase_request(purchase_request_id, db_path)
    if purchase is None:
        raise ValueError("purchase request not found")
    if not purchase_request_has_data_access(purchase_request_id, db_path):
        raise ValueError("payment completion is required for paid products")

    with get_connection(db_path) as connection:
        existing = connection.execute(
            """
            SELECT *
            FROM api_keys
            WHERE purchase_request_id = ? AND status = 'ACTIVE'
            LIMIT 1
            """,
            (purchase_request_id,),
        ).fetchone()
        if existing:
            return dict(existing)

        cursor = connection.execute(
            """
            INSERT INTO api_keys (
                purchase_request_id,
                product_id,
                user_id,
                token_hash,
                token_prefix,
                total_request_limit,
                monthly_request_limit,
                status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, 'ACTIVE')
            """,
            (
                purchase_request_id,
                purchase["product_id"],
                purchase["buyer_id"],
                token_hash,
                token_prefix,
                int(total_request_limit),
                int(monthly_request_limit),
            ),
        )
        key_id = int(cursor.lastrowid)
        row = connection.execute("SELECT * FROM api_keys WHERE id = ?", (key_id,)).fetchone()

    return dict(row)


def get_active_api_key_for_purchase(
    purchase_request_id: int,
    db_path: str | Path = DATABASE_PATH,
) -> dict[str, Any] | None:
    init_db(db_path)
    with get_connection(db_path) as connection:
        row = connection.execute(
            """
            SELECT *
            FROM api_keys
            WHERE purchase_request_id = ? AND status = 'ACTIVE'
            LIMIT 1
            """,
            (purchase_request_id,),
        ).fetchone()

    return dict(row) if row else None


def get_api_key(api_key_id: int, db_path: str | Path = DATABASE_PATH) -> dict[str, Any] | None:
    init_db(db_path)
    with get_connection(db_path) as connection:
        row = connection.execute(
            """
            SELECT
                api_keys.*,
                products.title AS product_title,
                users.name AS user_name,
                users.email AS user_email
            FROM api_keys
            JOIN products ON products.id = api_keys.product_id
            JOIN users ON users.id = api_keys.user_id
            WHERE api_keys.id = ?
            """,
            (api_key_id,),
        ).fetchone()

    return dict(row) if row else None


def deactivate_api_key(api_key_id: int, user_id: int | None = None, db_path: str | Path = DATABASE_PATH) -> bool:
    init_db(db_path)
    conditions = ["id = ?"]
    params: list[Any] = [api_key_id]

    if user_id is not None:
        conditions.append("user_id = ?")
        params.append(user_id)

    with get_connection(db_path) as connection:
        cursor = connection.execute(
            f"UPDATE api_keys SET status = 'INACTIVE' WHERE {' AND '.join(conditions)}",
            params,
        )

    return cursor.rowcount > 0


def list_api_keys(
    status: str | None = None,
    db_path: str | Path = DATABASE_PATH,
) -> list[dict[str, Any]]:
    init_db(db_path)
    conditions = []
    params: list[Any] = []

    if status:
        conditions.append("api_keys.status = ?")
        params.append(status)

    where_clause = ""
    if conditions:
        where_clause = "WHERE " + " AND ".join(conditions)

    with get_connection(db_path) as connection:
        rows = connection.execute(
            f"""
            SELECT
                api_keys.*,
                products.title AS product_title,
                users.name AS user_name,
                users.email AS user_email,
                purchase_requests.status AS purchase_status,
                (
                    SELECT COUNT(*)
                    FROM api_usage_logs
                    WHERE api_usage_logs.api_key_id = api_keys.id
                ) AS total_usage_count,
                (
                    SELECT COUNT(*)
                    FROM api_usage_logs
                    WHERE api_usage_logs.api_key_id = api_keys.id
                      AND strftime('%Y-%m', api_usage_logs.created_at) = strftime('%Y-%m', 'now')
                ) AS monthly_usage_count
            FROM api_keys
            JOIN products ON products.id = api_keys.product_id
            JOIN users ON users.id = api_keys.user_id
            JOIN purchase_requests ON purchase_requests.id = api_keys.purchase_request_id
            {where_clause}
            ORDER BY api_keys.id DESC
            """,
            params,
        ).fetchall()

    return [dict(row) for row in rows]


def get_api_key_by_hash(token_hash: str, db_path: str | Path = DATABASE_PATH) -> dict[str, Any] | None:
    init_db(db_path)
    with get_connection(db_path) as connection:
        row = connection.execute(
            """
            SELECT
                api_keys.*,
                products.status AS product_status,
                products.price AS product_price,
                purchase_requests.status AS purchase_status,
                orders.payment_status AS payment_status
            FROM api_keys
            JOIN products ON products.id = api_keys.product_id
            JOIN purchase_requests ON purchase_requests.id = api_keys.purchase_request_id
            LEFT JOIN orders ON orders.purchase_request_id = purchase_requests.id
            WHERE api_keys.token_hash = ? AND api_keys.status = 'ACTIVE'
            LIMIT 1
            """,
            (token_hash,),
        ).fetchone()

    return dict(row) if row else None


def get_api_key_usage_summary(api_key_id: int, db_path: str | Path = DATABASE_PATH) -> dict[str, Any]:
    init_db(db_path)
    with get_connection(db_path) as connection:
        row = connection.execute(
            """
            SELECT
                api_keys.id,
                api_keys.total_request_limit,
                api_keys.monthly_request_limit,
                (
                    SELECT COUNT(*)
                    FROM api_usage_logs
                    WHERE api_usage_logs.api_key_id = api_keys.id
                ) AS total_usage_count,
                (
                    SELECT COUNT(*)
                    FROM api_usage_logs
                    WHERE api_usage_logs.api_key_id = api_keys.id
                      AND strftime('%Y-%m', api_usage_logs.created_at) = strftime('%Y-%m', 'now')
                ) AS monthly_usage_count
            FROM api_keys
            WHERE api_keys.id = ?
            """,
            (api_key_id,),
        ).fetchone()

    if row is None:
        return {
            "total_request_limit": 0,
            "monthly_request_limit": 0,
            "total_usage_count": 0,
            "monthly_usage_count": 0,
            "total_remaining": 0,
            "monthly_remaining": 0,
            "is_exceeded": True,
            "reason": "API key not found",
        }

    summary = dict(row)
    summary["total_remaining"] = max(0, int(summary["total_request_limit"]) - int(summary["total_usage_count"]))
    summary["monthly_remaining"] = max(0, int(summary["monthly_request_limit"]) - int(summary["monthly_usage_count"]))
    if summary["total_remaining"] <= 0:
        summary["is_exceeded"] = True
        summary["reason"] = "total API request limit exceeded"
    elif summary["monthly_remaining"] <= 0:
        summary["is_exceeded"] = True
        summary["reason"] = "monthly API request limit exceeded"
    else:
        summary["is_exceeded"] = False
        summary["reason"] = ""
    return summary


def record_api_usage(
    api_key_id: int,
    product_id: int,
    user_id: int,
    endpoint: str,
    ip_address: str = "",
    db_path: str | Path = DATABASE_PATH,
) -> None:
    init_db(db_path)
    with get_connection(db_path) as connection:
        connection.execute(
            """
            INSERT INTO api_usage_logs (api_key_id, product_id, user_id, endpoint, ip_address)
            VALUES (?, ?, ?, ?, ?)
            """,
            (api_key_id, product_id, user_id, endpoint, ip_address),
        )


def list_api_usage_logs(db_path: str | Path = DATABASE_PATH) -> list[dict[str, Any]]:
    init_db(db_path)
    with get_connection(db_path) as connection:
        rows = connection.execute(
            """
            SELECT
                api_usage_logs.*,
                products.title AS product_title,
                users.name AS user_name,
                users.email AS user_email,
                api_keys.token_prefix
            FROM api_usage_logs
            JOIN products ON products.id = api_usage_logs.product_id
            JOIN users ON users.id = api_usage_logs.user_id
            JOIN api_keys ON api_keys.id = api_usage_logs.api_key_id
            ORDER BY api_usage_logs.id DESC
            LIMIT 200
            """
        ).fetchall()

    return [dict(row) for row in rows]


def record_audit_log(
    actor_user_id: int | None,
    action: str,
    target_type: str,
    target_id: int | None = None,
    detail: dict[str, Any] | None = None,
    ip_address: str = "",
    db_path: str | Path = DATABASE_PATH,
) -> None:
    init_db(db_path)
    with get_connection(db_path) as connection:
        connection.execute(
            """
            INSERT INTO audit_logs (
                actor_user_id,
                action,
                target_type,
                target_id,
                detail_json,
                ip_address
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                actor_user_id,
                action,
                target_type,
                target_id,
                json.dumps(detail or {}, ensure_ascii=False),
                ip_address,
            ),
        )


def record_access_log(
    user_id: int | None,
    email: str,
    event_type: str,
    failure_reason: str = "",
    ip_address: str = "",
    user_agent: str = "",
    db_path: str | Path = DATABASE_PATH,
) -> None:
    init_db(db_path)
    with get_connection(db_path) as connection:
        connection.execute(
            """
            INSERT INTO access_logs (
                user_id,
                email,
                event_type,
                failure_reason,
                ip_address,
                user_agent
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                email,
                event_type,
                failure_reason,
                ip_address,
                user_agent,
            ),
        )


def list_access_logs(
    query: str = "",
    event_type: str | None = None,
    user_id: int | None = None,
    limit: int = 100,
    db_path: str | Path = DATABASE_PATH,
) -> list[dict[str, Any]]:
    init_db(db_path)
    limit = max(1, min(int(limit or 100), 500))
    clauses: list[str] = []
    params: list[Any] = []

    if event_type:
        clauses.append("access_logs.event_type = ?")
        params.append(event_type)
    if user_id:
        clauses.append("access_logs.user_id = ?")
        params.append(user_id)
    if query:
        like = f"%{query}%"
        clauses.append(
            """
            (
                access_logs.email LIKE ?
                OR access_logs.event_type LIKE ?
                OR access_logs.failure_reason LIKE ?
                OR access_logs.ip_address LIKE ?
                OR access_logs.user_agent LIKE ?
                OR users.name LIKE ?
            )
            """
        )
        params.extend([like, like, like, like, like, like])

    where_clause = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    with get_connection(db_path) as connection:
        rows = connection.execute(
            f"""
            SELECT
                access_logs.*,
                users.name AS user_name,
                users.role AS user_role
            FROM access_logs
            LEFT JOIN users ON users.id = access_logs.user_id
            {where_clause}
            ORDER BY access_logs.id DESC
            LIMIT ?
            """,
            [*params, limit],
        ).fetchall()

    return [dict(row) for row in rows]


def list_audit_logs(
    query: str = "",
    action: str | None = None,
    actor_user_id: int | None = None,
    limit: int = 200,
    db_path: str | Path = DATABASE_PATH,
) -> list[dict[str, Any]]:
    init_db(db_path)
    clauses = []
    params: list[Any] = []

    if query:
        clauses.append(
            """
            (
                audit_logs.action LIKE ?
                OR audit_logs.target_type LIKE ?
                OR audit_logs.detail_json LIKE ?
                OR users.name LIKE ?
                OR users.email LIKE ?
            )
            """
        )
        like_query = f"%{query}%"
        params.extend([like_query, like_query, like_query, like_query, like_query])

    if action:
        clauses.append("audit_logs.action = ?")
        params.append(action)

    if actor_user_id:
        clauses.append("audit_logs.actor_user_id = ?")
        params.append(actor_user_id)

    where_clause = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    params.append(max(1, min(int(limit), 500)))

    with get_connection(db_path) as connection:
        rows = connection.execute(
            f"""
            SELECT
                audit_logs.*,
                users.name AS actor_name,
                users.email AS actor_email
            FROM audit_logs
            LEFT JOIN users ON users.id = audit_logs.actor_user_id
            {where_clause}
            ORDER BY audit_logs.id DESC
            LIMIT ?
            """,
            params,
        ).fetchall()

    logs = [dict(row) for row in rows]
    for log in logs:
        try:
            log["detail"] = json.loads(log.get("detail_json") or "{}")
        except json.JSONDecodeError:
            log["detail"] = {}
    return logs


def create_notification(
    recipient_user_id: int,
    category: str,
    title: str,
    message: str,
    target_type: str = "",
    target_id: int | None = None,
    db_path: str | Path = DATABASE_PATH,
) -> dict[str, Any]:
    init_db(db_path)
    with get_connection(db_path) as connection:
        cursor = connection.execute(
            """
            INSERT INTO notifications (
                recipient_user_id,
                category,
                title,
                message,
                target_type,
                target_id
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (recipient_user_id, category, title, message, target_type, target_id),
        )
        notification_id = int(cursor.lastrowid)
        row = connection.execute(
            "SELECT * FROM notifications WHERE id = ?",
            (notification_id,),
        ).fetchone()

    return dict(row)


def create_admin_notifications(
    category: str,
    title: str,
    message: str,
    target_type: str = "",
    target_id: int | None = None,
    db_path: str | Path = DATABASE_PATH,
) -> int:
    admin_ids = list_admin_user_ids(db_path)
    for admin_id in admin_ids:
        create_notification(admin_id, category, title, message, target_type, target_id, db_path)
    return len(admin_ids)


def list_notifications(
    recipient_user_id: int,
    include_read: bool = True,
    limit: int = 20,
    db_path: str | Path = DATABASE_PATH,
) -> list[dict[str, Any]]:
    init_db(db_path)
    where_clause = "WHERE recipient_user_id = ?"
    params: list[Any] = [recipient_user_id]
    if not include_read:
        where_clause += " AND read_at IS NULL"
    params.append(max(1, min(int(limit), 100)))

    with get_connection(db_path) as connection:
        rows = connection.execute(
            f"""
            SELECT *
            FROM notifications
            {where_clause}
            ORDER BY id DESC
            LIMIT ?
            """,
            params,
        ).fetchall()

    return [dict(row) for row in rows]


def count_unread_notifications(recipient_user_id: int, db_path: str | Path = DATABASE_PATH) -> int:
    init_db(db_path)
    with get_connection(db_path) as connection:
        row = connection.execute(
            """
            SELECT COUNT(*) AS count
            FROM notifications
            WHERE recipient_user_id = ? AND read_at IS NULL
            """,
            (recipient_user_id,),
        ).fetchone()

    return int(row["count"])


def mark_notification_read(
    notification_id: int,
    recipient_user_id: int,
    db_path: str | Path = DATABASE_PATH,
) -> bool:
    init_db(db_path)
    with get_connection(db_path) as connection:
        cursor = connection.execute(
            """
            UPDATE notifications
            SET read_at = CURRENT_TIMESTAMP
            WHERE id = ? AND recipient_user_id = ?
            """,
            (notification_id, recipient_user_id),
        )

    return cursor.rowcount > 0


def mark_all_notifications_read(
    recipient_user_id: int,
    db_path: str | Path = DATABASE_PATH,
) -> int:
    init_db(db_path)
    with get_connection(db_path) as connection:
        cursor = connection.execute(
            """
            UPDATE notifications
            SET read_at = CURRENT_TIMESTAMP
            WHERE recipient_user_id = ? AND read_at IS NULL
            """,
            (recipient_user_id,),
        )

    return cursor.rowcount


def record_processing_step(
    job_id: str,
    step_key: str,
    step_name: str,
    status: str,
    message: str = "",
    detail: dict[str, Any] | None = None,
    dataset_id: int | None = None,
    db_path: str | Path = DATABASE_PATH,
) -> dict[str, Any]:
    init_db(db_path)
    with get_connection(db_path) as connection:
        cursor = connection.execute(
            """
            INSERT INTO dataset_processing_steps (
                job_id,
                dataset_id,
                step_key,
                step_name,
                status,
                message,
                detail_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                job_id,
                dataset_id,
                step_key,
                step_name,
                status,
                message,
                json.dumps(detail or {}, ensure_ascii=False),
            ),
        )
        step_id = int(cursor.lastrowid)
        row = connection.execute(
            "SELECT * FROM dataset_processing_steps WHERE id = ?",
            (step_id,),
        ).fetchone()

    return dict(row)


def attach_processing_steps_to_dataset(
    job_id: str,
    dataset_id: int,
    db_path: str | Path = DATABASE_PATH,
) -> int:
    init_db(db_path)
    with get_connection(db_path) as connection:
        cursor = connection.execute(
            """
            UPDATE dataset_processing_steps
            SET dataset_id = ?
            WHERE job_id = ? AND dataset_id IS NULL
            """,
            (dataset_id, job_id),
        )

    return cursor.rowcount


def list_processing_steps(
    job_id: str | None = None,
    dataset_id: int | None = None,
    db_path: str | Path = DATABASE_PATH,
) -> list[dict[str, Any]]:
    init_db(db_path)
    if job_id:
        where_clause = "WHERE job_id = ?"
        params: list[Any] = [job_id]
    elif dataset_id:
        where_clause = "WHERE dataset_id = ?"
        params = [dataset_id]
    else:
        return []

    with get_connection(db_path) as connection:
        rows = connection.execute(
            f"""
            SELECT *
            FROM dataset_processing_steps
            {where_clause}
            ORDER BY id
            """,
            params,
        ).fetchall()

    steps = [dict(row) for row in rows]
    for step in steps:
        try:
            step["detail"] = json.loads(step.get("detail_json") or "{}")
        except json.JSONDecodeError:
            step["detail"] = {}
    return steps


def get_admin_metrics(db_path: str | Path = DATABASE_PATH) -> dict[str, Any]:
    init_db(db_path)
    with get_connection(db_path) as connection:
        dataset_status_rows = connection.execute(
            "SELECT status, COUNT(*) AS count FROM datasets GROUP BY status"
        ).fetchall()
        purchase_status_rows = connection.execute(
            "SELECT status, COUNT(*) AS count FROM purchase_requests GROUP BY status"
        ).fetchall()
        row = connection.execute(
            """
            SELECT
                (SELECT COUNT(*) FROM users) AS user_count,
                (SELECT COUNT(*) FROM datasets) AS dataset_count,
                (SELECT COUNT(*) FROM products WHERE status = 'ACTIVE') AS active_product_count,
                (SELECT COUNT(*) FROM purchase_requests) AS purchase_count,
                (SELECT COUNT(*) FROM download_logs) AS download_count,
                (SELECT COUNT(*) FROM api_usage_logs) AS api_usage_count,
                (SELECT COUNT(*) FROM audit_logs) AS audit_log_count,
                (SELECT COUNT(*) FROM datasets WHERE date(created_at) = date('now')) AS today_dataset_count,
                (SELECT COUNT(*) FROM products WHERE status = 'ACTIVE' AND date(created_at) = date('now')) AS today_product_count,
                (SELECT COUNT(*) FROM purchase_requests WHERE date(created_at) = date('now')) AS today_purchase_count,
                (SELECT COUNT(*) FROM api_usage_logs WHERE date(created_at) = date('now')) AS today_api_usage_count,
                (SELECT COUNT(*) FROM datasets WHERE pii_risk_score >= 50) AS high_pii_dataset_count,
                (SELECT COUNT(*) FROM datasets WHERE duplicate_status IN ('DUPLICATE', 'MOSTLY_DUPLICATE')) AS duplicate_risk_dataset_count,
                (SELECT COUNT(*) FROM orders) AS order_count,
                (SELECT COALESCE(SUM(amount), 0) FROM orders) AS estimated_order_amount,
                (SELECT COALESCE(SUM(CASE WHEN payment_status = 'PENDING' THEN amount ELSE 0 END), 0) FROM orders) AS pending_order_amount,
                (SELECT COALESCE(AVG(quality_score), 0) FROM datasets) AS avg_quality_score,
                (SELECT COALESCE(AVG(pii_risk_score), 0) FROM datasets) AS avg_pii_risk_score
            """
        ).fetchone()

    metrics = dict(row)
    metrics["dataset_status_counts"] = {item["status"]: item["count"] for item in dataset_status_rows}
    metrics["purchase_status_counts"] = {item["status"]: item["count"] for item in purchase_status_rows}
    metrics["avg_quality_score"] = round(float(metrics["avg_quality_score"]), 2)
    metrics["avg_pii_risk_score"] = round(float(metrics["avg_pii_risk_score"]), 2)
    return metrics


def get_user_metrics(user_id: int, db_path: str | Path = DATABASE_PATH) -> dict[str, Any]:
    init_db(db_path)
    with get_connection(db_path) as connection:
        row = connection.execute(
            """
            SELECT
                (SELECT COUNT(*) FROM datasets WHERE seller_id = ?) AS uploaded_count,
                (
                    SELECT COUNT(*)
                    FROM products
                    JOIN datasets ON datasets.id = products.dataset_id
                    WHERE datasets.seller_id = ? AND products.status = 'ACTIVE'
                ) AS active_product_count,
                (
                    SELECT COUNT(*)
                    FROM purchase_requests
                    WHERE buyer_id = ?
                ) AS purchase_request_count,
                (
                    SELECT COUNT(*)
                    FROM purchase_requests
                    WHERE buyer_id = ? AND status IN ('APPROVED', 'COMPLETED')
                ) AS approved_purchase_count,
                (
                    SELECT COUNT(*)
                    FROM api_keys
                    WHERE user_id = ? AND status = 'ACTIVE'
                ) AS active_api_key_count,
                (
                    SELECT COUNT(*)
                    FROM api_usage_logs
                    WHERE user_id = ?
                ) AS api_usage_count,
                (
                    SELECT COUNT(*)
                    FROM download_logs
                    WHERE user_id = ?
                ) AS download_count,
                (
                    SELECT COUNT(*)
                    FROM product_favorites
                    WHERE user_id = ?
                ) AS favorite_count
            """,
            (user_id, user_id, user_id, user_id, user_id, user_id, user_id, user_id),
        ).fetchone()

    return dict(row)


def _build_default_product_description(report: dict[str, Any]) -> str:
    schema = report["schema"]
    quality = report["quality"]
    return (
        f"{schema['row_count']} rows, {schema['column_count']} columns, "
        f"quality grade {quality['grade']} dataset sample"
    )


def _default_usage_terms() -> str:
    return (
        "구매 승인 범위 내에서 내부 분석, 리포트 작성, 서비스 검증 목적으로 사용할 수 있습니다. "
        "원본 또는 샘플 데이터의 재판매, 재배포, 개인정보 재식별 시도는 금지됩니다."
    )


def _normalize_product_category(category: str | None, report: dict[str, Any]) -> str:
    value = str(category or "").strip()
    if value:
        return value

    detected_format = str(report.get("format", {}).get("detected_format") or "").upper()
    if "JSON" in detected_format:
        return "Document"
    if "PLAIN_TEXT" in detected_format:
        return "Text"
    return "Tabular"


def _normalize_product_tags(tags: str | None, report: dict[str, Any]) -> str:
    explicit_tags = [tag.strip() for tag in str(tags or "").split(",") if tag.strip()]
    if explicit_tags:
        return ", ".join(dict.fromkeys(explicit_tags))

    generated = []
    detected_format = report.get("format", {}).get("detected_format")
    quality = report.get("quality", {}).get("grade")
    schema = report.get("schema", {})
    if detected_format:
        generated.append(str(detected_format))
    if quality:
        generated.append(f"grade-{quality}")
    if schema.get("column_count"):
        generated.append(f"{schema['column_count']}-columns")
    return ", ".join(dict.fromkeys(generated))
