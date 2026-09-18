"""24-hour LP over HiGHS, plus directive->bounds translation."""
from __future__ import annotations

import logging
import math
from typing import Any

import numpy as np
from scipy.optimize import linprog

log = logging.getLogger("gridwise.optimizer")

EPS = 1e-6          # anti-degeneracy weight on battery throughput
BIG = 1e7           # stand-in for an unbounded grid draw
H = 24


class Bounds:
    """Per-hour limits after every applicable directive is applied."""

    def __init__(self, req: dict, directives: list[dict]):
        b = req["battery"]
        hrs = sorted(req["hours"], key=lambda e: e["hour"])
        self.demand = [float(e["demand_kwh"]) for e in hrs]
        self.tariff = [float(e["tariff_bdt_per_kwh"]) for e in hrs]
        self.base_solar = [float(e["solar_kwh"]) for e in hrs]
        self.capacity = float(b["capacity_kwh"])
        self.initial = float(b["initial_energy_kwh"])
        self.base_min = float(b["minimum_energy_kwh"])
        self.cmax_base = float(b["max_charge_kwh_per_hour"])
        self.dmax_base = float(b["max_discharge_kwh_per_hour"])

        self.eff_solar = list(self.base_solar)
        self.reserve = [self.base_min] * H
        self.cmax = [self.cmax_base] * H
        self.dmax = [self.dmax_base] * H
        self.gmax = [BIG] * H

        for d in directives:
            if not d.get("applies"):
                continue
            adj = d.get("structured_adjustment") or {}
            hours = [h for h in adj.get("hours", []) if 0 <= h <= 23]
            t = d.get("directive_type")
            if t == "solar_reduction":
                f = float(adj["factor"])
                for h in hours:
                    self.eff_solar[h] = min(self.eff_solar[h],
                                            self.base_solar[h] * f)
            elif t == "minimum_battery_reserve":
                v = float(adj["minimum_energy_kwh"])
                for h in hours:
                    self.reserve[h] = max(self.reserve[h], v)
            elif t == "no_charge_window":
                for h in hours:
                    self.cmax[h] = 0.0
            elif t == "no_discharge_window":
                for h in hours:
                    self.dmax[h] = 0.0
            elif t == "max_grid_window":
                v = float(adj["max_grid_kwh"])
                for h in hours:
                    self.gmax[h] = min(self.gmax[h], v)


def _solve_lp(bd: Bounds) -> list[tuple[float, float]] | None:
    """Return per-hour (charge, discharge) or None if infeasible."""
    n = 4 * H
    gi, si, ci, di = 0, H, 2 * H, 3 * H

    cost = np.zeros(n)
    for h in range(H):
        cost[gi + h] = bd.tariff[h]
        cost[ci + h] = EPS
        cost[di + h] = EPS

    # equality: balance per hour, plus end-of-day neutrality
    a_eq = np.zeros((H + 1, n))
    b_eq = np.zeros(H + 1)
    for h in range(H):
        a_eq[h, gi + h] = 1.0
        a_eq[h, si + h] = 1.0
        a_eq[h, di + h] = 1.0
        a_eq[h, ci + h] = -1.0
        b_eq[h] = bd.demand[h]
    for h in range(H):
        a_eq[H, ci + h] = 1.0
        a_eq[H, di + h] = -1.0
    b_eq[H] = 0.0

    # inequality: running state of charge inside [reserve, capacity]
    a_ub = np.zeros((2 * H, n))
    b_ub = np.zeros(2 * H)
    for h in range(H):
        for k in range(h + 1):
            a_ub[h, ci + k] = 1.0
            a_ub[h, di + k] = -1.0
            a_ub[H + h, ci + k] = -1.0
            a_ub[H + h, di + k] = 1.0
        b_ub[h] = bd.capacity - bd.initial
        b_ub[H + h] = bd.initial - bd.reserve[h]

    bounds = (
        [(0.0, None if bd.gmax[h] >= BIG else bd.gmax[h]) for h in range(H)]
        + [(0.0, bd.eff_solar[h]) for h in range(H)]
        + [(0.0, bd.cmax[h]) for h in range(H)]
        + [(0.0, bd.dmax[h]) for h in range(H)]
    )

    res = linprog(cost, A_ub=a_ub, b_ub=b_ub, A_eq=a_eq, b_eq=b_eq,
                  bounds=bounds, method="highs")
    if not res.success or res.x is None:
        return None
    x = res.x
    return [(float(x[ci + h]), float(x[di + h])) for h in range(H)]


