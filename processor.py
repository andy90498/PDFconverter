from __future__ import annotations

import json
import mimetypes
import shutil
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterable

import fitz
import qrcode
from PIL import Image, ImageDraw, ImageFont, ImageOps
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename

import config

try:
    import magic
except ImportError:  # pragma: no cover - Docker image installs python-magic.
    magic = None

try:
    from pillow_heif import register_heif_opener

    register_heif_opener()
except Exception:  # pragma: no cover - HEIC support is verified in Docker.
    pass


Progress = Callable[[int, str | None], None]


class ProcessingError(Exception):
    pass


@dataclass(frozen=True)
class StoredFile:
    original_name: str
    safe_name: str
    path: Path
    mime_type: str


def clean_stem(name: str) -> str:
    stem = Path(name).stem.strip() or "file"
    safe = secure_filename(stem) or "file"
    return safe


def unique_path(directory: Path, filename: str) -> Path:
    candidate = directory / secure_filename(filename)
    if not candidate.exists():
        return candidate
    stem = candidate.stem
    suffix = candidate.suffix
    index = 2
    while True:
        next_candidate = directory / f"{stem}_{index}{suffix}"
        if not next_candidate.exists():
            return next_candidate
        index += 1


def detect_mime(path: Path) -> str:
    with path.open("rb") as handle:
        header = handle.read(32)
    if header.startswith(b"%PDF-"):
        return "application/pdf"
    if header.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if header.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if b"ftypheic" in header or b"ftypheix" in header or b"ftypheif" in header:
        return "image/heic"
    if magic is not None:
        detected = magic.from_file(str(path), mime=True)
        if detected:
            return detected
    guessed, _ = mimetypes.guess_type(path.name)
    return guessed or "application/octet-stream"


