#!/usr/bin/env python3
"""Run custom scenario or custom operator notes through GridWise."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
CASES = json.loads((ROOT / "fixtures" / "public_cases.json").read_text(encoding="utf-8"))["cases"]


def run_custom(
    notes: list[str],
    url: str = "http://localhost:8000",
    capacity: float = 200.0,
    initial: float = 100.0,
    min_reserve: float = 20.0,
    max_charge: float = 50.0,
    max_discharge: float = 50.0,
    base_case_index: int = 0,
):
    req = json.loads(json.dumps(CASES[base_case_index]["input"]))
    req["scenario_id"] = "CUSTOM-TEST"
    req["operator_notes"] = notes
    req["battery"] = {
        "capacity_kwh": capacity,
        "initial_energy_kwh": initial,
        "minimum_energy_kwh": min_reserve,
        "max_charge_kwh_per_hour": max_charge,
        "max_discharge_kwh_per_hour": max_discharge,
    }

    print(f"\n--- Sending Custom Scenario to {url}/optimize-energy ---")
    print(f"Notes ({len(notes)}):")
    for i, n in enumerate(notes):
        print(f"  [{i}] {n}")
    print(f"Battery: {req['battery']}\n")

    try:
        r = httpx.post(f"{url.rstrip('/')}/optimize-energy", json=req, timeout=30.0)
        r.raise_for_status()
        res = r.json()
    except Exception as exc:
        print(f"Error calling API: {exc}")
        if hasattr(exc, "response") and exc.response is not None:
            print(f"Response ({exc.response.status_code}): {exc.response.text}")
        sys.exit(1)

    print("=== DIRECTIVE INTERPRETATION ===")
    for d in res["directive_interpretation"]:
        applies = "APPLIES" if d["applies"] else "IGNORED (no_op)"
        print(f"[{d['note_index']}] {d['directive_type']} ({applies})")
        if d.get("structured_adjustment"):
            print(f"    Adjustment: {d['structured_adjustment']}")
        print(f"    Explanation: {d['explanation']}")

    print("\n=== OPTIMIZATION SUMMARY ===")
    print(f"Plan Summary: {res['plan_summary']}")
    print(f"Total Cost:   {res['total_cost_bdt']:.2f} BDT")
    print(f"Total Grid:   {res['total_grid_kwh']:.2f} kWh")
    print(f"Peak Grid:    {res['peak_grid_kwh']:.2f} kWh")

    # Replay Neutrality
    e0 = req["battery"]["initial_energy_kwh"]
    e23 = res["hourly_plan"][23]["battery_energy_after_kwh"]
    print(f"Neutrality:   Start={e0} kWh -> End={e23} kWh (Delta = {abs(e23 - e0):.4f} kWh)")

    print("\nHourly Sample (Hours 12-21):")
    print(f"{'Hour':<6}{'Demand':>8}{'Solar':>8}{'Action':>12}{'Battery':>10}{'SoC':>8}{'Grid':>8}")
    for h in range(12, 22):
        p = res["hourly_plan"][h]
        d = req["hours"][h]["demand_kwh"]
        print(f"{h:02d}:00 {d:>8.1f}{p['solar_used_kwh']:>8.1f}{p['battery_action']:>12}{p['battery_kwh']:>10.1f}{p['battery_energy_after_kwh']:>8.1f}{p['grid_kwh']:>8.1f}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test custom operator notes against GridWise")
    parser.add_argument("--url", default="http://localhost:8000", help="GridWise API base URL")
    parser.add_argument("--note", action="append", help="Operator note string (can specify multiple)")
    parser.add_argument("--cap", type=float, default=200.0, help="Battery capacity (kWh)")
    parser.add_argument("--init", type=float, default=100.0, help="Battery initial energy (kWh)")
    parser.add_argument("--min", type=float, default=20.0, help="Battery min reserve (kWh)")
    args = parser.parse_args()

    notes = args.note or [
        "Inverter work cuts PV to a quarter of normal from 11:00 to 14:00.",
        "Keep at least 50% of the battery capacity stored from 6 PM until 9 PM.",
        "The sports office moved next month's registration deadline.",
    ]

    run_custom(
        notes=notes,
        url=args.url,
        capacity=args.cap,
        initial=args.init,
        min_reserve=args.min,
    )
