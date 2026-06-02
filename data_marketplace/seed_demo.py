from __future__ import annotations

import csv
import json
from pathlib import Path

from werkzeug.security import generate_password_hash

from data_marketplace.config import REPORT_DIR, SAMPLE_DIR
from data_marketplace.database import (
    create_purchase_request,
    create_product_from_dataset,
    create_user,
    get_connection,
    get_user_by_email,
    save_validation_result,
    update_dataset_status,
    update_purchase_request_status,
    update_report_json,
)
from data_marketplace.services import build_review_summary


DEMO_SELLER_EMAIL = "seller.demo@obdm.local"
DEMO_BUYER_EMAIL = "buyer.demo@obdm.local"


def seed_demo_data() -> dict:
    seller = _get_or_create_user(DEMO_SELLER_EMAIL, "Demo Seller", "OBDM Seller Lab")
    buyer = _get_or_create_user(DEMO_BUYER_EMAIL, "Demo Buyer", "OBDM Buyer Lab")
    existing_product = _find_demo_product(seller["id"])
    if existing_product:
        purchase = create_purchase_request(
            product_id=existing_product["id"],
            buyer_id=buyer["id"],
            message="Demo purchase request for QA.",
        )
        update_purchase_request_status(purchase["id"], "APPROVED", "")
        return {
            "seller_email": seller["email"],
            "buyer_email": buyer["email"],
            "dataset_id": existing_product["dataset_id"],
            "product_id": existing_product["id"],
            "purchase_request_id": purchase["id"],
            "reused": True,
        }

    report = _build_demo_report(seller["id"])
    dataset_id = save_validation_result(report)
    report["dataset_id"] = dataset_id
    report_path = _write_report(dataset_id, report)
    report["report_path"] = str(report_path)
    update_report_json(dataset_id, report)
    update_dataset_status(dataset_id, "APPROVED", "")
    product = create_product_from_dataset(
        dataset_id,
        title="Demo Customer Orders Dataset",
        description="Demo dataset for marketplace QA with order, region, and amount columns.",
        price=10000,
        category="Commerce",
        tags="demo, commerce, orders, qa",
    )
    purchase = create_purchase_request(
        product_id=product["id"],
        buyer_id=buyer["id"],
        message="Demo purchase request for QA.",
    )
    update_purchase_request_status(purchase["id"], "APPROVED", "")

    return {
        "seller_email": seller["email"],
        "buyer_email": buyer["email"],
        "dataset_id": dataset_id,
        "product_id": product["id"],
        "purchase_request_id": purchase["id"],
        "reused": False,
    }


def _get_or_create_user(email: str, name: str, company: str) -> dict:
    user = get_user_by_email(email)
    if user:
        return user
    return create_user(
        name=name,
        email=email,
        password_hash=generate_password_hash("demo1234"),
        company=company,
        role="USER",
        status="ACTIVE",
    )


def _find_demo_product(seller_id: int) -> dict | None:
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT products.id, products.dataset_id
            FROM products
            JOIN datasets ON datasets.id = products.dataset_id
            WHERE datasets.seller_id = ?
              AND products.title = 'Demo Customer Orders Dataset'
            ORDER BY products.id DESC
            LIMIT 1
            """,
            (seller_id,),
        ).fetchone()
    return dict(row) if row else None


def _build_demo_report(seller_id: int) -> dict:
    SAMPLE_DIR.mkdir(parents=True, exist_ok=True)
    sample_path = SAMPLE_DIR / "demo_customer_orders_sample.csv"
    rows = [
        {"order_id": "O-1001", "region": "Seoul", "amount": "150000", "order_date": "2026-05-01"},
        {"order_id": "O-1002", "region": "Busan", "amount": "93000", "order_date": "2026-05-02"},
        {"order_id": "O-1003", "region": "Incheon", "amount": "121000", "order_date": "2026-05-03"},
    ]
    with sample_path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    schema = {
        "row_count": 3,
        "column_count": 4,
        "columns": [
            {"column_name": "order_id", "detected_type": "object", "null_count": 0, "null_rate": 0.0, "unique_count": 3},
            {"column_name": "region", "detected_type": "object", "null_count": 0, "null_rate": 0.0, "unique_count": 3},
            {"column_name": "amount", "detected_type": "int64", "null_count": 0, "null_rate": 0.0, "unique_count": 3},
            {"column_name": "order_date", "detected_type": "object", "null_count": 0, "null_rate": 0.0, "unique_count": 3},
        ],
    }
    pii = {
        "pii_counts": {"email": 0, "phone": 0, "rrn": 0, "ip": 0},
        "column_hits": {"email": [], "phone": [], "rrn": [], "ip": []},
        "total_pii_count": 0,
        "sample_size": 3,
        "pii_risk_score": 0,
    }
    duplicate = {
        "file_hash": "demo_customer_orders_hash",
        "is_duplicate": False,
        "is_file_duplicate": False,
        "row_count": 3,
        "duplicate_row_count": 0,
        "duplicate_row_rate": 0.0,
        "status": "NEW",
        "row_hashes": ["demo-row-1", "demo-row-2", "demo-row-3"],
    }
    quality = {
        "score": 80.0,
        "grade": "A",
        "components": {
            "avg_null_rate": 0.0,
            "completeness_score": 40.0,
            "volume_score": 0.0,
            "structure_score": 20,
            "pii_penalty": 0.0,
            "duplicate_penalty": 0.0,
        },
    }
    return {
        "metadata": {
            "seller_id": seller_id,
            "data_name": "Demo Customer Orders",
            "description": "Demo marketplace dataset generated by the seed script.",
        },
        "status": "PASS",
        "format": {
            "filename": "demo_customer_orders.csv",
            "detected_format": "CSV",
            "detection_reason": "Demo seed data",
            "has_header": True,
            "warnings": [],
        },
        "schema": schema,
        "pii": pii,
        "duplicate": duplicate,
        "quality": quality,
        "review_summary": build_review_summary(schema, pii, duplicate, quality),
        "sample": {"sample_path": str(sample_path), "sample_rows": len(rows)},
        "retention": {
            "uploaded_file_deleted": True,
            "normalized_file_deleted": True,
            "stored_file_path": None,
            "sample_retained": True,
        },
    }


def _write_report(dataset_id: int, report: dict) -> Path:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    report_path = REPORT_DIR / f"dataset_{dataset_id}.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report_path


if __name__ == "__main__":
    result = seed_demo_data()
    print(json.dumps(result, ensure_ascii=False, indent=2))