def validate_uploaded_file(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix not in config.ALLOWED_EXTENSIONS:
        raise ProcessingError(f"不支援的副檔名：{suffix}")
    with path.open("rb") as handle:
        header = handle.read(32)
    if suffix == ".pdf" and not header.startswith(b"%PDF-"):
        raise ProcessingError(f"PDF 檔案驗證失敗：{path.name}")
    if suffix in {".jpg", ".jpeg"} and not header.startswith(b"\xff\xd8\xff"):
        raise ProcessingError(f"JPG 檔案驗證失敗：{path.name}")
    if suffix == ".png" and not header.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ProcessingError(f"PNG 檔案驗證失敗：{path.name}")
    mime_type = detect_mime(path)
    if mime_type not in config.ALLOWED_MIME_TYPES and not mime_type.startswith(config.ALLOWED_MIME_PREFIXES):
        raise ProcessingError(f"檔案格式驗證失敗：{path.name}")
    return mime_type


def save_uploads(files: Iterable[FileStorage], job_upload_dir: Path) -> list[StoredFile]:
    job_upload_dir.mkdir(parents=True, exist_ok=True)
    stored_files: list[StoredFile] = []
    for uploaded in files:
        if not uploaded or not uploaded.filename:
            continue
        if len(stored_files) >= config.MAX_FILE_COUNT:
            raise ProcessingError(f"一次最多只能上傳 {config.MAX_FILE_COUNT} 個檔案")

        original_ext = Path(uploaded.filename).suffix.lower()
        if original_ext not in config.ALLOWED_EXTENSIONS:
            raise ProcessingError(f"不支援的副檔名：{original_ext}")

        stem = clean_stem(uploaded.filename)
        safe_name = f"{stem}{original_ext}"

        target = unique_path(job_upload_dir, safe_name)
        uploaded.save(target)
        mime_type = validate_uploaded_file(target)
        stored_files.append(
            StoredFile(
                original_name=uploaded.filename,
                safe_name=target.name,
                path=target,
                mime_type=mime_type,
            )
        )
    if not stored_files:
        raise ProcessingError("沒有收到可處理的檔案")
    return stored_files


def write_manifest(directory: Path, stored_files: list[StoredFile]) -> None:
    payload = [
        {
            "original_name": item.original_name,
            "safe_name": item.safe_name,
            "path": str(item.path),
            "mime_type": item.mime_type,
        }
        for item in stored_files
    ]
    (directory / "manifest.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def load_manifest(directory: Path) -> list[StoredFile]:
    payload = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    return [
        StoredFile(
            original_name=item["original_name"],
            safe_name=item["safe_name"],
            path=Path(item["path"]),
            mime_type=item["mime_type"],
        )
        for item in payload
    ]


def pdf_to_images(
    files: list[StoredFile],
    output_zip: Path,
    image_format: str,
    keep_annotations: bool,
    progress: Progress,
) -> None:
    fmt = image_format.lower()
    if fmt not in {"jpg", "png"}:
        raise ProcessingError("圖片格式必須是 JPG 或 PNG")
    pdf_files = [item for item in files if item.path.suffix.lower() == ".pdf"]
    if not pdf_files:
        raise ProcessingError("請上傳至少一個 PDF")

    total_pages = sum(fitz.open(item.path).page_count for item in pdf_files)
    done = 0
    temp_dir = output_zip.parent / "images"
    temp_dir.mkdir(parents=True, exist_ok=True)

    for item in pdf_files:
        doc = fitz.open(item.path)
        folder = temp_dir / clean_stem(item.original_name)
        folder.mkdir(parents=True, exist_ok=True)
        matrix = fitz.Matrix(300 / 72, 300 / 72)
        for index, page in enumerate(doc, start=1):
            pix = page.get_pixmap(matrix=matrix, alpha=False, annots=keep_annotations)
            ext = "jpg" if fmt == "jpg" else "png"
            out_path = folder / f"{clean_stem(item.original_name)}_page_{index:03d}.{ext}"
            if fmt == "jpg":
                pix.pil_save(str(out_path), format="JPEG", quality=98)
            else:
                pix.save(str(out_path))
            done += 1
            progress(round(done / total_pages * 95), f"正在轉換 {item.original_name} 第 {index} 頁")
        doc.close()

    with zipfile.ZipFile(output_zip, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(temp_dir.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(temp_dir))
    shutil.rmtree(temp_dir, ignore_errors=True)
    progress(100, "圖片轉換完成")


def image_to_pdf_page(image_path: Path, page_mode: str) -> fitz.Document:
    with Image.open(image_path) as image:
        image = ImageOps.exif_transpose(image).convert("RGB")
        width, height = image.size
        temp_jpg = image_path.with_suffix(image_path.suffix + ".normalized.jpg")
        image.save(temp_jpg, "JPEG", quality=98)

    if page_mode == "a4_portrait":
        page_width, page_height = 595, 842
    elif page_mode == "a4_landscape":
        page_width, page_height = 842, 595
    elif page_mode == "original":
        page_width, page_height = width * 72 / 300, height * 72 / 300
    else:
        temp_jpg.unlink(missing_ok=True)
        raise ProcessingError("頁面尺寸設定無效")

    doc = fitz.open()
    page = doc.new_page(width=page_width, height=page_height)
    scale = min(page_width / width, page_height / height)
    draw_width = width * scale
    draw_height = height * scale
    rect = fitz.Rect(
        (page_width - draw_width) / 2,
        (page_height - draw_height) / 2,
        (page_width + draw_width) / 2,
        (page_height + draw_height) / 2,
    )
    page.insert_image(rect, filename=str(temp_jpg), keep_proportion=True)
    temp_jpg.unlink(missing_ok=True)
    return doc


def merge_files_to_pdf(files: list[StoredFile], order: list[int], output_pdf: Path, page_mode: str, progress: Progress) -> None:
    if sorted(order) != list(range(len(files))):
        raise ProcessingError("合併順序資料不完整")
    ordered_files = [files[index] for index in order]

    merged = fitz.open()
    for index, item in enumerate(ordered_files, start=1):
        suffix = item.path.suffix.lower()
        if suffix == ".pdf":
            source = fitz.open(item.path)
            merged.insert_pdf(source)
            source.close()
        elif suffix in config.ALLOWED_IMAGE_EXTENSIONS:
            source = image_to_pdf_page(item.path, page_mode)
            merged.insert_pdf(source)
            source.close()
        else:
            raise ProcessingError(f"不支援的合併檔案：{item.original_name}")
        progress(round(index / len(ordered_files) * 95), f"正在合併 {item.original_name}")
    merged.save(output_pdf, garbage=4, deflate=True)
    merged.close()
    progress(100, "PDF 合併完成")


def page_count(pdf_path: Path) -> int:
    doc = fitz.open(pdf_path)
    count = doc.page_count
    doc.close()
    return count


def render_thumbnail(pdf_path: Path, page_number: int, output_path: Path) -> None:
    doc = fitz.open(pdf_path)
    if page_number < 1 or page_number > doc.page_count:
        doc.close()
        raise ProcessingError("頁碼超出範圍")
    page = doc.load_page(page_number - 1)
    zoom = 180 / 72
    pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False, annots=True)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    pix.pil_save(str(output_path), format="JPEG", quality=85)
    doc.close()


def normalize_keep_pages(page_total: int, selected_pages: list[int], mode: str) -> list[int]:
    selected = sorted({page for page in selected_pages if 1 <= page <= page_total})
    if mode == "keep":
        keep_pages = selected
    elif mode == "delete":
        delete_set = set(selected)
        keep_pages = [page for page in range(1, page_total + 1) if page not in delete_set]
    else:
        raise ProcessingError("頁面處理模式無效")
    if not keep_pages:
        raise ProcessingError("至少必須保留一頁")
    return keep_pages


def extract_pdf_pages(source_pdf: Path, output_pdf: Path, selected_pages: list[int], mode: str, progress: Progress) -> None:
    source = fitz.open(source_pdf)
    keep_pages = normalize_keep_pages(source.page_count, selected_pages, mode)
    result = fitz.open()
    for index, page_number in enumerate(keep_pages, start=1):
        result.insert_pdf(source, from_page=page_number - 1, to_page=page_number - 1)
        progress(round(index / len(keep_pages) * 95), f"正在整理第 {page_number} 頁")
    result.save(output_pdf, garbage=4, deflate=True)
    result.close()
    source.close()
    progress(100, "PDF 頁面整理完成")


def remove_original_uploads(job_upload_dir: Path) -> None:
    for path in job_upload_dir.iterdir():
        if path.is_file() and path.name != "manifest.json":
            path.unlink(missing_ok=True)


def create_qr_code(download_url: str, output_path: Path) -> None:
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=10, border=3)
    qr.add_data(download_url)
    qr.make(fit=True)
    image = qr.make_image(fill_color="#18202d", back_color="white").convert("RGB")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_path)


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        "C:/Windows/Fonts/msjh.ttc",
        "C:/Windows/Fonts/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for candidate in candidates:
        if Path(candidate).exists():
            return ImageFont.truetype(candidate, size)
    return ImageFont.load_default()


