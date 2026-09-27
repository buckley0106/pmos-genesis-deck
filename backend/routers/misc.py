"""Misc router — governance, rarity, economic sim, charts, docs, root."""
from datetime import datetime, timezone
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException

from deps import (
    build_docs, db, get_current_user, log_system_event, new_id, now_iso, require_admin,
)
from engines import ENGINE_ORDER, RARITY_WEIGHTS
from models import EconomicSimInput, ProposalCreate, RarityInput, VoteCreate

router = APIRouter(prefix="/api", tags=["misc"])


# --- Governance -------------------------------------------------------------
@router.get("/governance/proposals")
async def list_proposals():
    docs = await db.proposals.find({}, {"_id": 0}).sort("created_at", -1).to_list(100)
    for p in docs:
        votes = await db.votes.find({"proposal_id": p["id"]}, {"_id": 0}).to_list(1000)
        p["tally"] = {
            "yes": sum(1 for v in votes if v["choice"] == "yes"),
            "no": sum(1 for v in votes if v["choice"] == "no"),
            "abstain": sum(1 for v in votes if v["choice"] == "abstain"),
            "total": len(votes),
        }
    return docs


@router.post("/governance/proposals")
async def create_proposal(body: ProposalCreate, user: Dict[str, Any] = Depends(get_current_user)):
    doc = {
        "id": new_id(), "title": body.title, "description": body.description,
        "target_asset_id": body.target_asset_id, "proposal_type": body.proposal_type,
        "created_by": user["email"], "created_at": now_iso(), "status": "open",
    }
    await db.proposals.insert_one(doc)
    doc.pop("_id", None)
    await log_system_event("proposal_created", f"{user['email']} created proposal: {body.title}", related_id=doc["id"])
    return doc


@router.post("/governance/vote")
async def cast_vote(body: VoteCreate, user: Dict[str, Any] = Depends(get_current_user)):
    if body.choice not in ("yes", "no", "abstain"):
        raise HTTPException(status_code=400, detail="Invalid choice")
    if not await db.proposals.find_one({"id": body.proposal_id}):
        raise HTTPException(status_code=404, detail="Proposal not found")
    existing = await db.votes.find_one({"proposal_id": body.proposal_id, "voter_email": user["email"]})
    if existing:
        await db.votes.update_one(
            {"_id": existing["_id"]}, {"$set": {"choice": body.choice, "updated_at": now_iso()}},
        )
    else:
        await db.votes.insert_one({
            "id": new_id(), "proposal_id": body.proposal_id, "voter_email": user["email"],
            "choice": body.choice, "cast_at": now_iso(),
        })
    await log_system_event("vote_cast", f"{user['email']} voted {body.choice}", related_id=body.proposal_id)
    return {"ok": True}


@router.get("/governance/amendments")
async def list_amendments():
    return await db.constitution_amendments.find({}, {"_id": 0}).sort("created_at", -1).to_list(100)


@router.post("/governance/amendments")
async def add_amendment(body: ProposalCreate, user: Dict[str, Any] = Depends(require_admin)):
    doc = {
        "id": new_id(), "title": body.title, "body": body.description, "created_by": user["email"],
        "created_at": now_iso(), "version": int(datetime.now(timezone.utc).timestamp()),
    }
    await db.constitution_amendments.insert_one(doc)
    doc.pop("_id", None)
    await log_system_event("amendment_added", f"Constitution amended: {body.title}", related_id=doc["id"])
    return doc


# --- Rarity / Economic / Charts --------------------------------------------
@router.post("/rarity/calculate")
async def calc_rarity(body: RarityInput):
    score = (
        body.legendary_traits * RARITY_WEIGHTS["legendary"]
        + body.rare_traits * RARITY_WEIGHTS["rare"]
        + body.uncommon_traits * RARITY_WEIGHTS["uncommon"]
        + body.common_traits * RARITY_WEIGHTS["common"]
    )
    if body.canon_status:
        score = int(score * 1.5)
    if score >= 250:
        tier = "mythic"
    elif score >= 150:
        tier = "legendary"
    elif score >= 80:
        tier = "rare"
    elif score >= 40:
        tier = "uncommon"
    else:
        tier = "common"
    return {"score": score, "tier": tier, "formula": "Σ(traits × weight) × (1.5 if canon)", "weights": RARITY_WEIGHTS}


@router.post("/economic/simulate")
async def economic_sim(body: EconomicSimInput):
    rows, supply, price = [], body.initial_supply, body.mint_cost
    for m in range(0, body.horizon_months + 1):
        rows.append({"month": m, "supply": round(supply, 2), "price_usd": round(price, 6), "market_cap": round(supply * price, 2)})
        price = price * (1 + 0.04 * body.demand_factor)
        supply = supply * (1 - body.burn_rate)
    return {"rows": rows, "inputs": body.model_dump()}


@router.get("/charts/rarity-distribution")
async def chart_rarity():
    docs = await db.meme_assets.find({}, {"_id": 0, "rarity": 1}).to_list(500)
    counts = {"common": 0, "uncommon": 0, "rare": 0, "legendary": 0, "mythic": 0}
    for d in docs:
        t = (d.get("rarity") or {}).get("tier", "common")
        counts[t] = counts.get(t, 0) + 1
    return [{"tier": k, "count": v} for k, v in counts.items()]


@router.get("/charts/faction-breakdown")
async def chart_factions():
    docs = await db.meme_assets.find({}, {"_id": 0, "engines.Faction.name": 1}).to_list(500)
    tally: Dict[str, int] = {}
    for d in docs:
        name = (((d.get("engines") or {}).get("Faction") or {}).get("name")) or "Unknown"
        tally[name] = tally.get(name, 0) + 1
    return [{"faction": k, "count": v} for k, v in tally.items()]


@router.get("/charts/economic-curve")
async def chart_econ():
    docs = await db.meme_assets.find({}, {"_id": 0, "engines.ChartEngine.economic_curve": 1}).sort("created_at", -1).limit(1).to_list(1)
    if not docs:
        return []
    return (((docs[0].get("engines") or {}).get("ChartEngine") or {}).get("economic_curve")) or []


# --- Docs -------------------------------------------------------------------
@router.get("/docs/all")
async def docs_all():
    amendments = await db.constitution_amendments.find({}, {"_id": 0}).sort("created_at", -1).to_list(50)
    return {**build_docs(ENGINE_ORDER), "amendments": amendments}


# --- Root -------------------------------------------------------------------
@router.get("/")
async def root():
    return {
        "name": "PMOS • WMEU API",
        "version": "2.0.0",
        "engine_count": len(ENGINE_ORDER),
        "engines": ENGINE_ORDER,
        "copyright": "© 2026 Patrick Buckley",
        "edition": "Universe-Class",
    }
