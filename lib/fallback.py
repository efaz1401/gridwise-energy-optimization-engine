"""Always-feasible plan of last resort: never cycle the battery."""
from __future__ import annotations

import re
from typing import Any


def trivial_plan(req: dict, directives: list[dict]) -> dict[str, Any]:
    from .optimizer import Bounds
    bd = Bounds(req, directives)
    plan = []
    for h in range(24):
        solar = min(bd.eff_solar[h], bd.demand[h])
        grid = max(bd.demand[h] - solar, 0.0)
        plan.append({
            "hour": h,
            "grid_kwh": round(grid, 6),
            "solar_used_kwh": round(solar, 6),
            "battery_action": "idle",
            "battery_kwh": 0.0,
            "battery_energy_after_kwh": round(bd.initial, 6),
        })
    return {
        "hourly_plan": plan,
        "total_grid_kwh": round(sum(p["grid_kwh"] for p in plan), 6),
        "total_cost_bdt": round(
            sum(p["grid_kwh"] * bd.tariff[p["hour"]] for p in plan), 6),
        "peak_grid_kwh": round(max(p["grid_kwh"] for p in plan), 6),
    }


def heuristic_extract(notes: list[str], battery: dict) -> list[dict[str, Any]]:
    """Deterministic heuristic extraction when LLM is offline or quota-limited."""
    from .guardrails import _fix_factor, _fix_reserve, _num
    from .timeparse import parse_window

    cap = float(battery.get("capacity_kwh", 200.0))
    out = []
    for i, text in enumerate(notes):
        if re.search(r"\b(menu|cafeteria|library|seminar|registration|deadline|sports|club|notice)\b", text, re.I):
            out.append({"note_index": i, "directive_type": "no_op", "applies": False, "explanation": "Non-operational note."})
            continue

        fixed_text = re.sub(r"\b24:00\b", "midnight", text)
        hrs, _ = parse_window(fixed_text)
        if not hrs and "22:00 to 24:00" in text:
            hrs = [22, 23]
        if not hrs:
            out.append({"note_index": i, "directive_type": "no_op", "applies": False, "explanation": "No valid window established."})
            continue

        if re.search(r"\b(solar|pv|panel|cloud|inverter|sunlight)\b", text, re.I):
            f = _fix_factor(text, 0.5)
            out.append({"note_index": i, "directive_type": "solar_reduction", "applies": True, "hours": hrs, "factor": f, "explanation": "Solar curtailment window."})
        elif re.search(r"\b(discharg\w*|export)\b", text, re.I):
            out.append({"note_index": i, "directive_type": "no_discharge_window", "applies": True, "hours": hrs, "explanation": "Battery discharge restricted."})
        elif re.search(r"\bcharg\w*\b", text, re.I):
            out.append({"note_index": i, "directive_type": "no_charge_window", "applies": True, "hours": hrs, "explanation": "Battery charging restricted."})
        elif re.search(r"\b(grid|feeder|transformer|substation|import|intake)\b", text, re.I):
            m = re.search(r"(\d+(?:\.\d+)?)\s*(?:kwh|kw)", text, re.I)
            v = _num(m.group(1)) if m else None
            out.append({"note_index": i, "directive_type": "max_grid_window", "applies": True, "hours": hrs, "max_grid_kwh": v, "explanation": "Grid import ceiling enforced."})
        elif re.search(r"\b(reserve|retained|floor|stored|keep|in the battery)\b", text, re.I):
            m = re.search(r"(\d+(?:\.\d+)?)\s*(?:kwh|%)", text, re.I)
            v = _fix_reserve(text, _num(m.group(1)) if m else None, cap)
            out.append({"note_index": i, "directive_type": "minimum_battery_reserve", "applies": True, "hours": hrs, "minimum_energy_kwh": v, "explanation": "Minimum reserve level held."})
        else:
            out.append({"note_index": i, "directive_type": "no_op", "applies": False, "explanation": "Unrelated operator note."})
    return out
