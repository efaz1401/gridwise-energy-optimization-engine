"""Deterministic validation and repair of model output.

An entry that fails any check is DEMOTED to no_op rather than removed: a
missing entry is a schema failure that costs more than a wrong directive.
"""
from __future__ import annotations

import logging
import math
import re
from typing import Any

from .timeparse import parse_window

log = logging.getLogger("gridwise.guardrails")

FRACTION_WORDS = {
    r"\bhalf\b": 0.5,
    r"\bone[- ]?fifth\b|\ba fifth\b": 0.2,
    r"\bone[- ]?quarter\b|\ba quarter\b|\bone[- ]?fourth\b": 0.25,
    r"\bthree[- ]?quarters\b": 0.75,
    r"\bone[- ]?third\b|\ba third\b": 1 / 3,
    r"\btwo[- ]?thirds\b": 2 / 3,
}

_REDUCTION = re.compile(
    r"(\d{1,3}(?:\.\d+)?)\s*(?:%|percent)\s*(?:of\s+a\s+)?"
    r"(?:reduction|drop|decrease|decline|loss|less|lower|cut)", re.I)
_REDUCTION_ALT = re.compile(
    r"(?:reduc\w*|drop\w*|decreas\w*|down|cut|fall\w*|lower\w*)\s+(?:by|of)\s*"
    r"(\d{1,3}(?:\.\d+)?)\s*(?:%|percent)", re.I)
_REMAIN = re.compile(
    r"(?:to|at|about|around|roughly|approximately|only|treated as|leave\w*)"
    r"\D{0,20}?(\d{1,3}(?:\.\d+)?)\s*(?:%|percent)", re.I)
_PCT_CAPACITY = re.compile(
    r"(\d{1,3}(?:\.\d+)?)\s*(?:%|percent)\s*(?:of\s+)?(?:the\s+)?"
    r"(?:battery|capacity|total|rated|pack)", re.I)


def _no_op(idx: int, why: str) -> dict[str, Any]:
    return {
        "note_index": idx,
        "applies": False,
        "directive_type": "no_op",
        "structured_adjustment": None,
        "explanation": why,
    }


def _clean_hours(raw: Any) -> list[int] | None:
    if not isinstance(raw, (list, tuple)) or not raw:
        return None
    out = set()
    for v in raw:
        if isinstance(v, bool):
            return None
        if isinstance(v, float) and not v.is_integer():
            return None
        try:
            iv = int(v)
        except (TypeError, ValueError):
            return None
        if not 0 <= iv <= 23:
            return None
        out.add(iv)
    return sorted(out) or None


def _num(raw: Any) -> float | None:
    if isinstance(raw, bool) or raw is None:
        return None
    try:
        f = float(raw)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def _fix_factor(note: str, factor: float | None) -> float | None:
    """Enforce: factor is the fraction that REMAINS."""
    pct_remaining = None
    pct_lost = None

    m = _REDUCTION.search(note) or _REDUCTION_ALT.search(note)
    if m:
        pct_lost = float(m.group(1))
    m2 = _REMAIN.search(note)
    if m2:
        pct_remaining = float(m2.group(1))

    for pattern, value in FRACTION_WORDS.items():
        if re.search(pattern, note, re.I):
            if re.search(r"(reduc|drop|decreas|cut|less|lower)\w*\s+(by|of)\s*$",
                         note[:re.search(pattern, note, re.I).start()], re.I):
                pct_lost = value * 100
            else:
                pct_remaining = value * 100
            break

    if pct_lost is not None and 0 <= pct_lost <= 100:
        target = round(1 - pct_lost / 100, 6)
        if factor is None or abs(factor - target) > 1e-6:
            log.info("factor corrected %s -> %s (%.0f%% reduction)",
                     factor, target, pct_lost)
        return target
    if pct_remaining is not None and 0 <= pct_remaining <= 100:
        target = round(pct_remaining / 100, 6)
        if factor is None or abs(factor - target) > 1e-6:
            log.info("factor corrected %s -> %s (remaining)", factor, target)
        return target
    return factor


def _fix_reserve(note: str, value: float | None,
                 capacity: float) -> float | None:
    m = _PCT_CAPACITY.search(note)
    if m:
        pct = float(m.group(1))
        if 0 <= pct <= 100:
            target = round(capacity * pct / 100, 6)
            if value is None or abs(value - target) > 1e-6:
                log.info("reserve corrected %s -> %s (%.0f%% of %s)",
                         value, target, pct, capacity)
            return target
    return value


def _fix_hours(note: str, hours: list[int] | None) -> list[int] | None:
    parsed, confidence = parse_window(note)
    if not parsed:
        return hours
    if confidence == "high" and parsed != hours:
        log.info("hours corrected %s -> %s", hours, parsed)
        return parsed
    if hours is None:
        return parsed
    return hours


def normalize(raw_entries: list[dict[str, Any]], notes: list[str],
              battery: dict) -> list[dict[str, Any]]:
    """Exactly one clean entry per note, in note_index order."""
    capacity = float(battery["capacity_kwh"])
    by_index: dict[int, dict[str, Any]] = {}
    for e in raw_entries or []:
        if not isinstance(e, dict):
            continue
        idx = e.get("note_index")
        if isinstance(idx, bool) or not isinstance(idx, int):
            continue
        if 0 <= idx < len(notes) and idx not in by_index:
            by_index[idx] = e

    result: list[dict[str, Any]] = []
    for i, note in enumerate(notes):
        entry = by_index.get(i)
        if entry is None:
            result.append(_no_op(i, "No interpretation was produced for this "
                                    "note; treated as not affecting the schedule."))
            continue

        dtype = entry.get("directive_type")
        explanation = str(entry.get("explanation") or "").strip()[:500]
        if dtype not in {
            "solar_reduction", "minimum_battery_reserve", "no_charge_window",
            "no_discharge_window", "max_grid_window", "no_op",
        }:
            result.append(_no_op(i, explanation or
                                 "Unsupported directive type; treated as no_op."))
            continue

        if dtype == "no_op" or entry.get("applies") is False:
            result.append(_no_op(i, explanation or
                                 "This note does not affect today's schedule."))
            continue

        hours = _fix_hours(note, _clean_hours(entry.get("hours")))
        if not hours:
            result.append(_no_op(i, explanation or
                                 "No valid hour window could be established."))
            continue

        adj: dict[str, Any] = {"hours": hours}

        if dtype == "solar_reduction":
            factor = _fix_factor(note, _num(entry.get("factor")))
            if factor is None or not 0.0 <= factor <= 1.0:
                result.append(_no_op(i, explanation or
                                     "Solar factor outside the valid range."))
                continue
            adj["factor"] = round(factor, 6)

        elif dtype == "minimum_battery_reserve":
            val = _fix_reserve(note, _num(entry.get("minimum_energy_kwh")),
                               capacity)
            if val is None or not 0.0 <= val <= capacity:
                result.append(_no_op(i, explanation or
                                     "Reserve value outside the valid range."))
                continue
            adj["minimum_energy_kwh"] = round(val, 6)

        elif dtype == "max_grid_window":
            val = _num(entry.get("max_grid_kwh"))
            if val is None or val < 0:
                result.append(_no_op(i, explanation or
                                     "Grid cap value is invalid."))
                continue
            adj["max_grid_kwh"] = round(val, 6)

        result.append({
            "note_index": i,
            "applies": True,
            "directive_type": dtype,
            "structured_adjustment": adj,
            "explanation": explanation or f"Interpreted as {dtype}.",
        })

    return result
