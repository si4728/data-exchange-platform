def calculate_quality_score(schema_result: dict, pii_result: dict, duplicate_result: dict) -> dict:
    row_count = schema_result["row_count"]
    columns = schema_result["columns"]

    if columns:
        avg_null_rate = sum(column["null_rate"] for column in columns) / len(columns)
    else:
        avg_null_rate = 100

    completeness_score = max(0, 40 - avg_null_rate)
    volume_score = min(20, row_count / 10000)
    structure_score = 20 if schema_result["column_count"] > 1 else 10
    pii_penalty = pii_result["pii_risk_score"] * 0.3
    duplicate_penalty = round(min(20, duplicate_result.get("duplicate_row_rate", 0) * 0.2), 2)
    if duplicate_result.get("is_file_duplicate"):
        duplicate_penalty = 20

    score = completeness_score + volume_score + structure_score + 20 - pii_penalty - duplicate_penalty
    score = round(max(0, min(score, 100)), 2)

    if score >= 90:
        grade = "A+"
    elif score >= 80:
        grade = "A"
    elif score >= 70:
        grade = "B"
    elif score >= 60:
        grade = "C"
    else:
        grade = "HOLD"

    return {
        "score": score,
        "grade": grade,
        "metrics": {
            "avg_null_rate": round(avg_null_rate, 2),
            "completeness_score": round(completeness_score, 2),
            "volume_score": round(volume_score, 2),
            "structure_score": structure_score,
            "pii_penalty": round(pii_penalty, 2),
            "duplicate_penalty": duplicate_penalty,
        },
    }
