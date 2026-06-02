import pandas as pd


def check_schema(df: pd.DataFrame) -> dict:
    row_count = int(len(df))
    columns = []

    for column_name in df.columns:
        series = df[column_name]
        null_count = int(series.isnull().sum())
        null_rate = round((null_count / row_count * 100) if row_count else 0, 2)

        columns.append(
            {
                "column_name": str(column_name),
                "detected_type": str(series.dtype),
                "null_count": null_count,
                "null_rate": null_rate,
                "unique_count": int(series.nunique(dropna=True)),
            }
        )

    return {
        "row_count": row_count,
        "column_count": int(len(df.columns)),
        "columns": columns,
    }

