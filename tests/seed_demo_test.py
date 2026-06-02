from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from data_marketplace.database import get_product, get_purchase_request
from data_marketplace.seed_demo import seed_demo_data


def main() -> None:
    result = seed_demo_data()
    product = get_product(result["product_id"])
    purchase = get_purchase_request(result["purchase_request_id"])

    if product is None:
        raise AssertionError("seed product is missing")
    if product["status"] != "ACTIVE":
        raise AssertionError(f"seed product is not active: {product}")
    if product["category"] != "Commerce":
        raise AssertionError(f"seed product category mismatch: {product}")
    if purchase is None:
        raise AssertionError("seed purchase is missing")
    if purchase["status"] != "APPROVED":
        raise AssertionError(f"seed purchase status mismatch: {purchase}")

    print("SEED_DEMO_TEST_PASS")


if __name__ == "__main__":
    main()
