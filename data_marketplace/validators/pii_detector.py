import re

import pandas as pd


PII_PATTERNS = {
    "email": re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+"),
    "phone": re.compile(r"01[016789]-?\d{3,4}-?\d{4}"),
    "rrn": re.compile(r"\d{6}-[1-4]\d{6}"),
    "ip": re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"),
}


def detect_pii(df: pd.DataFrame, sample_size: int = 1000) -> dict:
    sample_df = df.head(sample_size).astype(str)
    pii_counts = {}
    column_hits = {}

    for pii_type, pattern in PII_PATTERNS.items():
        total_count = 0
        matched_columns = []

        for column_name in sample_df.columns:
            matched_count = int(sample_df[column_name].str.contains(pattern, regex=True, na=False).sum())
            if matched_count:
                total_count += matched_count
                matched_columns.append(
                    {
                        "column_name": str(column_name),
                        "count": matched_count,
                    }
                )

        pii_counts[pii_type] = total_count
        column_hits[pii_type] = matched_columns

    total_pii_count = int(sum(pii_counts.values()))

    return {
        "pii_counts": pii_counts,
        "column_hits": column_hits,
        "total_pii_count": total_pii_count,
        "sample_size": int(min(sample_size, len(df))),
        "pii_risk_score": min(total_pii_count * 10, 100),
    }

