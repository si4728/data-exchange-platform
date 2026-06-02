from pathlib import Path

import pandas as pd


def generate_sample(df: pd.DataFrame, output_path: str | Path, sample_size: int = 1000) -> dict:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    sample_df = df.head(sample_size)
    sample_df.to_csv(path, index=False, encoding="utf-8-sig")

    return {
        "sample_path": str(path),
        "sample_rows": int(len(sample_df)),
    }

