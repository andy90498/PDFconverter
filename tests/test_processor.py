from pathlib import Path

from PIL import Image

from processor import _safe_filename, image_to_pdf_page


def test_image_to_pdf_page_creates_single_page(tmp_path: Path):
    source = tmp_path / "photo.jpg"
    Image.new("RGB", (300, 200), "white").save(source)

    doc = image_to_pdf_page(source, "a4_portrait")

    assert doc.page_count == 1
    assert round(doc[0].rect.width) == 595
    assert round(doc[0].rect.height) == 842
    doc.close()


def test_safe_filename_preserves_chinese_and_supported_symbols():
    assert _safe_filename("報表-2026_09(最終)@#$!.pdf") == "報表-2026_09(最終)@#$!.pdf"


def test_safe_filename_removes_path_parts_and_windows_invalid_characters():
    assert _safe_filename("資料夾/報表:最終?.pdf") == "報表_最終_.pdf"


def test_clean_stem_keeps_chinese_for_output_names():
    from processor import clean_stem

    assert clean_stem("月結報表(最終版).pdf") == "月結報表(最終版)"
