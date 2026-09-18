"""Deterministic whole-hour window extraction from operator notes.

Returns (hours, confidence). confidence is "high" when explicit clock markers
(am/pm, HH:MM, noon, midnight) were found, "low" for bare/word numbers.
Windows are START-INCLUSIVE, END-EXCLUSIVE.
"""
from __future__ import annotations

import re

WORD_NUM = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
}

# numbers that are clearly quantities, not clock times
_QUANTITY = re.compile(r"\d+(?:\.\d+)?\s*(?:kwh|kw|%|percent|bdt|taka)", re.I)


def _mask_quantities(text: str) -> str:
    return _QUANTITY.sub(lambda m: "#" * len(m.group(0)), text)


def _to24(hour12: int, meridiem: str | None) -> int | None:
    if hour12 is None:
        return None
    if meridiem == "am":
        return 0 if hour12 == 12 else hour12
    if meridiem == "pm":
        return 12 if hour12 == 12 else (hour12 + 12) % 24
    return hour12


def _span(start: int, end: int) -> list[int]:
    if start == end:
        return []
    if end > start:
        return list(range(start, end))
    return list(range(start, 24)) + list(range(0, end))


def _collect_marked(text: str) -> list[tuple[int, int, str | None]]:
    """(position, hour_value_12_or_24, meridiem_or_None)"""
    out: list[tuple[int, int, str | None]] = []
    for m in re.finditer(r"\b(\d{1,2}):(\d{2})\s*(am|pm)?\b", text, re.I):
        h = int(m.group(1))
        mer = (m.group(3) or "").lower() or None
        if mer is None and 0 <= h <= 23:
            out.append((m.start(), h, "abs"))
        elif 1 <= h <= 12:
            out.append((m.start(), h, mer))
    for m in re.finditer(r"\b(\d{1,2})\s*(a\.?m\.?|p\.?m\.?)", text, re.I):
        h = int(m.group(1))
        if 1 <= h <= 12:
            out.append((m.start(), h, m.group(2)[0].lower() + "m"))
    for m in re.finditer(r"\bnoon|\bmidday\b", text, re.I):
        out.append((m.start(), 12, "abs"))
    for m in re.finditer(r"\bmidnight\b", text, re.I):
        out.append((m.start(), 0, "abs"))
    out.sort(key=lambda t: t[0])
    # de-duplicate overlapping matches at the same position
    deduped: list[tuple[int, int, str | None]] = []
    for item in out:
        if deduped and abs(item[0] - deduped[-1][0]) <= 1:
            continue
        deduped.append(item)
    return deduped


def _resolve_pair(a: tuple[int, int, str | None],
                  b: tuple[int, int, str | None]) -> tuple[int, int] | None:
    _, ha, ma = a
    _, hb, mb = b
    if ma == "abs" and mb == "abs":
        return ha, hb
    if ma == "abs":
        s = ha
        e = _to24(hb, mb) if mb else _daytime(hb)
        return s, e
    if mb == "abs":
        s = _to24(ha, ma) if ma else _daytime(ha)
        return s, hb
    if ma and mb:
        return _to24(ha, ma), _to24(hb, mb)
    if mb and not ma:
        s = _to24(ha, mb)
        e = _to24(hb, mb)
        if s >= e:  # e.g. "from 11 to 2 PM"
            s = _to24(ha, "am" if mb == "pm" else "pm")
        return s, e
    if ma and not mb:
        s = _to24(ha, ma)
        e = _to24(hb, ma)
        if e <= s:  # e.g. "from 11 AM to 2"
            e = _to24(hb, "pm" if ma == "am" else "am")
        return s, e
    return _daytime(ha), _daytime(hb)


def _daytime(h12: int) -> int:
    """Bare hour with no meridiem: 1-7 reads as afternoon, 8-12 as morning."""
    if h12 == 12:
        return 12
    if 1 <= h12 <= 7:
        return h12 + 12
    return h12


def parse_window(note: str) -> tuple[list[int], str | None]:
    text = _mask_quantities(note)

    # Path 1: shared meridiem across a dash/word range -> "1-3 PM", "6 to 9 pm"
    m = re.search(
        r"\b(\d{1,2})\s*(?:-|–|—|to|until|till|through|and)\s*(\d{1,2})\s*"
        r"(a\.?m\.?|p\.?m\.?)",
        text, re.I,
    )
    if m:
        mer = m.group(3)[0].lower() + "m"
        s = _to24(int(m.group(1)), mer)
        e = _to24(int(m.group(2)), mer)
        if s is not None and e is not None:
            hrs = _span(s, e)
            if hrs:
                return hrs, "high"

    # Path 2: two explicitly marked clock tokens
    marked = _collect_marked(text)
    if len(marked) >= 2:
        pair = _resolve_pair(marked[0], marked[1])
        if pair and pair[0] is not None and pair[1] is not None:
            hrs = _span(pair[0] % 24, pair[1] % 24)
            if hrs:
                return hrs, "high"

    # Path 3: word numbers or bare digits inside an explicit range construct
    m = re.search(
        r"\b(?:from|between)\s+([a-z]+|\d{1,2})\s+(?:to|until|till|and|through)"
        r"\s+([a-z]+|\d{1,2})\b",
        text, re.I,
    )
    if m:
        def val(tok: str) -> int | None:
            tok = tok.lower()
            if tok.isdigit():
                return int(tok)
            return WORD_NUM.get(tok)
        a, b = val(m.group(1)), val(m.group(2))
        if a is not None and b is not None and 0 <= a <= 23 and 0 <= b <= 23:
            s = _daytime(a) if a <= 12 else a
            e = _daytime(b) if b <= 12 else b
            hrs = _span(s, e)
            if hrs:
                return hrs, "low"

    return [], None
