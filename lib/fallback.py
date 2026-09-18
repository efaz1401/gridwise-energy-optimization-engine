"""Always-feasible plan of last resort: never cycle the battery."""
from __future__ import annotations

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
