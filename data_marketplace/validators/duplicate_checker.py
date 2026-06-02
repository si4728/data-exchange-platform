import hashlib
import json
from pathlib import Path

import pandas as pd

from data_marketplace.database import file_hash_exists, find_existing_row_hashes


def calculate_file_hash(file_path: str | Path) -> str:
    sha256 = hashlib.sha256()

    with Path(file_path).open("rb") as file:
        for chunk in iter(lambda: file.read(8192), b""):
            sha256.update(chunk)

    return sha256.hexdigest()


def calculate_row_hashes(df: pd.DataFrame) -> list[str]:
    hashes = []
    normalized_df = df.fillna("").astype(str)

    for row in normalized_df.to_dict(orient="records"):
        payload = json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        hashes.append(hashlib.sha256(payload.encode("utf-8")).hexdigest())

    return hashes


def check_duplicate(file_path: str | Path, df: pd.DataFrame | None = None) -> dict:
    file_hash = calculate_file_hash(file_path)
    is_file_duplicate = file_hash_exists(file_hash)
    row_hashes = calculate_row_hashes(df) if df is not None else []
    existing_row_hashes = find_existing_row_hashes(row_hashes) if row_hashes else set()
    duplicate_row_count = sum(1 for row_hash in row_hashes if row_hash in existing_row_hashes)
    row_count = len(row_hashes)
    duplicate_row_rate = round((duplicate_row_count / row_count * 100) if row_count else 0, 2)

    if is_file_duplicate:
        status = "DUPLICATE"
    elif duplicate_row_rate >= 80:
        status = "MOSTLY_DUPLICATE"
    elif duplicate_row_rate > 0:
        status = "PARTIAL_DUPLICATE"
    else:
        status = "NEW"

    return {
        "file_hash": file_hash,
        "is_duplicate": is_file_duplicate or duplicate_row_rate >= 80,
        "is_file_duplicate": is_file_duplicate,
        "row_count": row_count,
        "duplicate_row_count": duplicate_row_count,
        "duplicate_row_rate": duplicate_row_rate,
        "row_hashes": row_hashes,
        "status": status,
    }
