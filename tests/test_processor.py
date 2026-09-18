from pathlib import Path

from PIL import Image

from processor import image_to_pdf_page


def test_image_to_pdf_page_creates_single_page(tmp_path: Path):
    source = tmp_path / "photo.jpg"
    Image.new("RGB", (300, 200), "white").save(source)

    doc = image_to_pdf_page(source, "a4_portrait")

    assert doc.page_count == 1
    assert round(doc[0].rect.width) == 595
    assert round(doc[0].rect.height) == 842
    doc.close()
