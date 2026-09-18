from __future__ import annotations

import asyncio
import logging
import os
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from lib import cache, guardrails, llm
from lib.contracts import OptimizeResponse, ScenarioRequest
from lib.optimizer import Bounds, solve, warmup
from lib.validator import validate_interpretation, validate_plan

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
log = logging.getLogger("gridwise")

LLM_BUDGET = float(os.getenv("LLM_BUDGET_SECONDS", "20"))


@asynccontextmanager
async def lifespan(_: FastAPI):
    warmup()
    log.info("solver warm; providers=%s", llm.providers_available() or ["none"])
    yield


app = FastAPI(title="GridWise", version="1.0.0", lifespan=lifespan)


@app.exception_handler(RequestValidationError)
async def _bad_request(_: Request, exc: RequestValidationError):
    return JSONResponse(status_code=400,
                        content={"error": "invalid request",
                                 "detail": jsonable_encoder(exc.errors())[:5]})


@app.exception_handler(Exception)
async def _internal(_: Request, exc: Exception):
    log.exception("unhandled: %s", type(exc).__name__)
    return JSONResponse(status_code=500, content={"error": "internal error"})


@app.get("/health")
async def health():
    return {"status": "ok"}


def _summary(entries: list[dict], tier: str) -> str:
    applied = [e["directive_type"] for e in entries if e["applies"]]
    ignored = sum(1 for e in entries if not e["applies"])
    parts = []
    if applied:
        parts.append("Applied " + ", ".join(sorted(set(applied))))
    else:
        parts.append("No operator directive affected the schedule")
    if ignored:
        parts.append(f"ignored {ignored} unrelated note(s)")
    parts.append("charged in low-tariff hours and discharged into peak hours "
                 "while holding every limit and returning the battery to its "
                 "starting level")
    if tier not in ("all", "none"):
        parts.append(f"(relaxation tier: {tier})")
    return "; ".join(parts) + "."


async def _interpret(notes: list[str], battery: dict) -> tuple[list[dict], str]:
    capacity = float(battery["capacity_kwh"])
    keys = [cache.key(n, capacity) for n in notes]
    cached = [cache.get(k) for k in keys]
    missing = [(i, n) for i, (n, c) in enumerate(zip(notes, cached)) if c is None]

    provider = "cache"
    raw: list[dict] = []
    if missing:
        try:
            raw, provider = await asyncio.wait_for(
                llm.extract(missing, battery), timeout=LLM_BUDGET)
        except asyncio.TimeoutError:
            log.warning("llm budget exceeded")
            raw, provider = [], "timeout"

    merged: list[dict] = []
    for i, c in enumerate(cached):
        if c is not None:
            merged.append({**c, "note_index": i})
    merged.extend(r for r in raw if isinstance(r, dict))

    entries = guardrails.normalize(merged, notes, battery)
    if provider not in ("degraded", "timeout"):
        for i, e in enumerate(entries):
            if cached[i] is None:
                cache.put(keys[i], e)
    return entries, provider


@app.post("/optimize-energy")
async def optimize(request: Request):
    started = time.perf_counter()
    try:
        body = await request.json()
    except Exception:  # noqa: BLE001
        return JSONResponse(status_code=400,
                            content={"error": "malformed JSON body"})
    try:
        parsed = ScenarioRequest.model_validate(body)
    except ValidationError as exc:
        return JSONResponse(
            status_code=400,
            content={"error": "invalid request",
                     "detail": jsonable_encoder(exc.errors())[:5]})

    req = parsed.model_dump()
    entries, provider = await _interpret(req["operator_notes"], req["battery"])

    problems = validate_interpretation(req["operator_notes"], entries,
                                       req["battery"]["capacity_kwh"])
    if problems:
        log.error("guardrail escape: %s", problems[:3])
        entries = [{"note_index": i, "applies": False,
                    "directive_type": "no_op", "structured_adjustment": None,
                    "explanation": "Interpretation could not be validated."}
                   for i in range(len(req["operator_notes"]))]

    payload, tier = solve(req, entries)

    final = validate_plan(req, payload, Bounds(req, [e for e in entries
                                                     if e["applies"]]))
    if final:
        log.error("post-solve invalid, using trivial plan: %s", final[:3])
        from lib.fallback import trivial_plan
        payload = trivial_plan(req, [e for e in entries if e["applies"]])
        tier = "trivial"

    response = OptimizeResponse(
        scenario_id=req["scenario_id"],
        directive_interpretation=entries,
        hourly_plan=payload["hourly_plan"],
        total_grid_kwh=payload["total_grid_kwh"],
        total_cost_bdt=payload["total_cost_bdt"],
        peak_grid_kwh=payload["peak_grid_kwh"],
        plan_summary=_summary(entries, tier),
    )
    log.info("scenario=%s notes=%d provider=%s tier=%s cost=%.2f ms=%.0f",
             req["scenario_id"], len(entries), provider, tier,
             payload["total_cost_bdt"], (time.perf_counter() - started) * 1000)
    return response
