"""Independent replay validator - the single most important file here."""
from __future__ import annotations

import math
from typing import Any

TOL = 0.01


def _fin(x: Any) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) \
        and math.isfinite(float(x))


def validate_plan(req: dict, payload: dict, truth) -> list[str]:
    """Replay hourly_plan against ground-truth bounds. Empty list == valid."""
    issues: list[str] = []
    plan = payload.get("hourly_plan")
    if not isinstance(plan, list) or len(plan) != 24:
        return ["hourly_plan must contain exactly 24 entries"]
    if [p.get("hour") for p in plan] != list(range(24)):
        return ["hourly_plan hours must be 0..23 in ascending order"]

    energy = truth.initial
    total_grid = 0.0
    total_cost = 0.0
    peak = 0.0

    for h, p in enumerate(plan):
        g, s = p.get("grid_kwh"), p.get("solar_used_kwh")
        act, amt = p.get("battery_action"), p.get("battery_kwh")
        after = p.get("battery_energy_after_kwh")

        for name, val in (("grid_kwh", g), ("solar_used_kwh", s),
                          ("battery_kwh", amt),
                          ("battery_energy_after_kwh", after)):
            if not _fin(val):
                issues.append(f"h{h}: {name} not finite")
        if issues:
            return issues
        if g < -TOL or s < -TOL or amt < -TOL:
            issues.append(f"h{h}: negative energy value")
        if act not in ("charge", "discharge", "idle"):
            issues.append(f"h{h}: invalid battery_action {act!r}")
            continue
        if act == "idle" and abs(amt) > TOL:
            issues.append(f"h{h}: idle hour has battery_kwh={amt}")

        charge = amt if act == "charge" else 0.0
        discharge = amt if act == "discharge" else 0.0

        if s > truth.eff_solar[h] + TOL:
            issues.append(
                f"h{h}: solar_used {s} exceeds effective solar "
                f"{truth.eff_solar[h]:.4f}")
        if charge > truth.cmax[h] + TOL:
            issues.append(f"h{h}: charge {charge} exceeds limit {truth.cmax[h]}")
        if discharge > truth.dmax[h] + TOL:
            issues.append(
                f"h{h}: discharge {discharge} exceeds limit {truth.dmax[h]}")
        if g > truth.gmax[h] + TOL:
            issues.append(f"h{h}: grid {g} exceeds cap {truth.gmax[h]}")

        lhs = g + s + discharge
        rhs = truth.demand[h] + charge
        if abs(lhs - rhs) > TOL:
            issues.append(
                f"h{h}: energy balance {lhs:.4f} != {rhs:.4f}")

        energy = energy + charge - discharge
        if abs(energy - after) > TOL:
            issues.append(
                f"h{h}: battery_energy_after {after} != replayed {energy:.4f}")
        energy = after
        if energy < truth.reserve[h] - TOL:
            issues.append(
                f"h{h}: battery {energy} below reserve {truth.reserve[h]}")
        if energy > truth.capacity + TOL:
            issues.append(f"h{h}: battery {energy} above capacity")

        total_grid += g
        total_cost += g * truth.tariff[h]
        peak = max(peak, g)

    if abs(energy - truth.initial) > TOL:
        issues.append(
            f"end-of-day battery {energy:.4f} != initial {truth.initial}")

    for name, computed in (("total_grid_kwh", total_grid),
                           ("total_cost_bdt", total_cost),
                           ("peak_grid_kwh", peak)):
        reported = payload.get(name)
        if not _fin(reported) or abs(float(reported) - computed) > TOL:
            issues.append(f"{name} {reported} != recomputed {computed:.4f}")

    return issues


def validate_interpretation(notes: list[str], entries: list[dict],
                            capacity: float) -> list[str]:
    issues: list[str] = []
    if len(entries) != len(notes):
        issues.append(
            f"expected {len(notes)} interpretation entries, got {len(entries)}")
    seen = [e.get("note_index") for e in entries]
    if seen != list(range(len(notes))):
        issues.append(f"note_index sequence {seen} is not 0..{len(notes) - 1}")

    shapes = {
        "solar_reduction": ("hours", "factor"),
        "minimum_battery_reserve": ("hours", "minimum_energy_kwh"),
        "no_charge_window": ("hours",),
        "no_discharge_window": ("hours",),
        "max_grid_window": ("hours", "max_grid_kwh"),
    }

    for e in entries:
        i = e.get("note_index")
        t = e.get("directive_type")
        adj = e.get("structured_adjustment")
        applies = e.get("applies")
        if t == "no_op":
            if applies is not False or adj is not None:
                issues.append(f"note {i}: no_op must be applies=false, adj=null")
            continue
        if t not in shapes:
            issues.append(f"note {i}: unsupported directive_type {t!r}")
            continue
        if applies is not True:
            issues.append(f"note {i}: non-no_op directive must have applies=true")
        if not isinstance(adj, dict):
            issues.append(f"note {i}: structured_adjustment must be an object")
            continue
        if set(adj) != set(shapes[t]):
            issues.append(f"note {i}: adjustment keys {sorted(adj)} != "
                          f"{sorted(shapes[t])}")
        hrs = adj.get("hours")
        if (not isinstance(hrs, list) or not hrs
                or hrs != sorted(set(hrs))
                or any(not isinstance(h, int) or isinstance(h, bool)
                       or not 0 <= h <= 23 for h in hrs)):
            issues.append(f"note {i}: hours must be unique ints 0-23 ascending")
        if t == "solar_reduction":
            f = adj.get("factor")
            if not _fin(f) or not 0.0 <= float(f) <= 1.0:
                issues.append(f"note {i}: factor out of range")
        if t == "minimum_battery_reserve":
            v = adj.get("minimum_energy_kwh")
            if not _fin(v) or not 0.0 <= float(v) <= capacity:
                issues.append(f"note {i}: reserve out of range")
        if t == "max_grid_window":
            v = adj.get("max_grid_kwh")
            if not _fin(v) or float(v) < 0:
                issues.append(f"note {i}: max_grid_kwh out of range")
    return issues
