from pathlib import Path

import pytest

from processor import ProcessingError, validate_uploaded_file


def test_rejects_fake_pdf(tmp_path: Path):
    fake = tmp_path / "fake.pdf"
    fake.write_text("not a pdf", encoding="utf-8")

    with pytest.raises(ProcessingError):
        validate_uploaded_file(fake)


def test_accepts_png_header(tmp_path: Path):
    png = tmp_path / "image.png"
    png.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\0" * 32)

    assert validate_uploaded_file(png) == "image/png"
