from __future__ import annotations

import logging
import shutil
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from filelock import FileLock, Timeout

import config


logger = logging.getLogger(__name__)
_started = False


def cleanup_expired() -> None:
    deadline = datetime.now(timezone.utc) - timedelta(days=config.RETENTION_DAYS)
    with FileLock(str(config.CLEANUP_LOCK), timeout=0):
        for parent in (config.JOB_DIR, config.UPLOAD_DIR, config.RESULT_DIR):
            if not parent.exists():
                continue
            for path in parent.iterdir():
                try:
                    modified = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
                    if modified < deadline:
                        if path.is_dir():
                            shutil.rmtree(path, ignore_errors=True)
                        else:
                            path.unlink(missing_ok=True)
                except OSError:
                    logger.exception("清理過期檔案失敗：%s", path)


def _cleanup_loop() -> None:
    while True:
        try:
            cleanup_expired()
        except Timeout:
            pass
        except Exception:
            logger.exception("背景清理排程失敗")
        time.sleep(3600)


def start_cleanup_scheduler() -> None:
    global _started
    if _started:
        return
    _started = True
    thread = threading.Thread(target=_cleanup_loop, name="cleanup-scheduler", daemon=True)
    thread.start()
