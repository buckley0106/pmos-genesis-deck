"""PMOS router — run, run/stream, debug, engine-status, system-events, engine-order."""
from __future__ import annotations

import asyncio
import json
from typing import Any, AsyncGenerator, Dict, List

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from deps import (
    ENGINE_VERSION, db, log_system_event, now_iso, update_engine_status,
)
from engines import ENGINE_FUNCS, ENGINE_ORDER, approve_canon, persist_meme_asset, run_single_engine
from models import DebugPMOSRequest, EngineStatusUpdate, RunPMOSRequest, SystemEventCreate

router = APIRouter(prefix="/api/pmos", tags=["pmos"])


@router.get("/engine-order")
async def engine_order():
    return {"order": ENGINE_ORDER, "version": ENGINE_VERSION, "count": len(ENGINE_ORDER)}


@router.post("/run")
async def run_pmos(body: RunPMOSRequest):
    ctx: Dict[str, Any] = {}
    errors: List[Dict[str, Any]] = []
    for name in ENGINE_ORDER:
        try:
            ctx[name] = await run_single_engine(name, body.seed, ctx)
        except Exception as exc:
            errors.append({"engine": name, "error": str(exc)})
            break
    asset = await persist_meme_asset(body.seed, ctx, errors)
    if body.auto_approve:
        await approve_canon(asset["id"])
        refreshed = await db.meme_assets.find_one({"id": asset["id"]}, {"_id": 0})
        if refreshed:
            asset = refreshed
    await log_system_event(
        "engine_run", f"runPMOS completed for seed={body.seed[:24]}",
        related_id=asset["id"], details={"errors": errors, "rarity": asset["rarity"]},
    )
    return asset


def _sse(event: str, data: Any) -> bytes:
    return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n".encode()


@router.get("/run/stream")
async def run_pmos_stream(seed: str, enrich_ai: bool = False):
    if not seed:
        raise HTTPException(status_code=400, detail="seed required")

    async def gen() -> AsyncGenerator[bytes, None]:
        ctx: Dict[str, Any] = {}
        errors: List[Dict[str, Any]] = []
        yield _sse("start", {"seed": seed, "total": len(ENGINE_ORDER)})
        for i, name in enumerate(ENGINE_ORDER):
            yield _sse("engine_start", {"engine": name, "index": i})
            await asyncio.sleep(0.04)
            try:
                out = await run_single_engine(name, seed, ctx)
                ctx[name] = out
                yield _sse("engine_done", {"engine": name, "index": i, "output_keys": list(out.keys())})
            except Exception as exc:
                errors.append({"engine": name, "error": str(exc)})
                yield _sse("engine_error", {"engine": name, "error": str(exc)})
                break
        asset = await persist_meme_asset(seed, ctx, errors)
        await log_system_event("engine_run", f"runPMOS (sse) completed for seed={seed[:24]}", related_id=asset["id"])
        yield _sse("complete", asset)

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/debug")
async def debug_pmos(body: DebugPMOSRequest):
    report: List[Dict[str, Any]] = []
    targets = [body.engine] if body.engine else ENGINE_ORDER
    ctx: Dict[str, Any] = {}
    for name in targets:
        if name not in ENGINE_FUNCS:
            report.append({"engine": name, "ok": False, "error": "unknown engine"})
            continue
        try:
            out = await run_single_engine(name, body.seed, ctx)
            ctx[name] = out
            report.append({"engine": name, "ok": True, "output_keys": list(out.keys())})
        except Exception as exc:
            report.append({"engine": name, "ok": False, "error": str(exc)})
    await log_system_event("debug_run", f"debugPMOS completed ({len(report)} engines)", details={"report": report})
    return {"report": report, "tested_at": now_iso()}


@router.post("/engine-status/update")
async def api_update_engine_status(body: EngineStatusUpdate):
    return await update_engine_status(body.engine_name, body.status, body.last_error, body.engine_version)


@router.get("/engine-status")
async def list_engine_status():
    docs = await db.engine_status.find({}, {"_id": 0}).to_list(200)
    by_name = {d["engine_name"]: d for d in docs}
    out = []
    for name in ENGINE_ORDER:
        out.append(by_name.get(name, {"engine_name": name, "status": "idle", "last_run": None, "last_error": None, "engine_version": ENGINE_VERSION}))
    return out


@router.post("/system-events")
async def api_log_system_event(body: SystemEventCreate):
    return await log_system_event(body.type, body.summary, body.related_id, body.details)


@router.get("/system-events")
async def list_system_events(limit: int = 100):
    docs = await db.system_events.find({}, {"_id": 0}).sort("timestamp", -1).to_list(limit)
    return docs
