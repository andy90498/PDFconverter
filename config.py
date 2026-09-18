import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
STORAGE_DIR = Path(os.getenv("STORAGE_DIR", str(BASE_DIR / "data" / "storage")))

MAX_FILE_SIZE_MB = int(os.getenv("MAX_FILE_SIZE_MB", "150"))
MAX_CONTENT_LENGTH = MAX_FILE_SIZE_MB * 1024 * 1024
MAX_FILE_COUNT = int(os.getenv("MAX_FILE_COUNT", "20"))
MAX_CONCURRENT_JOBS = int(os.getenv("MAX_CONCURRENT_JOBS", "4"))
RETENTION_DAYS = int(os.getenv("RETENTION_DAYS", "3"))

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
