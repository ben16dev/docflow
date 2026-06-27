import pytest

from scripts.common.pdf_ranges import (
    parse_ranges,
    expand_ranges_to_pages,
    ranges_to_pages_set,
)


def test_parse_ranges_single_page():
    assert parse_ranges("5") == [(5, 5)]


def test_parse_ranges_multiple_ranges():
    assert parse_ranges("1-3, 5, 8-10") == [(1, 3), (5, 5), (8, 10)]


def test_parse_ranges_rejects_empty():
    with pytest.raises(ValueError):
        parse_ranges("")


def test_parse_ranges_rejects_invalid_range_order():
    with pytest.raises(ValueError):
        parse_ranges("5-2")


def test_parse_ranges_rejects_non_numeric():
    with pytest.raises(ValueError):
        parse_ranges("a-b")


def test_expand_ranges_to_pages():
    assert expand_ranges_to_pages([(1, 3), (5, 5)], 10) == [1, 2, 3, 5]


def test_expand_ranges_rejects_out_of_bounds():
    with pytest.raises(ValueError):
        expand_ranges_to_pages([(1, 11)], 10)


def test_ranges_to_pages_set():
    assert ranges_to_pages_set([(1, 3), (3, 4)], 10) == {1, 2, 3, 4}