def create_download_info_image(download_url: str, expires_at: datetime, output_path: Path) -> None:
    qr_path = output_path.with_name("download_qr.png")
    if not qr_path.exists():
        create_qr_code(download_url, qr_path)
    qr_image = Image.open(qr_path).resize((360, 360))
    expires_local = expires_at.astimezone().strftime("%Y-%m-%d %H:%M")

    canvas = Image.new("RGB", (920, 560), "#f6fbff")
    draw = ImageDraw.Draw(canvas)
    draw.rounded_rectangle((24, 24, 896, 536), radius=34, fill="#ffffff", outline="#d9e6ef", width=2)
    draw.text((64, 58), "PDF 轉換器下載資訊", fill="#18202d", font=_font(42))
    draw.text((64, 125), f"有效下載時間：{expires_local}", fill="#617084", font=_font(28))
    draw.text((64, 178), "掃描右側 QR CODE，或使用下方連結下載。", fill="#617084", font=_font(24))

    link_font = _font(21)
    wrapped = []
    current = ""
    for char in download_url:
        trial = current + char
        if draw.textlength(trial, font=link_font) > 470:
            wrapped.append(current)
            current = char
        else:
            current = trial
    if current:
        wrapped.append(current)
    y = 245
    for line in wrapped[:4]:
        draw.text((64, y), line, fill="#0f8bff", font=link_font)
        y += 30

    canvas.paste(qr_image, (500, 125))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output_path)
