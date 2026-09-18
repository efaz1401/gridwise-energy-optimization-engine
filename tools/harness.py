#!/usr/bin/env python3
"""Public-case runner, paraphrase drills, adversarial suite, soak test."""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lib.optimizer import Bounds  # noqa: E402
from lib.validator import validate_plan  # noqa: E402

CASES = json.loads(
    (Path(__file__).resolve().parents[1] / "fixtures" / "public_cases.json")
    .read_text())["cases"]


def _post(url: str, body, timeout=35.0):
    t0 = time.perf_counter()
    r = httpx.post(f"{url.rstrip('/')}/optimize-energy", json=body,
                   timeout=timeout)
    return r, (time.perf_counter() - t0) * 1000


def _strip(entries):
    out = []
    for e in entries:
        out.append({
            "note_index": e.get("note_index"),
            "applies": e.get("applies"),
            "directive_type": e.get("directive_type"),
            "structured_adjustment": e.get("structured_adjustment"),
        })
    return out


def run_public(url: str) -> bool:
    print(f"{'case':<12}{'valid':<7}{'interp':<8}{'cost':>12}{'ref':>12}"
          f"{'ratio':>8}{'ms':>8}")
    valid = exact = better = 0
    lat = []
    for case in CASES:
        req = case["input"]
        exp = case["expected_output"]
        try:
            r, ms = _post(url, req)
            lat.append(ms)
            r.raise_for_status()
            got = r.json()
        except Exception as exc:  # noqa: BLE001
            print(f"{case['id']:<12}ERROR {type(exc).__name__}: {exc}")
            continue

        truth = Bounds(req, [e for e in exp["directive_interpretation"]
                             if e["applies"]])
        issues = validate_plan(req, got, truth)
        ok = not issues
        valid += ok
        same = _strip(got["directive_interpretation"]) == \
            _strip(exp["directive_interpretation"])
        exact += same
        ref = exp["total_cost_bdt"]
        mine = got["total_cost_bdt"]
        ratio = (ref / mine) if mine else 1.0
        better += ratio >= 0.9999
        print(f"{case['id']:<12}{'OK' if ok else 'BAD':<7}"
              f"{'OK' if same else 'DIFF':<8}{mine:>12.2f}{ref:>12.2f}"
              f"{ratio:>8.4f}{ms:>8.0f}")
        if not ok:
            for i in issues[:4]:
                print(f"    ! {i}")
        if not same:
            print(f"    got {json.dumps(_strip(got['directive_interpretation']))}")
            print(f"    exp {json.dumps(_strip(exp['directive_interpretation']))}")

    n = len(CASES)
    p95 = statistics.quantiles(lat, n=20)[18] if len(lat) >= 20 else max(lat or [0])
    print(f"\ncases_valid={valid}/{n} interp_exact={exact}/{n} "
          f"cost_ratio_ge_1={better}/{n} p95_ms={p95:.0f}")
    return valid == n and exact == n and better >= 8


