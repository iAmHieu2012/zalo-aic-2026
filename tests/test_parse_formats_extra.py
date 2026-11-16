"""Money and date formats beyond the train files: currency prefix, accounting negative,
'45k5'; Vietnamese long dates, weekday/'ngày' prefix, y/m/d, 2-digit year, time first,
'14h30', English month names. Formats train already reads are unchanged
(checked over every train cell when this was added)."""

import datetime

import pytest

from datamate.parse.dates import parse_date, parse_timestamp
from datamate.parse.money import parse_money


@pytest.mark.parametrize("raw,want", [
    ("₫250.000", 250000), ("đ250.000", 250000), ("VND 250,000", 250000),
    ("250.000₫", 250000), ("(50.000)", -50000), ("45k5", 45500),
    ("250.000đ", 250000), ("1tr2", 1200000), ("-50.000", -50000),
])
def test_money_formats(raw: str, want: int) -> None:
    assert parse_money(raw) == want


D = datetime.date(2025, 2, 1)


@pytest.mark.parametrize("raw", [
    "1 tháng 2 năm 2025", "Ngày 01 tháng 02, 2025", "ngày 1/2/2025", "2025/02/01",
    "01/02/25", "Feb 1, 2025", "1-Feb-2025", "Thứ 7, 01/02/2025", "01/02/2025",
])
def test_date_formats(raw: str) -> None:
    assert parse_date(raw) == D


@pytest.mark.parametrize("raw", ["14:30 01/02/2025", "01/02/2025 14h30", "01/02/2025 14:30"])
def test_timestamp_formats(raw: str) -> None:
    assert parse_timestamp(raw) == datetime.datetime(2025, 2, 1, 14, 30)


def test_day_month_without_year_still_needs_default_year() -> None:
    assert parse_date("1/2") is None
    assert parse_date("1/2", default_year=2025) == D
