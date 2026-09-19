from __future__ import annotations

import json
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


def _is_result_expired(token_dir: Path, now: datetime) -> bool:
    meta_path = token_dir / "result.json"
    if not meta_path.exists():
        # 沒有 result.json 的異常資料夾，視為過期，直接歸類清理
        return True
    try:
        data = json.loads(meta_path.read_text(encoding="utf-8"))
        expires_at = datetime.fromisoformat(data["expires_at"])
        return expires_at < now
    except (json.JSONDecodeError, KeyError, ValueError):
        logger.exception("無法解析到期時間，視為過期：%s", meta_path)
        return True


def cleanup_expired() -> None:
    now = datetime.now(timezone.utc)
    fallback_deadline = now - timedelta(days=config.RETENTION_DAYS)

    with FileLock(str(config.CLEANUP_LOCK), timeout=0):
        # RESULT_DIR：依照 result.json 裡的 expires_at 判斷
        if config.RESULT_DIR.exists():
            for path in config.RESULT_DIR.iterdir():
                try:
                    if path.is_dir() and _is_result_expired(path, now):
                        shutil.rmtree(path, ignore_errors=True)
                except OSError:
                    logger.exception("清理過期結果失敗：%s", path)

        # JOB_DIR、UPLOAD_DIR：沒有 expires_at 概念，維持用 mtime 判斷
        for parent in (config.JOB_DIR, config.UPLOAD_DIR):
            if not parent.exists():
                continue
            for path in parent.iterdir():
                try:
                    modified = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
                    if modified < fallback_deadline:
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
        time.sleep(43200)


def start_cleanup_scheduler() -> None:
    global _started
    if _started:
        return
    _started = True
    thread = threading.Thread(target=_cleanup_loop, name="cleanup-scheduler", daemon=True)
    thread.start()