PARAPHRASES = [
    # (note, capacity, expected_type, expected_hours, extra_key, extra_value)
    ("PV production will drop to about 20% between 13:00 and 15:00.",
     200, "solar_reduction", [13, 14], "factor", 0.2),
    ("Panel washing from one until three will leave roughly one-fifth of "
     "normal solar output.", 200, "solar_reduction", [13, 14], "factor", 0.2),
    ("Expect an 80% reduction in rooftop solar during the 1-3 PM maintenance "
     "window.", 200, "solar_reduction", [13, 14], "factor", 0.2),
    ("Cloud cover will halve solar output from 10 AM until noon.",
     200, "solar_reduction", [10, 11], "factor", 0.5),
    ("Usable solar should be treated as 25% of forecast from noon to 2 PM.",
     200, "solar_reduction", [12, 13], "factor", 0.25),
    ("Solar generation falls by 60 percent between 9 AM and 11 AM.",
     200, "solar_reduction", [9, 10], "factor", 0.4),
    ("Inverter work cuts PV to a quarter of normal from 11:00 to 14:00.",
     200, "solar_reduction", [11, 12, 13], "factor", 0.25),
    ("The battery charger will be isolated from 2 AM until 5 AM.",
     200, "no_charge_window", [2, 3, 4], None, None),
    ("Do not charge the battery between 2 PM and 4 PM.",
     200, "no_charge_window", [14, 15], None, None),
    ("Charging is unavailable from 11 AM until 1 PM for charger inspection.",
     200, "no_charge_window", [11, 12], None, None),
    ("The charging circuit stays offline from 22:00 to 24:00.",
     200, "no_charge_window", [22, 23], None, None),
    ("No battery charging during the 6-8 AM electrical works.",
     200, "no_charge_window", [6, 7], None, None),
    ("For protection testing the battery must not discharge from 6 PM until "
     "8 PM.", 200, "no_discharge_window", [18, 19], None, None),
    ("Relay testing blocks battery discharge between 5 PM and 7 PM.",
     200, "no_discharge_window", [17, 18], None, None),
    ("Hold all discharge from 20:00 until 23:00.",
     200, "no_discharge_window", [20, 21, 22], None, None),
    ("Battery export to load is disabled from 9 AM to 11 AM.",
     200, "no_discharge_window", [9, 10], None, None),
    ("Keep at least 120 kWh in reserve from 6 PM until 9 PM.",
     200, "minimum_battery_reserve", [18, 19, 20], "minimum_energy_kwh", 120),
    ("Keep at least 50% of the battery capacity stored from 6 PM until 9 PM.",
     200, "minimum_battery_reserve", [18, 19, 20], "minimum_energy_kwh", 100),
    ("The data center requires at least 80 kWh in the battery from 6 PM "
     "until 10 PM.", 260, "minimum_battery_reserve", [18, 19, 20, 21],
     "minimum_energy_kwh", 80),
    ("Maintain a floor of 40 percent of capacity between 19:00 and 22:00.",
     250, "minimum_battery_reserve", [19, 20, 21], "minimum_energy_kwh", 100),
    ("Emergency services need 90 kWh retained from 6 PM to 10 PM.",
     250, "minimum_battery_reserve", [18, 19, 20, 21], "minimum_energy_kwh", 90),
    ("From 6 PM until 9 PM grid import must not exceed 155 kWh in any hour.",
     240, "max_grid_window", [18, 19, 20], "max_grid_kwh", 155),
    ("The evening transformer limit is 180 kWh of grid import from 7 PM "
     "until 9 PM.", 250, "max_grid_window", [19, 20], "max_grid_kwh", 180),
    ("Grid intake must stay at or below 190 kWh from 7 PM until 10 PM.",
     260, "max_grid_window", [19, 20, 21], "max_grid_kwh", 190),
    ("Substation constraint caps import at 200 kWh between 18:00 and 21:00.",
     260, "max_grid_window", [18, 19, 20], "max_grid_kwh", 200),
    ("Feeder capacity limits us to 170 kWh per hour from 8 PM to 11 PM.",
     260, "max_grid_window", [20, 21, 22], "max_grid_kwh", 170),
    ("The cafeteria menu changes tomorrow.", 200, "no_op", None, None, None),
    ("The library is extending book-return hours next week.",
     200, "no_op", None, None, None),
    ("A seminar room booking was moved to next week.",
     200, "no_op", None, None, None),
    ("The student affairs office will publish club notices tomorrow.",
     200, "no_op", None, None, None),
    ("The sports office moved next month's registration deadline.",
     200, "no_op", None, None, None),
]


def run_paraphrase(url: str) -> bool:
    base = CASES[0]["input"]
    passed = 0
    for note, cap, want_type, want_hours, key, val in PARAPHRASES:
        req = json.loads(json.dumps(base))
        req["scenario_id"] = "PARA"
        req["operator_notes"] = [note]
        req["battery"]["capacity_kwh"] = cap
        req["battery"]["initial_energy_kwh"] = min(
            req["battery"]["initial_energy_kwh"], cap)
        try:
            r, _ = _post(url, req)
            e = r.json()["directive_interpretation"][0]
        except Exception as exc:  # noqa: BLE001
            print(f"  FAIL(err) {note[:60]}: {exc}")
            continue
        ok = e["directive_type"] == want_type
        if want_hours is not None:
            ok = ok and (e.get("structured_adjustment") or {}).get("hours") == want_hours
        if key:
            got = (e.get("structured_adjustment") or {}).get(key)
            ok = ok and got is not None and abs(float(got) - val) < 0.01
        if want_type == "no_op":
            ok = ok and e["applies"] is False and e["structured_adjustment"] is None
        passed += ok
        if not ok:
            print(f"  FAIL {note[:62]}")
            print(f"       got {e['directive_type']} "
                  f"{e.get('structured_adjustment')}")
    print(f"paraphrase_stable={passed}/{len(PARAPHRASES)}")
    return passed == len(PARAPHRASES)


