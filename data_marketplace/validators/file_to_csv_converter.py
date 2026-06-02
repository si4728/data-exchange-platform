import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd


SUPPORTED_DELIMITERS = {
    ",": "comma",
    "\t": "tab",
    "|": "pipe",
    ";": "semicolon",
}


@dataclass(frozen=True)
class DetectedPattern:
    file_format: str
    delimiter: str | None = None
    reason: str = ""


class FilePatternDetector:
    """Detects whether an uploaded text-like file is CSV, JSON, delimited text, or plain text."""

    def __init__(self, file_path: str | Path, sample_bytes: int = 4096):
        self.file_path = Path(file_path)
        self.sample_bytes = sample_bytes
        self.extension = self.file_path.suffix.lower()

    def detect(self) -> DetectedPattern:
        if not self.file_path.exists():
            raise FileNotFoundError(f"File not found: {self.file_path}")

        sample = self._read_sample()
        stripped = sample.lstrip()

        if self.extension == ".json" or self._looks_like_json(stripped):
            return DetectedPattern("JSON", reason="JSON extension or JSON-like content")

        if self._looks_like_json_lines(sample):
            return DetectedPattern("JSON_LINES", reason="line-delimited JSON objects")

        delimiter = self._detect_delimiter(sample)

        if self.extension == ".csv":
            return DetectedPattern("CSV", delimiter=",", reason="CSV extension")

        if delimiter:
            return DetectedPattern("DELIMITED_TEXT", delimiter=delimiter, reason="repeated delimiter pattern")

        if self.extension in {".txt", ".log", ""}:
            return DetectedPattern("PLAIN_TEXT", reason="no table delimiter detected")

        return DetectedPattern("UNKNOWN", reason=f"unsupported extension: {self.extension}")

    def _read_sample(self) -> str:
        return self.file_path.read_text(encoding="utf-8", errors="ignore")[: self.sample_bytes]

    @staticmethod
    def _looks_like_json(sample: str) -> bool:
        if not sample.startswith(("{", "[")):
            return False

        try:
            json.loads(sample)
            return True
        except json.JSONDecodeError:
            return False

    @staticmethod
    def _looks_like_json_lines(sample: str) -> bool:
        lines = [line.strip() for line in sample.splitlines() if line.strip()][:5]
        if len(lines) < 2:
            return False

        parsed_count = 0
        for line in lines:
            if not line.startswith("{"):
                return False

            try:
                parsed = json.loads(line)
            except json.JSONDecodeError:
                return False

            if isinstance(parsed, dict):
                parsed_count += 1

        return parsed_count == len(lines)

    @staticmethod
    def _detect_delimiter(sample: str) -> str | None:
        lines = [line for line in sample.splitlines()[:10] if line.strip()]
        if len(lines) < 2:
            return None

        best_delimiter = None
        best_score = 0

        for delimiter in SUPPORTED_DELIMITERS:
            counts = [line.count(delimiter) for line in lines]
            non_zero_counts = [count for count in counts if count > 0]

            if len(non_zero_counts) < 2:
                continue

            consistency_bonus = 2 if len(set(non_zero_counts)) == 1 else 0
            score = sum(non_zero_counts) + consistency_bonus

            if score > best_score:
                best_score = score
                best_delimiter = delimiter

        return best_delimiter


class HeaderDetector:
    @staticmethod
    def has_header(file_path: str | Path, delimiter: str = ",") -> bool:
        sample = Path(file_path).read_text(encoding="utf-8", errors="ignore")[:4096]

        try:
            return csv.Sniffer().has_header(sample)
        except csv.Error:
            return False


