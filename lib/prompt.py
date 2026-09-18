"""Extraction prompt. One call covers every note in the request."""
from __future__ import annotations

import json

SYSTEM = "You convert campus energy operator notes into structured directives. Output JSON only."

TEMPLATE = """You convert campus energy operator notes into structured directives.

SUPPORTED TYPES (no others exist):
  solar_reduction          needs hours[], factor
  minimum_battery_reserve  needs hours[], minimum_energy_kwh
  no_charge_window         needs hours[]
  no_discharge_window      needs hours[]
  max_grid_window          needs hours[], max_grid_kwh
  no_op                    needs nothing

RULES
1. Time windows are START-INCLUSIVE and END-EXCLUSIVE, whole hours only.
   "6 PM until 9 PM"   -> [18,19,20]
   "1 PM to 3 PM"      -> [13,14]
   "11 AM until 1 PM"  -> [11,12]
   "noon until 2 PM"   -> [12,13]
   "13:00 to 15:00"    -> [13,14]
   "5 PM until 7 PM"   -> [17,18]
   "2 AM until 5 AM"   -> [2,3,4]
   "6 PM until 10 PM"  -> [18,19,20,21]
2. factor is the FRACTION THAT REMAINS USABLE, never the fraction lost.
   "80% reduction" -> 0.2      "drops to 25%" -> 0.25
   "about half"    -> 0.5      "one-fifth of normal" -> 0.2
3. A reserve expressed as a percentage is multiplied by capacity_kwh.
   "50% of capacity" with capacity 200 -> minimum_energy_kwh = 100
4. Mapping cues:
   charger / charging circuit isolated or unavailable -> no_charge_window
   relay test / protection test / must not discharge  -> no_discharge_window
   feeder / transformer / substation / import limit / grid intake cap
                                                      -> max_grid_window
   emergency reserve / keep X kWh in the battery      -> minimum_battery_reserve
   cloud cover / panel washing / inverter work / PV drop -> solar_reduction
5. A note that does not change TODAY'S 24-hour electricity schedule is no_op:
   menus, library hours, seminars, registrations, notices, deadlines.
6. Never invent demand, tariff, battery limits, or unsupported directive types.
7. hours must be unique integers 0-23 in ascending order.

BATTERY: {battery}

NOTES:
{notes}

Return ONLY this JSON object:
{{"interpretations":[
  {{"note_index":0,
    "explanation":"state the hour arithmetic and the numeric reasoning here",
    "directive_type":"one of the six types",
    "applies":true,
    "hours":[ints] or null,
    "factor":number or null,
    "minimum_energy_kwh":number or null,
    "max_grid_kwh":number or null}}
]}}
Write "explanation" FIRST for each entry, before deciding the other fields.
Emit exactly one entry per note, in note_index order.
For no_op set applies=false and all value fields to null.
"""


def build_prompt(notes: list[tuple[int, str]], battery: dict) -> str:
    listed = "\n".join(f"[{i}] {t}" for i, t in notes)
    return TEMPLATE.format(battery=json.dumps(battery), notes=listed)


RESPONSE_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "interpretations": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "note_index": {"type": "INTEGER"},
                    "explanation": {"type": "STRING"},
                    "directive_type": {
                        "type": "STRING",
                        "enum": [
                            "solar_reduction", "minimum_battery_reserve",
                            "no_charge_window", "no_discharge_window",
                            "max_grid_window", "no_op",
                        ],
                    },
                    "applies": {"type": "BOOLEAN"},
                    "hours": {"type": "ARRAY", "items": {"type": "INTEGER"},
                              "nullable": True},
                    "factor": {"type": "NUMBER", "nullable": True},
                    "minimum_energy_kwh": {"type": "NUMBER", "nullable": True},
                    "max_grid_kwh": {"type": "NUMBER", "nullable": True},
                },
                "propertyOrdering": [
                    "note_index", "explanation", "directive_type", "applies",
                    "hours", "factor", "minimum_energy_kwh", "max_grid_kwh",
                ],
                "required": ["note_index", "explanation", "directive_type",
                             "applies"],
            },
        }
    },
    "required": ["interpretations"],
}
