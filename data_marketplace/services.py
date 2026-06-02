import json
from pathlib import Path
from typing import Any

import pandas as pd

from data_marketplace.config import (
    CONVERTED_DIR,
    DELETE_UPLOADED_FILES_AFTER_PROCESSING,
    KEEP_NORMALIZED_DATA,
    KEEP_SAMPLES,
    REPORT_DIR,
    SAMPLE_DIR,
    SAMPLE_SIZE,
)
from data_marketplace.database import save_dataset_row_hashes, save_validation_result, update_report_json
from data_marketplace.validators.duplicate_checker import check_duplicate
from data_marketplace.validators.file_to_csv_converter import FileToCSVConverter
from data_marketplace.validators.pii_detector import detect_pii
from data_marketplace.validators.quality_scorer import calculate_quality_score
from data_marketplace.validators.sample_generator import generate_sample
from data_marketplace.validators.schema_checker import check_schema


def validate_dataset(
    file_path: str | Path,
    user_pattern: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
    progress_callback=None,
) -> dict:
    source_path = Path(file_path)
    metadata = _normalize_metadata(source_path, metadata)
    _emit_progress(
        progress_callback,
        "RECEIVED",
        "파일 접수",
        "DONE",
        "업로드 파일 검증 작업을 접수했습니다.",
        {
            "filename": source_path.name,
            "file_size_bytes": source_path.stat().st_size if source_path.exists() else 0,
        },
    )

    converter = FileToCSVConverter(source_path, CONVERTED_DIR)
    _emit_progress(
        progress_callback,
        "FORMAT_DETECTION",
        "포맷 감지 및 CSV 변환",
        "RUNNING",
        "파일 구조를 확인하고 내부 검증용 CSV로 변환합니다.",
    )
    conversion_result = converter.convert(user_pattern=user_pattern)
    converted_path = Path(conversion_result["output_csv"])
    _emit_progress(
        progress_callback,
        "FORMAT_DETECTION",
        "포맷 감지 및 CSV 변환",
        "DONE",
        "CSV 표준화가 완료되었습니다.",
        {
            "detected_format": conversion_result["detected_format"],
            "has_header": conversion_result["has_header"],
            "warnings": conversion_result["warnings"],
        },
    )

    _emit_progress(
        progress_callback,
        "DATA_LOADING",
        "데이터 로딩",
        "RUNNING",
        "표준화된 CSV를 데이터프레임으로 읽습니다.",
    )
    df = pd.read_csv(converted_path)
    _emit_progress(
        progress_callback,
        "DATA_LOADING",
        "데이터 로딩",
        "DONE",
        "데이터 로딩이 완료되었습니다.",
        {
            "row_count": int(len(df)),
            "column_count": int(len(df.columns)),
        },
    )

    _emit_progress(
        progress_callback,
        "DUPLICATE_CHECK",
        "중복 검사",
        "RUNNING",
        "파일 해시와 행 해시를 기준으로 중복 여부를 검사합니다.",
    )
    duplicate_result = check_duplicate(source_path, df)
    _emit_progress(
        progress_callback,
        "DUPLICATE_CHECK",
        "중복 검사",
        "DONE",
        "중복 검사가 완료되었습니다.",
        {
            "status": duplicate_result["status"],
            "is_duplicate": duplicate_result["is_duplicate"],
            "duplicate_row_rate": duplicate_result.get("duplicate_row_rate", 0),
        },
    )

    _emit_progress(
        progress_callback,
        "SCHEMA_CHECK",
        "스키마 및 컬럼 통계",
        "RUNNING",
        "컬럼 타입, NULL 비율, 고유값 수를 계산합니다.",
    )
    schema_result = check_schema(df)
    _emit_progress(
        progress_callback,
        "SCHEMA_CHECK",
        "스키마 및 컬럼 통계",
        "DONE",
        "컬럼별 통계 계산이 완료되었습니다.",
        {
            "row_count": schema_result["row_count"],
            "column_count": schema_result["column_count"],
        },
    )

    _emit_progress(
        progress_callback,
        "PII_CHECK",
        "개인정보 탐지",
        "RUNNING",
        "샘플 데이터에서 개인정보 패턴을 탐지합니다.",
    )
    pii_result = detect_pii(df)
    _emit_progress(
        progress_callback,
        "PII_CHECK",
        "개인정보 탐지",
        "DONE",
        "개인정보 탐지가 완료되었습니다.",
        {
            "pii_risk_score": pii_result["pii_risk_score"],
            "total_pii_count": pii_result["total_pii_count"],
        },
    )

    _emit_progress(
        progress_callback,
        "QUALITY_SCORE",
        "품질 점수 계산",
        "RUNNING",
        "완전성, 규모, 중복, 개인정보 위험을 기준으로 점수를 계산합니다.",
    )
    quality_result = calculate_quality_score(schema_result, pii_result, duplicate_result)
    status = _decide_status(quality_result, pii_result, duplicate_result)
    _emit_progress(
        progress_callback,
        "QUALITY_SCORE",
        "품질 점수 계산",
        "DONE",
        "품질 점수 계산이 완료되었습니다.",
        {
            "score": quality_result["score"],
            "grade": quality_result["grade"],
            "initial_status": status,
        },
    )

    sample_result = None
    if KEEP_SAMPLES:
        _emit_progress(
            progress_callback,
            "SAMPLE_GENERATION",
            "샘플 생성",
            "RUNNING",
            "마켓 미리보기와 관리자 검토용 샘플을 생성합니다.",
        )
        sample_path = SAMPLE_DIR / f"{converted_path.stem}_sample.csv"
        sample_result = generate_sample(df, sample_path, SAMPLE_SIZE)
        _emit_progress(
            progress_callback,
            "SAMPLE_GENERATION",
            "샘플 생성",
            "DONE",
            "샘플 생성이 완료되었습니다.",
            {
                "sample_rows": sample_result["sample_rows"],
                "sample_path": sample_result["sample_path"],
            },
        )

    review_summary = build_review_summary(schema_result, pii_result, duplicate_result, quality_result)
    report = {
        "metadata": metadata,
        "status": status,
        "format": {
            "filename": source_path.name,
            "detected_format": conversion_result["detected_format"],
            "detection_reason": conversion_result["detection_reason"],
            "has_header": conversion_result["has_header"],
            "warnings": conversion_result["warnings"],
        },
        "schema": schema_result,
        "pii": pii_result,
        "duplicate": duplicate_result,
        "quality": quality_result,
        "review_summary": review_summary,
        "sample": sample_result,
        "retention": {
            "uploaded_file_deleted": False,
            "normalized_file_deleted": False,
            "stored_file_path": str(converted_path) if KEEP_NORMALIZED_DATA else None,
            "sample_retained": KEEP_SAMPLES,
        },
    }

    _emit_progress(
        progress_callback,
        "REPORT_SAVE",
        "검증 리포트 저장",
        "RUNNING",
        "검증 결과와 컬럼 통계를 DB에 저장합니다.",
    )
    dataset_id = save_validation_result(report)
    save_dataset_row_hashes(dataset_id, duplicate_result["row_hashes"])
    duplicate_result.pop("row_hashes", None)
    report["dataset_id"] = dataset_id
    _apply_retention_policy(source_path, converted_path, report)
    _save_report_json(dataset_id, report)
    update_report_json(dataset_id, report)
    _emit_progress(
        progress_callback,
        "REPORT_SAVE",
        "검증 리포트 저장",
        "DONE",
        "검증 리포트 저장이 완료되었습니다.",
        {
            "dataset_id": dataset_id,
            "uploaded_file_deleted": report["retention"]["uploaded_file_deleted"],
            "normalized_file_deleted": report["retention"]["normalized_file_deleted"],
        },
        dataset_id=dataset_id,
    )

    return report


