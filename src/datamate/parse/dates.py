from __future__ import annotations

import datetime
import re
import unicodedata
from decimal import Decimal, InvalidOperation

_YEAR_HINT_RE = re.compile(r"(?<!\d)((?:19|20)\d\d)(?!\d)")

_ISO_DATETIME_RE = re.compile(
    r"^(?P<y>\d{4})-(?P<m>\d{1,2})-(?P<d>\d{1,2})"
    r"(?:[ T](?P<hh>\d{1,2}):(?P<mm>\d{2})(?::(?P<ss>\d{2}))?)?$"
)

_DMY_RE = re.compile(
    r"^(?P<d>\d{1,2})[/.\-](?P<m>\d{1,2})[/.\-](?P<y>\d{4})"
    r"(?:\s+(?P<hh>\d{1,2}):(?P<mm>\d{2})(?::(?P<ss>\d{2}))?)?$"
)

_DM_RE = re.compile(
    r"^(?P<d>\d{1,2})[/.\-](?P<m>\d{1,2})"
    r"(?:\s+(?P<hh>\d{1,2}):(?P<mm>\d{2})(?::(?P<ss>\d{2}))?)?$"
)

_THG_RE = re.compile(
    r"^(?P<d>\d{1,2})\s+thg\s+(?P<m>\d{1,2})(?:\s+(?P<y>\d{4}))?"
    r"(?:\s+(?P<hh>\d{1,2}):(?P<mm>\d{2})(?::(?P<ss>\d{2}))?)?$",
    re.IGNORECASE,
)

_SERIAL_RE = re.compile(r"^[+-]?\d+(?:\.\d+)?$")

_EXCEL_EPOCH = datetime.datetime(1899, 12, 30)


_MONTHS_EN = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}
_WEEKDAY_PREFIX_RE = re.compile(
    r"^(?:thứ\s*(?:hai|ba|tư|năm|sáu|bảy|[2-7])|chủ\s*nhật|cn|t[2-7])\s*[,\-]?\s*", re.IGNORECASE)
_NGAY_PREFIX_RE = re.compile(r"^ngày\s+", re.IGNORECASE)
_VN_LONG_RE = re.compile(
    r"^(\d{1,2})\s+tháng\s+(\d{1,2})(?:\s*(?:năm|,)\s*|\s+)(\d{4})(.*)$", re.IGNORECASE)
_HOUR_H_RE = re.compile(r"(?<!\d)(\d{1,2})\s*[hg]\s*(\d{2})(?!\d)", re.IGNORECASE)
_TIME_FIRST_RE = re.compile(r"^(\d{1,2}:\d{2}(?::\d{2})?)\s*,?\s+(.+)$")
_YMD_SLASH_RE = re.compile(r"^(\d{4})[/.](\d{1,2})[/.](\d{1,2})(.*)$")
_DMY_SHORT_RE = re.compile(r"^(\d{1,2})([/.\-])(\d{1,2})\2(\d{2})(\s.*)?$")
_EN_MDY_RE = re.compile(r"^([a-z]{3})[a-z]*\.?\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(\d{4})(.*)$")
_EN_DMY_RE = re.compile(r"^(\d{1,2})[\s\-]([a-z]{3})[a-z]*\.?[\s\-,]+(\d{4})(.*)$")


def _rewrite_date_text(s: str) -> str:
    """Other common ways of writing a date, rewritten to a form the patterns above read.
    Used only when the text as written does not parse."""
    t = s.strip().rstrip(",.").strip()
    t = _WEEKDAY_PREFIX_RE.sub("", t)
    t = _NGAY_PREFIX_RE.sub("", t)
    t = _HOUR_H_RE.sub(lambda m: f"{m.group(1)}:{m.group(2)}", t)
    m = _TIME_FIRST_RE.match(t)
    if m is not None:
        t = f"{m.group(2)} {m.group(1)}"
    m = _VN_LONG_RE.match(t)
    if m is not None:
        t = f"{m.group(1)}/{m.group(2)}/{m.group(3)}{m.group(4)}"
    m = _YMD_SLASH_RE.match(t)
    if m is not None:
        t = f"{m.group(1)}-{m.group(2)}-{m.group(3)}{m.group(4)}"
    m = _DMY_SHORT_RE.match(t)
    if m is not None:
        t = f"{m.group(1)}/{m.group(3)}/20{m.group(4)}{m.group(5) or ''}"
    low = t.lower()
    for rx, order in ((_EN_MDY_RE, "mdy"), (_EN_DMY_RE, "dmy")):
        m = rx.match(low)
        if m is not None:
            a, b, y, rest = m.groups()
            mon, day = (a, b) if order == "mdy" else (b, a)
            if mon in _MONTHS_EN:
                t = f"{int(day)}/{_MONTHS_EN[mon]}/{y}{rest}"
            break
    return " ".join(t.split())