def _materialize(bd: Bounds,
                 flows: list[tuple[float, float]]) -> dict[str, Any]:
    """Round, net, re-derive solar and grid, forward-replay the battery."""
    net = []
    for c, d in flows:
        v = round(c - d, 6)
        net.append(0.0 if abs(v) < 1e-9 else v)

    residual = round(sum(net), 6)
    if residual != 0.0:
        net = _absorb(bd, net, residual)

    plan, energy = [], bd.initial
    for h in range(H):
        n = net[h]
        charge = max(n, 0.0)
        discharge = max(-n, 0.0)
        need = bd.demand[h] + charge - discharge
        if need < 0:
            need = 0.0
        solar = min(bd.eff_solar[h], need)
        grid = max(need - solar, 0.0)
        energy = round(energy + n, 6)
        if h == H - 1:
            energy = bd.initial
        action = "charge" if charge > 0 else ("discharge" if discharge > 0
                                              else "idle")
        plan.append({
            "hour": h,
            "grid_kwh": round(grid, 6),
            "solar_used_kwh": round(solar, 6),
            "battery_action": action,
            "battery_kwh": round(charge if charge > 0 else discharge, 6),
            "battery_energy_after_kwh": round(energy, 6),
        })

    total_grid = round(sum(p["grid_kwh"] for p in plan), 6)
    total_cost = round(sum(p["grid_kwh"] * bd.tariff[p["hour"]]
                           for p in plan), 6)
    peak = round(max(p["grid_kwh"] for p in plan), 6)
    return {"hourly_plan": plan, "total_grid_kwh": total_grid,
            "total_cost_bdt": total_cost, "peak_grid_kwh": peak}


def _absorb(bd: Bounds, net: list[float], residual: float) -> list[float]:
    """Push a tiny rounding residual into one hour that has slack."""
    if abs(residual) > 1e-3:
        log.warning("large neutrality residual %.6f", residual)
    for h in range(H - 1, -1, -1):
        target = net[h] - residual
        if -bd.dmax[h] - 1e-9 <= target <= bd.cmax[h] + 1e-9:
            trial = list(net)
            trial[h] = round(target, 6)
            energy, ok = bd.initial, True
            for k in range(H):
                energy += trial[k]
                if energy < bd.reserve[k] - 1e-6 or energy > bd.capacity + 1e-6:
                    ok = False
                    break
            if ok:
                return trial
    return net


def solve(req: dict, directives: list[dict]) -> tuple[dict[str, Any], str]:
    """Return (plan_payload, tier). Never raises."""
    applied = [d for d in directives if d.get("applies")]

    attempts: list[tuple[str, list[dict]]] = [("all", applied)]
    for i in range(len(applied)):
        attempts.append((f"drop:{applied[i]['directive_type']}",
                         applied[:i] + applied[i + 1:]))
    attempts.append(("none", []))

    for tier, subset in attempts:
        try:
            bd = Bounds(req, subset)
            flows = _solve_lp(bd)
            if flows is None:
                continue
            payload = _materialize(bd, flows)
            from .validator import validate_plan
            truth = Bounds(req, applied)
            issues = validate_plan(req, payload, truth)
            if not issues:
                return payload, tier
            log.warning("tier %s rejected by self-validation: %s",
                        tier, issues[:3])
        except Exception as exc:  # noqa: BLE001
            log.warning("tier %s raised %s", tier, type(exc).__name__)

    from .fallback import trivial_plan
    return trivial_plan(req, applied), "trivial"


def warmup() -> None:
    """Touch HiGHS once at startup so the first real request is not the one
    that pays import and JIT cost."""
    req = {
        "hours": [{"hour": h, "demand_kwh": 100.0, "solar_kwh": 10.0,
                   "tariff_bdt_per_kwh": 5.0 + h % 7} for h in range(H)],
        "battery": {"capacity_kwh": 200.0, "initial_energy_kwh": 100.0,
                    "minimum_energy_kwh": 20.0,
                    "max_charge_kwh_per_hour": 50.0,
                    "max_discharge_kwh_per_hour": 50.0},
    }
    try:
        solve(req, [])
    except Exception:  # noqa: BLE001
        log.warning("warmup failed", exc_info=False)


def finite(x: float) -> bool:
    return isinstance(x, (int, float)) and math.isfinite(x)