def build_review_summary(
    schema_result: dict,
    pii_result: dict,
    duplicate_result: dict,
    quality_result: dict,
) -> dict:
    columns = schema_result.get("columns", [])
    row_count = int(schema_result.get("row_count") or 0)
    column_count = int(schema_result.get("column_count") or 0)
    avg_null_rate = round(
        sum(float(column.get("null_rate") or 0) for column in columns) / len(columns),
        2,
    ) if columns else 100.0
    high_null_columns = [
        column["column_name"]
        for column in columns
        if float(column.get("null_rate") or 0) >= 50
    ]
    pii_columns = _collect_pii_columns(pii_result)

    findings = []
    if duplicate_result.get("is_file_duplicate"):
        findings.append(_finding("CRITICAL", "완전 중복 파일", "동일한 파일 해시가 이미 등록되어 있습니다."))
    elif float(duplicate_result.get("duplicate_row_rate") or 0) >= 80:
        findings.append(_finding("HIGH", "행 대부분 중복", "기존 데이터와 중복되는 행 비율이 80% 이상입니다."))
    elif float(duplicate_result.get("duplicate_row_rate") or 0) > 0:
        findings.append(_finding("MEDIUM", "부분 중복", "기존 데이터와 일부 행이 중복됩니다."))

    if int(pii_result.get("total_pii_count") or 0) > 0:
        severity = "HIGH" if float(pii_result.get("pii_risk_score") or 0) >= 50 else "MEDIUM"
        findings.append(_finding(severity, "개인정보 패턴 탐지", "이메일, 전화번호, 주민등록번호, IP 등 개인정보 패턴이 탐지되었습니다."))

    if avg_null_rate >= 40:
        findings.append(_finding("HIGH", "높은 결측률", f"평균 NULL 비율이 {avg_null_rate}%입니다."))
    elif avg_null_rate >= 20:
        findings.append(_finding("MEDIUM", "결측률 주의", f"평균 NULL 비율이 {avg_null_rate}%입니다."))

    if high_null_columns:
        findings.append(_finding("MEDIUM", "결측 컬럼 확인 필요", "NULL 비율 50% 이상 컬럼이 있습니다."))

    if row_count == 0 or column_count == 0:
        findings.append(_finding("CRITICAL", "빈 데이터", "행 또는 컬럼이 없어 상품화할 수 없습니다."))
    elif column_count == 1:
        findings.append(_finding("LOW", "단일 컬럼 데이터", "표 형식 상품으로 판매하기 전에 데이터 의미 설명이 필요합니다."))

    recommendation = _review_recommendation(quality_result, pii_result, duplicate_result, avg_null_rate, row_count, column_count)
    if not findings:
        findings.append(_finding("LOW", "주요 위험 낮음", "MVP 기준에서 큰 위험 신호가 발견되지 않았습니다."))

    return {
        "recommendation": recommendation,
        "summary_text": _recommendation_text(recommendation),
        "row_count": row_count,
        "column_count": column_count,
        "avg_null_rate": avg_null_rate,
        "high_null_column_count": len(high_null_columns),
        "high_null_columns": high_null_columns[:10],
        "pii_column_count": len(pii_columns),
        "pii_columns": pii_columns[:10],
        "duplicate_row_rate": duplicate_result.get("duplicate_row_rate", 0),
        "quality_score": quality_result.get("score"),
        "quality_grade": quality_result.get("grade"),
        "findings": findings,
    }


