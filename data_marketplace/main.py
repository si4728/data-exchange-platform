import argparse
import json
from pathlib import Path

try:
    from data_marketplace.validators.file_to_csv_converter import FileToCSVConverter
except ModuleNotFoundError:
    from validators.file_to_csv_converter import FileToCSVConverter


def convert_upload_to_csv(
    file_path: str | Path,
    output_dir: str | Path = "converted_csv",
    user_pattern: dict | None = None,
) -> dict:
    converter = FileToCSVConverter(file_path=file_path, output_dir=output_dir)
    return converter.convert(user_pattern=user_pattern)


def main() -> None:
    parser = argparse.ArgumentParser(description="Uploaded text-like data to normalized CSV converter")
    parser.add_argument("file_path", help="변환할 입력 파일 경로")
    parser.add_argument("--output-dir", default="converted_csv", help="CSV 저장 폴더")
    parser.add_argument("--format", dest="file_format", help="사용자 지정 포맷: CSV, JSON, DELIMITED_TEXT, PLAIN_TEXT")
    parser.add_argument("--delimiter", help="사용자 지정 구분자. 탭은 \\t 로 입력")
    args = parser.parse_args()

    user_pattern = None
    if args.file_format:
        user_pattern = {
            "file_format": args.file_format,
            "delimiter": args.delimiter,
        }

    result = convert_upload_to_csv(args.file_path, args.output_dir, user_pattern)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
