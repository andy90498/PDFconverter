import pytest

from processor import ProcessingError, normalize_keep_pages


def test_keep_mode_uses_positive_page_list():
    assert normalize_keep_pages(5, [3, 1, 3, 9], "keep") == [1, 3]


def test_delete_mode_converts_to_final_keep_pages():
    assert normalize_keep_pages(5, [2, 4], "delete") == [1, 3, 5]


def test_cannot_remove_every_page():
    with pytest.raises(ProcessingError):
        normalize_keep_pages(2, [1, 2], "delete")