def _clean_input(raw: str | None) -> str | None:
    if raw is None or not isinstance(raw, str):
        return None
    s = unicodedata.normalize("NFC", raw).replace("\xa0", " ").strip()
    return s if s else None


def year_hint(sheet: str | None, file: str | None) -> int | None:
    for candidate in (sheet, file):
        if candidate is None:
            continue
        m = _YEAR_HINT_RE.search(candidate)
        if m is not None:
            return int(m.group(1))
    return None


def _safe_date(year: int, month: int, day: int) -> datetime.date | None:
    try:
        return datetime.date(year, month, day)
    except ValueError:
        return None


def _safe_datetime(
    year: int, month: int, day: int, hour: int, minute: int, second: int
) -> datetime.datetime | None:
    try:
        return datetime.datetime(year, month, day, hour, minute, second)
    except ValueError:
        return None


def parse_date(raw: str | None, default_year: int | None = None) -> datetime.date | None:
    s = _clean_input(raw)
    if s is None:
        return None
    got = _parse_date_text(s, default_year)
    if got is None:
        alt = _rewrite_date_text(s)
        if alt and alt != s:
            got = _parse_date_text(alt, default_year)
    return got


def _parse_date_text(s: str, default_year: int | None) -> datetime.date | None:

    m = _ISO_DATETIME_RE.match(s)
    if m is not None:
        return _safe_date(int(m.group("y")), int(m.group("m")), int(m.group("d")))

    m = _DMY_RE.match(s)
    if m is not None:
        return _safe_date(int(m.group("y")), int(m.group("m")), int(m.group("d")))

    m = _THG_RE.match(s)
    if m is not None:
        yr_str = m.group("y")
        yr = int(yr_str) if yr_str is not None else default_year
        if yr is None:
            return None
        return _safe_date(yr, int(m.group("m")), int(m.group("d")))

    m = _DM_RE.match(s)
    if m is not None:
        if default_year is None:
            return None
        return _safe_date(default_year, int(m.group("m")), int(m.group("d")))

    if _SERIAL_RE.match(s):
        try:
            val = Decimal(s)
        except InvalidOperation:
            return None
        if Decimal(20000) <= val <= Decimal(80000):
            days = int(val)
            return (_EXCEL_EPOCH + datetime.timedelta(days=days)).date()

    return None


def parse_timestamp(
    raw: str | None, default_year: int | None = None
) -> datetime.datetime | None:
    s = _clean_input(raw)
    if s is None:
        return None
    got = _parse_timestamp_text(s, default_year)
    if got is None:
        alt = _rewrite_date_text(s)
        if alt and alt != s:
            got = _parse_timestamp_text(alt, default_year)
    return got


def _parse_timestamp_text(
    s: str, default_year: int | None
) -> datetime.datetime | None:

    for pattern in (_ISO_DATETIME_RE, _DMY_RE, _THG_RE, _DM_RE):
        m = pattern.match(s)
        if m is not None:
            if m.group("hh") is None:
                return None
            yr_str = m.groupdict().get("y")
            yr = int(yr_str) if yr_str is not None else default_year
            if yr is None:
                return None
            hh = int(m.group("hh"))
            mm = int(m.group("mm"))
            ss = int(m.group("ss")) if m.group("ss") is not None else 0
            return _safe_datetime(yr, int(m.group("m")), int(m.group("d")), hh, mm, ss)

    if _SERIAL_RE.match(s):
        try:
            val = Decimal(s)
        except InvalidOperation:
            return None
        if Decimal(20000) <= val <= Decimal(80000):
            days = int(val)
            frac = val - Decimal(days)
            if frac <= 0:
                return None
            total_seconds = int((frac * Decimal(86400)).quantize(Decimal(1)))
            return _EXCEL_EPOCH + datetime.timedelta(days=days, seconds=total_seconds)

    return None
