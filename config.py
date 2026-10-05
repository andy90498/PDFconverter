import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
STORAGE_DIR = Path(os.getenv("STORAGE_DIR", str(BASE_DIR / "data" / "storage")))

MAX_FILE_SIZE_MB = int(os.getenv("MAX_FILE_SIZE_MB", "300"))
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024
MAX_FILE_COUNT = int(os.getenv("MAX_FILE_COUNT", "100"))
MAX_TOTAL_UPLOAD_SIZE_GB = int(os.getenv("MAX_TOTAL_UPLOAD_SIZE_GB", "5"))
MAX_TOTAL_UPLOAD_SIZE_BYTES = MAX_TOTAL_UPLOAD_SIZE_GB * 1024 ** 3
# Allow multipart headers while enforcing the exact file-byte total separately.
MAX_CONTENT_LENGTH = MAX_TOTAL_UPLOAD_SIZE_BYTES + MAX_FILE_COUNT * 64 * 1024
MAX_CONCURRENT_JOBS = int(os.getenv("MAX_CONCURRENT_JOBS", "4"))
RETENTION_DAYS = int(os.getenv("RETENTION_DAYS", "3"))  # 保留：給 JOB_DIR/UPLOAD_DIR 暫存清理用
CLEANUP_INTERVAL_SECONDS = int(os.getenv("CLEANUP_INTERVAL_SECONDS", "300"))

RETENTION_OPTIONS = {
    "30m": 30 * 60,
    "1h": 60 * 60,
    "3h": 3 * 60 * 60,
    "12h": 12 * 60 * 60,
    "24h": 24 * 60 * 60,
    "48h": 48 * 60 * 60,
    "72h": 72 * 60 * 60,
}
DEFAULT_RETENTION_KEY = "72h"
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "").rstrip("/")

JOB_DIR = STORAGE_DIR / "jobs"
UPLOAD_DIR = STORAGE_DIR / "uploads"
RESULT_DIR = STORAGE_DIR / "results"
LOG_DIR = STORAGE_DIR / "logs"
CLEANUP_LOCK = STORAGE_DIR / ".cleanup.lock"

ALLOWED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png", ".heic", ".heif"}
ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".heic", ".heif"}
ALLOWED_MIME_PREFIXES = ("image/",)
ALLOWED_MIME_TYPES = {
    "application/pdf",
    "image/jpeg",
    "image/png",
    "image/heic",
    "image/heif",
}



def ensure_storage_dirs() -> None:
    for path in (STORAGE_DIR, JOB_DIR, UPLOAD_DIR, RESULT_DIR, LOG_DIR):
        path.mkdir(parents=True, exist_ok=True)
