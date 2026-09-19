from __future__ import annotations

import json
import logging
import os
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path

from flask import Flask, jsonify, render_template, request, send_file
from werkzeug.exceptions import RequestEntityTooLarge

import config
import processor
import scheduler


config.ensure_storage_dirs()

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = config.MAX_CONTENT_LENGTH * config.MAX_FILE_COUNT

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(config.LOG_DIR / "app.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)
executor = ThreadPoolExecutor(max_workers=config.MAX_CONCURRENT_JOBS)
scheduler.start_cleanup_scheduler()


def job_path(job_id: str) -> Path:
    return config.JOB_DIR / job_id


def status_path(job_id: str) -> Path:
    return job_path(job_id) / "status.json"


def write_status(job_id: str, **payload: object) -> None:
    path = status_path(job_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    current = {}
    if path.exists():
        try:
            current = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            current = {}
    current.update(payload)
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(current, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(path)


def make_job() -> str:
    job_id = uuid.uuid4().hex
    write_status(job_id, status="queued", progress=0, message="正在排隊")
    return job_id


def run_job(job_id: str, worker) -> None:
    try:
        write_status(job_id, status="processing", progress=1, message="開始處理")
        worker(lambda progress, message=None: write_status(job_id, progress=progress, message=message or "處理中"))
        write_status(job_id, status="done", progress=100, message="完成")
    except Exception as exc:
        logger.exception("任務失敗：%s", job_id)
        write_status(job_id, status="failed", progress=100, message=str(exc))


def result_payload(job_id: str, output_path: Path, filename: str, base_url: str) -> dict[str, str]:
    token = uuid.uuid4().hex
    token_path = config.RESULT_DIR / token
    token_path.mkdir(parents=True, exist_ok=True)
    target = token_path / filename
    output_path.replace(target)
    expires_at = datetime.now(timezone.utc) + timedelta(days=config.RETENTION_DAYS)
    download_url = f"{base_url}/download/{token}"
    qr_path = token_path / "download_qr.png"
    info_path = token_path / "download_info.png"
    processor.create_qr_code(download_url, qr_path)
    processor.create_download_info_image(download_url, expires_at, info_path)
    (token_path / "result.json").write_text(
        json.dumps({"filename": filename, "expires_at": expires_at.isoformat()}, ensure_ascii=False),
        encoding="utf-8",
    )
    write_status(
        job_id,
        token=token,
        filename=filename,
        download_url=download_url,
        qr_url=f"{base_url}/download/{token}/qr",
        info_image_url=f"{base_url}/download/{token}/info-image",
        expires_at=expires_at.isoformat(),
    )
    return {"token": token, "filename": filename}


@app.errorhandler(RequestEntityTooLarge)
def too_large(_error):
    return jsonify({"error": f"檔案太大，單檔限制為 {config.MAX_FILE_SIZE_MB} MB"}), 413


@app.errorhandler(processor.ProcessingError)
def processing_error(error):
    logger.warning("處理錯誤：%s", error)
    return jsonify({"error": str(error)}), 400


@app.get("/")
def index():
    return render_template("index.html", max_file_count=config.MAX_FILE_COUNT, max_file_size=config.MAX_FILE_SIZE_MB)


@app.get("/api/status/<job_id>")
def status(job_id: str):
    path = status_path(job_id)
    if not path.exists():
        return jsonify({"error": "找不到任務"}), 404
    return jsonify(json.loads(path.read_text(encoding="utf-8")))


@app.post("/api/jobs/pdf-to-images")
def create_pdf_to_images_job():
    job_id = make_job()
    base_url = config.PUBLIC_BASE_URL or request.host_url.rstrip("/")
    upload_dir = config.UPLOAD_DIR / job_id
    files = processor.save_uploads(request.files.getlist("files"), upload_dir)
    processor.write_manifest(upload_dir, files)
    image_format = request.form.get("image_format", "jpg")
    keep_annotations = request.form.get("keep_annotations", "true") == "true"

    def worker(progress):
        stored = processor.load_manifest(upload_dir)
        out = job_path(job_id) / "pdf_images.zip"
        processor.pdf_to_images(stored, out, image_format, keep_annotations, progress)
        result_payload(job_id, out, "pdf_images.zip", base_url)
        processor.remove_original_uploads(upload_dir)

    executor.submit(run_job, job_id, worker)
    return jsonify({"job_id": job_id})


@app.post("/api/jobs/merge")
def create_merge_job():
    job_id = make_job()
    base_url = config.PUBLIC_BASE_URL or request.host_url.rstrip("/")
    upload_dir = config.UPLOAD_DIR / job_id
    files = processor.save_uploads(request.files.getlist("files"), upload_dir)
    processor.write_manifest(upload_dir, files)
    order = [int(index) for index in json.loads(request.form.get("order", "[]"))]
    page_mode = request.form.get("page_mode", "original")

    def worker(progress):
        stored = processor.load_manifest(upload_dir)
        out = job_path(job_id) / "merged.pdf"
        processor.merge_files_to_pdf(stored, order, out, page_mode, progress)
        result_payload(job_id, out, "merged.pdf", base_url)
        processor.remove_original_uploads(upload_dir)

    executor.submit(run_job, job_id, worker)
    return jsonify({"job_id": job_id})


@app.post("/api/pages/upload")
def upload_pages_pdf():
    job_id = make_job()
    upload_dir = config.UPLOAD_DIR / job_id
    files = processor.save_uploads(request.files.getlist("file"), upload_dir)
    if len(files) != 1 or files[0].path.suffix.lower() != ".pdf":
        return jsonify({"error": "請上傳單一 PDF"}), 400
    processor.write_manifest(upload_dir, files)
    count = processor.page_count(files[0].path)
    write_status(job_id, status="ready", progress=100, message="PDF 已載入", page_count=count)
    return jsonify({"job_id": job_id, "page_count": count, "filename": files[0].original_name})


@app.get("/api/pages/<job_id>/thumbnail/<int:page_number>")
def page_thumbnail(job_id: str, page_number: int):
    upload_dir = config.UPLOAD_DIR / job_id
    try:
        stored = processor.load_manifest(upload_dir)
        source = stored[0].path
        thumb = job_path(job_id) / "thumbs" / f"{page_number:04d}.jpg"
        if not thumb.exists():
            processor.render_thumbnail(source, page_number, thumb)
        return send_file(thumb, mimetype="image/jpeg")
    except Exception as exc:
        logger.exception("縮圖產生失敗")
        return jsonify({"error": str(exc)}), 400


@app.post("/api/jobs/pages")
def create_pages_job():
    payload = request.get_json(force=True)
    base_url = config.PUBLIC_BASE_URL or request.host_url.rstrip("/")
    source_job_id = payload.get("source_job_id")
    selected_pages = payload.get("selected_pages", [])
    mode = payload.get("mode", "keep")
    if not source_job_id:
        return jsonify({"error": "缺少來源任務"}), 400

    job_id = make_job()
    source_upload_dir = config.UPLOAD_DIR / source_job_id

    def worker(progress):
        stored = processor.load_manifest(source_upload_dir)
        out = job_path(job_id) / "pages.pdf"
        processor.extract_pdf_pages(stored[0].path, out, [int(page) for page in selected_pages], mode, progress)
        result_payload(job_id, out, "pages.pdf", base_url)

    executor.submit(run_job, job_id, worker)
    return jsonify({"job_id": job_id})


@app.get("/download/<token>")
def download(token: str):
    token_dir = config.RESULT_DIR / token
    if not token_dir.exists() or not token_dir.is_dir():
        return jsonify({"error": "下載連結不存在或已過期"}), 404
    meta_path = token_dir / "result.json"
    if not meta_path.exists():
        return jsonify({"error": "找不到下載檔案"}), 404
    filename = json.loads(meta_path.read_text(encoding="utf-8"))["filename"]
    result_file = token_dir / filename
    if not result_file.exists():
        return jsonify({"error": "找不到下載檔案"}), 404
    return send_file(result_file, as_attachment=True, download_name=result_file.name)


@app.get("/download/<token>/qr")
def download_qr(token: str):
    qr_path = config.RESULT_DIR / token / "download_qr.png"
    if not qr_path.exists():
        return jsonify({"error": "QR CODE 不存在或已過期"}), 404
    return send_file(qr_path, mimetype="image/png")


@app.get("/download/<token>/info-image")
def download_info_image(token: str):
    info_path = config.RESULT_DIR / token / "download_info.png"
    if not info_path.exists():
        return jsonify({"error": "下載資訊圖片不存在或已過期"}), 404
    return send_file(info_path, as_attachment=True, download_name="download_info.png", mimetype="image/png")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "9013")), debug=True)
