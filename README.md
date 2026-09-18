# GridWise — LLM-Assisted Campus Energy Optimization

One HTTP service that reads a 24-hour campus energy scenario plus 1–3
natural-language operator notes, uses an LLM to turn those notes into
structured directives, validates them deterministically, and returns a
cost-minimal 24-hour schedule that satisfies every applicable directive.

## Architecture

    request
      -> Pydantic contract validation
      -> LLM interpretation        (one schema-constrained call, all notes)
      -> deterministic guardrails  (validate, repair, demote-to-no_op)
      -> bounds table              (directives become per-hour limits)
      -> linear program            (SciPy HiGHS, 96 variables)
      -> re-derivation + replay    (recompute solar/grid, forward battery)
      -> self-validation           (independent judge; fallback if it fails)
      -> response

The LLM is the interpretation path. Guardrails only validate and correct its
output; they never replace it. `OFFLINE_FALLBACK=1` is a degraded diagnostic
mode that returns all-`no_op` so the service still answers without credentials.

### LP formulation

Per hour h: `g[h]` grid, `s[h]` solar used, `c[h]` charge, `d[h]` discharge,
all ≥ 0.

    minimize  Σ g[h]·tariff[h] + 1e-6·Σ (c[h] + d[h])
    s.t.      g[h] + s[h] + d[h] = demand[h] + c[h]
              E[h] = initial + Σ_{k≤h}(c[k] − d[k]),  reserve[h] ≤ E[h] ≤ capacity
              E[23] = initial
              s[h] ≤ effective_solar[h],  c[h] ≤ cmax[h],  d[h] ≤ dmax[h],
              g[h] ≤ gmax[h]

The 1e-6 throughput term breaks degenerate optima where an hour would both
charge and discharge — a state the response schema cannot express. It is far
below the 0.01 BDT judging tolerance.

Directives are applied only as bound changes: `solar_reduction` scales
`effective_solar`, `minimum_battery_reserve` raises `reserve`,
`no_charge_window`/`no_discharge_window` zero `cmax`/`dmax`, `max_grid_window`
caps `gmax`.

If the full directive set is infeasible, the solver retries by dropping one
directive at a time, then all of them, then falls back to an idle-battery
plan. Every tier is re-checked by the validator before it can be returned.

## Quickstart (clean machine)

    git clone <REPO_URL> && cd gridwise
    python -m venv .venv && source .venv/bin/activate
    pip install -r requirements.txt
    export GEMINI_API_KEY=...        # or GROQ_API_KEY=...
    uvicorn app.main:app --host 0.0.0.0 --port 8080

    curl -s localhost:8080/health
    # {"status":"ok"}

    curl -s -X POST localhost:8080/optimize-energy \
      -H 'content-type: application/json' \
      -d @<(python -c "import json;print(json.dumps(json.load(open('fixtures/public_cases.json'))['cases'][0]['input']))")

Expected for SAMPLE-01: `directive_interpretation[0]` is
`solar_reduction` with `hours [12,13]`, `factor 0.25`; entry 1 is `no_op`
with `applies:false` and `structured_adjustment:null`; `hourly_plan` has 24
entries ending at `battery_energy_after_kwh = 110`.

Run the full gate:

    python tools/harness.py --url http://localhost:8080
    python tools/harness.py --url http://localhost:8080 --paraphrase
    python tools/harness.py --url http://localhost:8080 --adversarial
    python tools/harness.py --url http://localhost:8080 --soak

## Docker fallback

    docker pull ghcr.io/USERNAME/gridwise:v1
    docker run --rm -p 8080:8080 \
      -e GEMINI_API_KEY=... \
      ghcr.io/USERNAME/gridwise:v1
    curl -s localhost:8080/health

Multi-arch (amd64 + arm64). Binds `0.0.0.0`, exposes `8080`, overridable with
`PORT`. No credentials are baked into any layer. `/health` returns ok with no
environment variables set at all.

## Environment variables (names only)

| Name | Required | Purpose |
|---|---|---|
| `GEMINI_API_KEY` | one of these | primary interpreter |
| `GROQ_API_KEY` | one of these | failover interpreter |
| `GEMINI_MODEL` | no | default `gemini-2.0-flash` |
| `GROQ_MODEL` | no | default `llama-3.3-70b-versatile` |
| `PORT` | no | default 8080 |
| `LLM_TIMEOUT_SECONDS` | no | per-call timeout, default 12 |
| `LLM_BUDGET_SECONDS` | no | total interpretation budget, default 14 |
| `OFFLINE_FALLBACK` | no | `1` forces degraded all-`no_op` mode |
| `LOG_LEVEL` | no | default INFO |

## Model, solver, dependencies

Interpreter: Google Gemini 2.0 Flash via REST with `responseSchema`,
`temperature=0`; failover to Groq Llama 3.3 70B with JSON mode.
Solver: SciPy `linprog` with HiGHS (chosen over PuLP/CBC to avoid a bundled
solver binary that can fail on ARM judging machines).
Dependencies: FastAPI, Uvicorn, Pydantic v2, NumPy, SciPy, httpx. All credited
to their upstream projects; all are open source.

## Known limitations

Windows crossing midnight are supported but untested against hidden cases.
Notes containing two directives yield the single strongest interpretation,
since the schema is one directive per note. Only the five supported directive
types plus `no_op` are ever emitted; anything else is demoted to `no_op`
rather than dropped, preserving one entry per note. Per-note responses are
cached in memory for the process lifetime, so a restart loses the cache.

## Secret handling

No keys, tokens, or `.env` files in the repository or image. Keys are read
from the environment only. Error responses carry no message body beyond a
generic string; stack traces are logged locally and never returned. Prompts
are never logged at INFO level.