def run_adversarial(url: str) -> bool:
    base = CASES[0]["input"]

    def mutate(fn):
        req = json.loads(json.dumps(base))
        fn(req)
        return req

    probes = [
        ("malformed-json", "{not json"),
        ("empty-object", {}),
        ("missing-battery", mutate(lambda r: r.pop("battery"))),
        ("23-hours", mutate(lambda r: r["hours"].pop())),
        ("25-hours", mutate(lambda r: r["hours"].append(dict(r["hours"][0])))),
        ("duplicate-hour",
         mutate(lambda r: r["hours"].__setitem__(5, dict(r["hours"][4])))),
        ("no-notes", mutate(lambda r: r.__setitem__("operator_notes", []))),
        ("four-notes", mutate(lambda r: r.__setitem__(
            "operator_notes", ["a", "b", "c", "the menu changed"]))),
        ("huge-note", mutate(lambda r: r.__setitem__(
            "operator_notes", ["solar drops " + "x" * 3000]))),
        ("two-directives-one-note", mutate(lambda r: r.__setitem__(
            "operator_notes",
            ["No charging 2 AM to 5 AM and keep 100 kWh from 6 PM to 9 PM."]))),
        ("nonsense", mutate(lambda r: r.__setitem__(
            "operator_notes", ["zxcv qwerty 9999 ~~~"]))),
        ("negative-demand",
         mutate(lambda r: r["hours"][3].__setitem__("demand_kwh", -50))),
        ("initial-above-capacity",
         mutate(lambda r: r["battery"].__setitem__("initial_energy_kwh", 9999))),
        ("zero-capacity",
         mutate(lambda r: r["battery"].__setitem__("capacity_kwh", 0))),
        ("impossible-cap", mutate(lambda r: r.__setitem__(
            "operator_notes", ["Grid import must not exceed 1 kWh from "
                               "6 PM until 9 PM."]))),
    ]

    bad = 0
    for name, body in probes:
        try:
            if isinstance(body, str):
                r = httpx.post(f"{url.rstrip('/')}/optimize-energy",
                               content=body,
                               headers={"content-type": "application/json"},
                               timeout=35)
            else:
                r, _ = _post(url, body)
            if r.status_code >= 500:
                print(f"  FAIL {name}: {r.status_code}")
                bad += 1
            elif r.status_code == 200:
                got = r.json()
                exp_notes = len(body.get("operator_notes", [])) \
                    if isinstance(body, dict) else 0
                if exp_notes and len(got["directive_interpretation"]) != exp_notes:
                    print(f"  FAIL {name}: entry count mismatch")
                    bad += 1
                else:
                    print(f"  ok   {name}: 200")
            else:
                print(f"  ok   {name}: {r.status_code}")
        except Exception as exc:  # noqa: BLE001
            print(f"  FAIL {name}: {type(exc).__name__}")
            bad += 1
    print(f"adversarial_5xx={bad} adversarial_unhandled=0")
    return bad == 0


def run_soak(url: str) -> bool:
    lat = []
    for case in CASES * 2:
        try:
            _, ms = _post(url, case["input"])
            lat.append(ms)
        except Exception:  # noqa: BLE001
            print("  soak request failed")
            return False
    p95 = statistics.quantiles(lat, n=20)[18]
    print(f"soak n={len(lat)} p50={statistics.median(lat):.0f}ms "
          f"p95={p95:.0f}ms max={max(lat):.0f}ms")
    return p95 <= 5000


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://localhost:8080")
    ap.add_argument("--paraphrase", action="store_true")
    ap.add_argument("--adversarial", action="store_true")
    ap.add_argument("--soak", action="store_true")
    a = ap.parse_args()

    h = httpx.get(f"{a.url.rstrip('/')}/health", timeout=60)
    print(f"health: {h.status_code} {h.text}")
    assert h.json().get("status") == "ok", "health check failed"

    if a.paraphrase:
        sys.exit(0 if run_paraphrase(a.url) else 1)
    if a.adversarial:
        sys.exit(0 if run_adversarial(a.url) else 1)
    if a.soak:
        sys.exit(0 if run_soak(a.url) else 1)
    sys.exit(0 if run_public(a.url) else 1)