def _finding(severity: str, title: str, message: str) -> dict:
    return {
        "severity": severity,
        "title": title,
        "message": message,
    }


def _collect_pii_columns(pii_result: dict) -> list[str]:
    column_names = set()
    for hits in pii_result.get("column_hits", {}).values():
        for hit in hits:
            column_name = hit.get("column_name")
            if column_name:
                column_names.add(str(column_name))
    return sorted(column_names)


def _review_recommendation(
    quality_result: dict,
    pii_result: dict,
    duplicate_result: dict,
    avg_null_rate: float,
    row_count: int,
    column_count: int,
) -> str:
    if row_count == 0 or column_count == 0:
        return "REJECT_RECOMMENDED"
    if duplicate_result.get("is_file_duplicate") or float(duplicate_result.get("duplicate_row_rate") or 0) >= 80:
        return "REJECT_RECOMMENDED"
    if float(pii_result.get("pii_risk_score") or 0) >= 50:
        return "REVIEW_REQUIRED"
    if float(quality_result.get("score") or 0) < 60:
        return "REVIEW_REQUIRED"
    if avg_null_rate >= 40:
        return "REVIEW_REQUIRED"
    if float(quality_result.get("score") or 0) >= 70:
        return "APPROVE_CANDIDATE"
    return "REVIEW_REQUIRED"


def _recommendation_text(recommendation: str) -> str:
    texts = {
        "APPROVE_CANDIDATE": "승인 후보입니다. 관리자 최종 검토 후 마켓 게시가 가능합니다.",
        "REVIEW_REQUIRED": "추가 검토가 필요합니다. 개인정보, 결측률, 중복률을 확인하세요.",
        "REJECT_RECOMMENDED": "반려 권장입니다. 완전 중복, 빈 데이터, 또는 심각한 품질 문제가 있습니다.",
    }
    return texts.get(recommendation, "추가 검토가 필요합니다.")


def _emit_progress(progress_callback, step_key, step_name, status, message="", detail=None, dataset_id=None):
    if progress_callback:
        progress_callback(
            step_key=step_key,
            step_name=step_name,
            status=status,
            message=message,
            detail=detail or {},
            dataset_id=dataset_id,
        )


def _normalize_metadata(source_path: Path, metadata: dict[str, Any] | None) -> dict[str, Any]:
    metadata = metadata or {}
    data_name = str(metadata.get("data_name") or "").strip()
    description = str(metadata.get("description") or "").strip()
    parent_dataset_id = metadata.get("parent_dataset_id")

    return {
        "seller_id": metadata.get("seller_id"),
        "data_name": data_name or source_path.stem,
        "description": description,
        "parent_dataset_id": parent_dataset_id,
    }


def _decide_status(quality_result: dict, pii_result: dict, duplicate_result: dict) -> str:
    if duplicate_result["is_duplicate"]:
        return "REVIEW"
    if pii_result["pii_risk_score"] >= 50:
        return "REVIEW"
    if quality_result["score"] >= 70:
        return "PASS"
    return "REVIEW"


def _save_report_json(dataset_id: int, report: dict) -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    report_path = REPORT_DIR / f"dataset_{dataset_id}.json"
    report["report_path"] = str(report_path)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


def _apply_retention_policy(source_path: Path, converted_path: Path, report: dict) -> None:
    if DELETE_UPLOADED_FILES_AFTER_PROCESSING and source_path.exists():
        source_path.unlink()
        report["retention"]["uploaded_file_deleted"] = True

    if not KEEP_NORMALIZED_DATA and converted_path.exists():
        converted_path.unlink()
        report["retention"]["normalized_file_deleted"] = True
