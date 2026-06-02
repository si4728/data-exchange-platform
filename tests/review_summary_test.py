from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from data_marketplace.services import build_review_summary


def main() -> None:
    schema = {
        "row_count": 100,
        "column_count": 3,
        "columns": [
            {"column_name": "email", "null_rate": 0},
            {"column_name": "name", "null_rate": 10},
            {"column_name": "memo", "null_rate": 60},
        ],
    }
    pii = {
        "total_pii_count": 2,
        "pii_risk_score": 20,
        "column_hits": {
            "email": [{"column_name": "email", "match_count": 2}],
        },
    }
    duplicate = {
        "is_duplicate": False,
        "duplicate_row_rate": 5,
    }
    quality = {
        "score": 78,
        "grade": "B",
    }

    summary = build_review_summary(schema, pii, duplicate, quality)
    if summary["recommendation"] != "APPROVE_CANDIDATE":
        raise AssertionError(summary)
    if summary["avg_null_rate"] != 23.33:
        raise AssertionError(summary)
    if summary["pii_columns"] != ["email"]:
        raise AssertionError(summary)
    if summary["high_null_columns"] != ["memo"]:
        raise AssertionError(summary)
    if not summary["findings"]:
        raise AssertionError("findings are missing")

    duplicate["duplicate_row_rate"] = 90
    duplicate["is_duplicate"] = True
    rejected = build_review_summary(schema, pii, duplicate, quality)
    if rejected["recommendation"] != "REJECT_RECOMMENDED":
        raise AssertionError(rejected)

    print("REVIEW_SUMMARY_TEST_PASS")


if __name__ == "__main__":
    main()
