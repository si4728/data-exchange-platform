from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
UPLOAD_DIR = BASE_DIR / "uploads"
CONVERTED_DIR = BASE_DIR / "converted_csv"
SAMPLE_DIR = BASE_DIR / "samples"
REPORT_DIR = BASE_DIR / "reports"
DATABASE_PATH = BASE_DIR / "database" / "marketplace.db"

DELETE_UPLOADED_FILES_AFTER_PROCESSING = True
KEEP_NORMALIZED_DATA = False
KEEP_SAMPLES = True
SAMPLE_SIZE = 1000
MAX_UPLOAD_BYTES = 50 * 1024 * 1024