class FileToCSVConverter:
    """Converts supported upload formats into a normalized CSV file."""

    def __init__(self, file_path: str | Path, output_dir: str | Path = "converted_csv"):
        self.file_path = Path(file_path)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.warnings: list[str] = []

    def convert(self, user_pattern: dict[str, Any] | None = None) -> dict[str, Any]:
        pattern = self._resolve_pattern(user_pattern)
        output_path = self.output_dir / f"{self.file_path.stem}.csv"

        if pattern.file_format == "CSV":
            df = self._read_delimited(pattern.delimiter or ",")
            detected_format = "CSV"
            has_header = HeaderDetector.has_header(self.file_path, pattern.delimiter or ",")
        elif pattern.file_format == "JSON":
            df = self._read_json()
            detected_format = "JSON"
            has_header = True
        elif pattern.file_format == "JSON_LINES":
            df = self._read_json_lines()
            detected_format = "JSON_LINES"
            has_header = True
        elif pattern.file_format == "DELIMITED_TEXT":
            delimiter = pattern.delimiter or ","
            df = self._read_delimited(delimiter)
            detected_format = f"DELIMITED_TEXT:{SUPPORTED_DELIMITERS.get(delimiter, delimiter)}"
            has_header = HeaderDetector.has_header(self.file_path, delimiter)
        elif pattern.file_format == "PLAIN_TEXT":
            df = self._read_plain_text()
            detected_format = "PLAIN_TEXT"
            has_header = False
        else:
            raise ValueError(f"Unsupported file format: {pattern.file_format}")

        df.to_csv(output_path, index=False, encoding="utf-8-sig")

        return {
            "input_file": str(self.file_path),
            "detected_format": detected_format,
            "detection_reason": pattern.reason,
            "has_header": has_header,
            "output_csv": str(output_path),
            "rows": int(len(df)),
            "columns": int(len(df.columns)),
            "column_names": [str(column) for column in df.columns],
            "warnings": self.warnings,
        }

    def _resolve_pattern(self, user_pattern: dict[str, Any] | None) -> DetectedPattern:
        if not user_pattern:
            return FilePatternDetector(self.file_path).detect()

        file_format = str(user_pattern.get("file_format", "")).upper()
        delimiter = user_pattern.get("delimiter")

        if delimiter == "\\t":
            delimiter = "\t"

        return DetectedPattern(
            file_format=file_format,
            delimiter=delimiter,
            reason="user-defined pattern",
        )

    def _read_delimited(self, delimiter: str) -> pd.DataFrame:
        has_header = HeaderDetector.has_header(self.file_path, delimiter)

        try:
            if has_header:
                return pd.read_csv(self.file_path, delimiter=delimiter)

            df = pd.read_csv(self.file_path, delimiter=delimiter, header=None)
        except pd.errors.ParserError as exc:
            raise ValueError(
                "Delimited text parsing failed. This file may be JSON Lines, logs, or irregular text. "
                "Try --format JSON_LINES or --format PLAIN_TEXT."
            ) from exc

        df.columns = [f"column_{index + 1}" for index in range(len(df.columns))]
        return df

    def _read_json(self) -> pd.DataFrame:
        with self.file_path.open("r", encoding="utf-8", errors="ignore") as file:
            data = json.load(file)

        records = self._extract_records(data)
        return pd.json_normalize(records)

    def _read_json_lines(self) -> pd.DataFrame:
        records = []
        invalid_line_count = 0

        with self.file_path.open("r", encoding="utf-8", errors="ignore") as file:
            for line_number, line in enumerate(file, start=1):
                stripped = line.strip()
                if not stripped:
                    continue

                try:
                    record = json.loads(stripped)
                except json.JSONDecodeError as exc:
                    invalid_line_count += 1
                    records.append(
                        {
                            "__line_no": line_number,
                            "__raw_line": stripped,
                            "__parse_error": f"invalid_json: {exc.msg}",
                        }
                    )
                    continue

                if not isinstance(record, dict):
                    invalid_line_count += 1
                    records.append(
                        {
                            "__line_no": line_number,
                            "__raw_line": stripped,
                            "__parse_error": "json_line_is_not_object",
                        }
                    )
                    continue

                record["__line_no"] = line_number
                records.append(record)

        if invalid_line_count:
            self.warnings.append(f"{invalid_line_count} invalid JSON Lines rows were preserved as raw text")

        return pd.json_normalize(records)

    @staticmethod
    def _extract_records(data: Any) -> Any:
        if isinstance(data, list):
            return data

        if isinstance(data, dict):
            for value in data.values():
                if isinstance(value, list):
                    return value
            return data

        raise ValueError("지원하지 않는 JSON 구조입니다.")

    def _read_plain_text(self) -> pd.DataFrame:
        rows = []

        with self.file_path.open("r", encoding="utf-8", errors="ignore") as file:
            for line_number, line in enumerate(file, start=1):
                rows.append({"line_no": line_number, "text": line.rstrip("\n")})

        return pd.DataFrame(rows)
