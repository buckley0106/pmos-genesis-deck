"""PMOS • WMEU — Meme Civilization Engine backend.

15-engine pipeline + governance + canon vault + debug tools.
Copyright (c) 2026 Patrick Buckley. All rights reserved.
"""
from dotenv import load_dotenv
from pathlib import Path

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

import os
import hashlib
import logging
import secrets
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

import bcrypt
import jwt
from bson import ObjectId
from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request, status
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, EmailStr, Field
from starlette.middleware.cors import CORSMiddleware

# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("pmos")

mongo_url = os.environ["MONGO_URL"]
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ["DB_NAME"]]

JWT_SECRET = os.environ["JWT_SECRET"]
JWT_ALG = "HS256"

app = FastAPI(title="PMOS • WMEU API", version="1.0.0")
api = APIRouter(prefix="/api")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id() -> str:
    return str(uuid.uuid4())


def seed_hash(seed: str, salt: str = "") -> int:
    h = hashlib.sha256(f"{seed}::{salt}".encode("utf-8")).hexdigest()
    return int(h[:12], 16)


def pick(seed: str, salt: str, options: List[Any]) -> Any:
    return options[seed_hash(seed, salt) % len(options)]


def pick_float(seed: str, salt: str, lo: float, hi: float, decimals: int = 4) -> float:
    span = hi - lo
    val = lo + (seed_hash(seed, salt) % 10_000) / 10_000.0 * span
    return round(val, decimals)


def pick_int(seed: str, salt: str, lo: int, hi: int) -> int:
    return lo + (seed_hash(seed, salt) % max(1, hi - lo + 1))


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------
def hash_password(pw: str) -> str:
    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()


def verify_password(pw: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(pw.encode(), hashed.encode())
    except Exception:
        return False


def create_access_token(user_id: str, email: str, role: str) -> str:
    payload = {
        "sub": user_id,
        "email": email,
        "role": role,
        "exp": datetime.now(timezone.utc) + timedelta(days=7),
        "type": "access",
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALG)


async def get_current_user(request: Request) -> Dict[str, Any]:
    token = None
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        token = auth[7:]
    if not token:
        token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])
        user = await db.users.find_one({"_id": ObjectId(payload["sub"])})
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        user["id"] = str(user["_id"])
        user.pop("_id", None)
        user.pop("password_hash", None)
        return user
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


async def require_admin(user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    return user


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------
class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6)
    name: Optional[str] = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RunPMOSRequest(BaseModel):
    seed: str = Field(min_length=1, max_length=200)
    enrich_ai: bool = False
    auto_approve: bool = False


class DebugPMOSRequest(BaseModel):
    engine: Optional[str] = None  # if None, debug all
    seed: str = "DEBUG-SEED"


class EngineStatusUpdate(BaseModel):
    engine_name: str
    status: str
    last_error: Optional[str] = None
    engine_version: str = "1.0.0"


class SystemEventCreate(BaseModel):
    type: str
    summary: str
    related_id: Optional[str] = None
    details: Optional[Dict[str, Any]] = None


class ProposalCreate(BaseModel):
    title: str
    description: str
    target_asset_id: Optional[str] = None
    proposal_type: str = "canon_approval"  # canon_approval, constitution_amendment, parameter_change


class VoteCreate(BaseModel):
    proposal_id: str
    choice: str  # yes / no / abstain


class RarityInput(BaseModel):
    trait_count: int = 8
    legendary_traits: int = 1
    rare_traits: int = 2
    uncommon_traits: int = 3
    common_traits: int = 2
    canon_status: bool = False


class EconomicSimInput(BaseModel):
    initial_supply: float = 1_000_000.0
    mint_cost: float = 0.01
    demand_factor: float = 1.5
    burn_rate: float = 0.02
    horizon_months: int = 12


# ---------------------------------------------------------------------------
# Workflow primitives: updateEngineStatus + logSystemEvent
# ---------------------------------------------------------------------------
async def update_engine_status(
    engine_name: str, status_value: str, last_error: Optional[str] = None, engine_version: str = "1.0.0"
) -> Dict[str, Any]:
    doc = {
        "engine_name": engine_name,
        "status": status_value,
        "last_run": now_iso(),
        "last_error": last_error,
        "engine_version": engine_version,
    }
    await db.engine_status.update_one({"engine_name": engine_name}, {"$set": doc}, upsert=True)
    return doc


async def log_system_event(
    event_type: str, summary: str, related_id: Optional[str] = None, details: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    doc = {
        "event_id": new_id(),
        "timestamp": now_iso(),
        "type": event_type,
        "summary": summary,
        "related_id": related_id,
        "details": details or {},
    }
    await db.system_events.insert_one(doc)
    doc.pop("_id", None)
    return doc


# ---------------------------------------------------------------------------
# 15-engine pipeline (deterministic seeded)
# ---------------------------------------------------------------------------
ENGINE_ORDER = [
    "Blueprint",
    "Biological",
    "Energy",
    "Artifact",
    "Species",
    "Plant",
    "Faction",
    "Lore",
    "MemeBinding",
    "MemeCoinBinder",
    "NFTMint",
    "Economic",
    "Governance",
    "CanonVaultConnector",
    "ChartEngine",
]

ENGINE_VERSION = "1.0.0"


def engine_blueprint(seed: str, ctx: Dict[str, Any]) -> Dict[str, Any]:
    archetype = pick(seed, "bp.archetype", ["Cosmic Wanderer", "Glyph Forger", "Void Saint", "Neon Prophet", "Quantum Jester", "Astral Trickster"])
    geometry = pick(seed, "bp.geo", ["dodecahedral", "fractal-spiral", "möbius", "tesseract", "klein-bottle"])
    return {
        "engine": "Blueprint",
        "archetype": archetype,
        "geometry": geometry,
        "dimensional_layer": pick_int(seed, "bp.dim", 3, 11),
        "schema_version": "blueprint/1.0",
    }


def engine_biological(seed: str, ctx: Dict[str, Any]) -> Dict[str, Any]:
    bases = ["A", "T", "G", "C"]
    dna = "".join(pick(seed, f"bio.dna.{i}", bases) for i in range(16))
    return {
        "engine": "Biological",
        "dna_signature": dna,
        "mutation_rate": pick_float(seed, "bio.mut", 0.001, 0.25, 5),
        "lifespan_eons": pick_int(seed, "bio.life", 1, 9999),
        "consciousness_index": pick_float(seed, "bio.ci", 0.0, 1.0),
    }


def engine_energy(seed: str, ctx: Dict[str, Any]) -> Dict[str, Any]:
    signature = pick(seed, "en.sig", ["plasma", "anti-matter", "dark-flux", "photon-storm", "void-current", "hyperionic"])
    return {
        "engine": "Energy",
        "signature": signature,
        "output_terawatts": pick_float(seed, "en.tw", 0.1, 9999.9, 2),
        "frequency_hz": pick_int(seed, "en.hz", 1, 1_000_000),
        "stability": pick_float(seed, "en.stab", 0.0, 1.0),
    }


def engine_artifact(seed: str, ctx: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "engine": "Artifact",
        "name": pick(seed, "art.name", ["Glyph of Recursion", "Mask of the Pepe", "Doge Compass", "Wojak Locket", "Chad Sigil", "Wabi Crown"]),
        "material": pick(seed, "art.mat", ["void-steel", "meme-crystal", "ether-glass", "neon-bone"]),
        "power_rating": pick_int(seed, "art.pwr", 1, 100),
    }


def engine_species(seed: str, ctx: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "engine": "Species",
        "name": pick(seed, "sp.name", ["Pepeling", "Wojakaur", "Dogir", "Chadnoid", "Wabithian", "Bonkari"]),
        "kingdom": pick(seed, "sp.king", ["Memeota", "Glyphota", "Voidanimalia", "Hyperia"]),
        "population_est": pick_int(seed, "sp.pop", 100, 10_000_000),
    }


def engine_plant(seed: str, ctx: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "engine": "Plant",
        "name": pick(seed, "pl.name", ["Glyphvine", "Memebloom", "Voidshroom", "Pepetree", "Wojakberry", "Coinroot"]),
        "habitat": pick(seed, "pl.hab", ["nebula-floor", "crater-rim", "data-stream", "void-cliff"]),
        "psychoactive": bool(seed_hash(seed, "pl.psy") % 2),
    }


def engine_faction(seed: str, ctx: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "engine": "Faction",
        "name": pick(seed, "fc.name", ["Order of P.BUCK", "Waboot Collective", "Glyph Wardens", "Neon Hyperborea", "Cult of the Coin"]),
        "alignment": pick(seed, "fc.al", ["lawful-meme", "chaotic-meme", "neutral-glyph", "ascended"]),
        "influence": pick_int(seed, "fc.inf", 1, 100),
    }


def engine_lore(seed: str, ctx: Dict[str, Any]) -> Dict[str, Any]:
    archetype = ctx.get("Blueprint", {}).get("archetype", "Entity")
    species = ctx.get("Species", {}).get("name", "Unknown")
    faction = ctx.get("Faction", {}).get("name", "Unbound")
    snippet = (
        f"In the {pick(seed, 'lore.era', ['First', 'Second', 'Tenth', 'Final'])} Cycle of the WMEU, "
        f"a {archetype} of the {species} rose under the banner of {faction}, "
        f"channeling {ctx.get('Energy', {}).get('signature', 'unknown')} energy through the "
        f"{ctx.get('Artifact', {}).get('name', 'Relic')}."
    )
    return {
        "engine": "Lore",
        "summary": snippet,
        "tags": [pick(seed, "lore.t1", ["origin", "rebirth", "ascension"]), pick(seed, "lore.t2", ["myth", "prophecy", "saga"])],
    }


def engine_meme_binding(seed: str, ctx: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "engine": "MemeBinding",
        "binding_id": hashlib.sha1(seed.encode()).hexdigest()[:16].upper(),
        "resonance": pick_float(seed, "mb.res", 0.0, 1.0, 3),
        "bind_strength": pick_int(seed, "mb.str", 1, 100),
    }


def engine_meme_coin_binder(seed: str, ctx: Dict[str, Any]) -> Dict[str, Any]:
    species = ctx.get("Species", {}).get("name", "MEME")
    ticker = "$" + "".join(c for c in species.upper() if c.isalpha())[:5]
    return {
        "engine": "MemeCoinBinder",
        "ticker": ticker,
        "decimals": 9,
        "max_supply": pick_int(seed, "mcb.sup", 100_000, 1_000_000_000),
        "chain_adapter": "simulated-evm",
    }


def engine_nft_mint(seed: str, ctx: Dict[str, Any]) -> Dict[str, Any]:
    token_id = pick_int(seed, "nft.id", 1, 999_999_999)
    chain_hash = "0x" + hashlib.sha256(f"mint::{seed}".encode()).hexdigest()
    return {
        "engine": "NFTMint",
        "token_id": token_id,
        "chain_hash": chain_hash,
        "chain_adapter": "simulated-evm",
        "metadata_uri": f"wmeu://meta/{token_id}",
        "is_simulated": True,
    }


def engine_economic(seed: str, ctx: Dict[str, Any]) -> Dict[str, Any]:
    supply = ctx.get("MemeCoinBinder", {}).get("max_supply", 1_000_000)
    return {
        "engine": "Economic",
        "initial_price_usd": pick_float(seed, "econ.p", 0.0001, 0.5, 6),
        "circulating_supply": int(supply * pick_float(seed, "econ.circ", 0.05, 0.4, 3)),
        "market_cap_usd_est": round(supply * pick_float(seed, "econ.p", 0.0001, 0.5, 6) * 0.2, 2),
        "burn_rate_pct": pick_float(seed, "econ.burn", 0.0, 5.0, 2),
    }


def engine_governance(seed: str, ctx: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "engine": "Governance",
        "voting_power": pick_int(seed, "gov.vp", 1, 1000),
        "quorum_pct": pick_int(seed, "gov.q", 10, 75),
        "proposal_window_days": pick_int(seed, "gov.w", 1, 14),
    }


def engine_canon_vault_connector(seed: str, ctx: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "engine": "CanonVaultConnector",
        "vault_namespace": "wmeu.canon.v1",
        "intake_status": "pending_approval",
        "submission_hash": hashlib.sha256(seed.encode()).hexdigest()[:32],
    }


def engine_chart_engine(seed: str, ctx: Dict[str, Any]) -> Dict[str, Any]:
    rarity_buckets = [
        {"tier": "common", "count": pick_int(seed, "ch.c", 1, 20)},
        {"tier": "uncommon", "count": pick_int(seed, "ch.u", 1, 15)},
        {"tier": "rare", "count": pick_int(seed, "ch.r", 1, 10)},
        {"tier": "legendary", "count": pick_int(seed, "ch.l", 0, 5)},
    ]
    economic_curve = [
        {"month": m, "supply": ctx.get("Economic", {}).get("circulating_supply", 100_000) * (1 + 0.02 * m)}
        for m in range(0, 13)
    ]
    return {
        "engine": "ChartEngine",
        "rarity_distribution": rarity_buckets,
        "economic_curve": economic_curve,
    }


ENGINE_FUNCS = {
    "Blueprint": engine_blueprint,
    "Biological": engine_biological,
    "Energy": engine_energy,
    "Artifact": engine_artifact,
    "Species": engine_species,
    "Plant": engine_plant,
    "Faction": engine_faction,
    "Lore": engine_lore,
    "MemeBinding": engine_meme_binding,
    "MemeCoinBinder": engine_meme_coin_binder,
    "NFTMint": engine_nft_mint,
    "Economic": engine_economic,
    "Governance": engine_governance,
    "CanonVaultConnector": engine_canon_vault_connector,
    "ChartEngine": engine_chart_engine,
}


async def run_single_engine(name: str, seed: str, ctx: Dict[str, Any]) -> Dict[str, Any]:
    """Runs one engine, logs status + events. Returns the output dict."""
    if name not in ENGINE_FUNCS:
        raise ValueError(f"Unknown engine: {name}")
    await update_engine_status(name, "running", engine_version=ENGINE_VERSION)
    try:
        output = ENGINE_FUNCS[name](seed, ctx)
        if not isinstance(output, dict) or output.get("engine") != name:
            raise ValueError("Invalid engine output: missing 'engine' key or not dict")
        await update_engine_status(name, "success", engine_version=ENGINE_VERSION)
        await log_system_event("engine_run", f"{name} completed", details={"engine": name})
        return output
    except Exception as exc:
        await update_engine_status(name, "error", last_error=str(exc), engine_version=ENGINE_VERSION)
        await log_system_event("engine_error", f"{name} failed: {exc}", details={"engine": name, "error": str(exc)})
        raise


# ---------------------------------------------------------------------------
# Rarity formula
# ---------------------------------------------------------------------------
RARITY_WEIGHTS = {"legendary": 50, "rare": 20, "uncommon": 8, "common": 2}


def compute_rarity(asset: Dict[str, Any]) -> Dict[str, Any]:
    """Rarity = sum(trait weights) + canon bonus."""
    engines = asset.get("engines", {})
    # Use ChartEngine bucket counts to score
    buckets = engines.get("ChartEngine", {}).get("rarity_distribution", [])
    score = 0
    breakdown = {}
    for b in buckets:
        w = RARITY_WEIGHTS.get(b.get("tier"), 1)
        sub = w * int(b.get("count", 0))
        score += sub
        breakdown[b["tier"]] = sub
    if asset.get("canon_approved"):
        score = int(score * 1.5)
        breakdown["canon_bonus_x1.5"] = True
    tier = "common"
    if score >= 600:
        tier = "mythic"
    elif score >= 350:
        tier = "legendary"
    elif score >= 180:
        tier = "rare"
    elif score >= 80:
        tier = "uncommon"
    return {"score": score, "tier": tier, "breakdown": breakdown}


# ---------------------------------------------------------------------------
# Auth endpoints
# ---------------------------------------------------------------------------
@api.post("/auth/register")
async def register(body: RegisterRequest):
    email = body.email.lower()
    if await db.users.find_one({"email": email}):
        raise HTTPException(status_code=400, detail="Email already registered")
    doc = {
        "email": email,
        "name": body.name or email.split("@")[0],
        "password_hash": hash_password(body.password),
        "role": "member",
        "created_at": now_iso(),
    }
    res = await db.users.insert_one(doc)
    uid = str(res.inserted_id)
    token = create_access_token(uid, email, "member")
    return {"token": token, "user": {"id": uid, "email": email, "name": doc["name"], "role": "member"}}


@api.post("/auth/login")
async def login(body: LoginRequest):
    email = body.email.lower()
    user = await db.users.find_one({"email": email})
    if not user or not verify_password(body.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    uid = str(user["_id"])
    token = create_access_token(uid, email, user.get("role", "member"))
    return {
        "token": token,
        "user": {"id": uid, "email": email, "name": user.get("name"), "role": user.get("role", "member")},
    }


@api.get("/auth/me")
async def me(user: Dict[str, Any] = Depends(get_current_user)):
    return user


# ---------------------------------------------------------------------------
# PMOS endpoints
# ---------------------------------------------------------------------------
@api.post("/pmos/run")
async def run_pmos(body: RunPMOSRequest):
    """runPMOS: runs all 15 engines, binds outputs into a MemeAsset, returns full JSON."""
    started = now_iso()
    ctx: Dict[str, Any] = {}
    errors: List[Dict[str, Any]] = []
    for name in ENGINE_ORDER:
        try:
            ctx[name] = await run_single_engine(name, body.seed, ctx)
        except Exception as exc:
            errors.append({"engine": name, "error": str(exc)})
            break

    asset_id = new_id()
    rarity = compute_rarity({"engines": ctx, "canon_approved": False})
    asset = {
        "id": asset_id,
        "seed": body.seed,
        "created_at": started,
        "completed_at": now_iso(),
        "engines": ctx,
        "errors": errors,
        "rarity": rarity,
        "canon_approved": False,
        "enrich_ai": body.enrich_ai,
    }
    await db.meme_assets.insert_one({**asset, "_doc_kind": "MemeAsset"})

    # Blueprint table copy
    if "Blueprint" in ctx:
        await db.blueprints.insert_one({"asset_id": asset_id, "blueprint": ctx["Blueprint"], "created_at": started})

    if body.auto_approve:
        await _approve_canon(asset_id)
        asset["canon_approved"] = True

    await log_system_event(
        "engine_run",
        f"runPMOS completed for seed={body.seed[:24]}",
        related_id=asset_id,
        details={"errors": errors, "rarity": rarity},
    )
    return asset


@api.post("/pmos/debug")
async def debug_pmos(body: DebugPMOSRequest):
    """debugPMOS: tests one or all engines, validates JSON, logs errors."""
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


@api.post("/pmos/engine-status/update")
async def api_update_engine_status(body: EngineStatusUpdate):
    return await update_engine_status(body.engine_name, body.status, body.last_error, body.engine_version)


@api.get("/pmos/engine-status")
async def list_engine_status():
    docs = await db.engine_status.find({}, {"_id": 0}).to_list(100)
    by_name = {d["engine_name"]: d for d in docs}
    # ensure every engine present
    out = []
    for name in ENGINE_ORDER:
        out.append(by_name.get(name, {"engine_name": name, "status": "idle", "last_run": None, "last_error": None, "engine_version": ENGINE_VERSION}))
    return out


@api.post("/pmos/system-events")
async def api_log_system_event(body: SystemEventCreate):
    return await log_system_event(body.type, body.summary, body.related_id, body.details)


@api.get("/pmos/system-events")
async def list_system_events(limit: int = 100):
    docs = await db.system_events.find({}, {"_id": 0}).sort("timestamp", -1).to_list(limit)
    return docs


@api.get("/pmos/engine-order")
async def engine_order():
    return {"order": ENGINE_ORDER, "version": ENGINE_VERSION}


# ---------------------------------------------------------------------------
# Meme assets
# ---------------------------------------------------------------------------
@api.get("/meme-assets")
async def list_meme_assets(limit: int = 50):
    docs = await db.meme_assets.find({}, {"_id": 0}).sort("created_at", -1).to_list(limit)
    return docs


@api.get("/meme-assets/{asset_id}")
async def get_meme_asset(asset_id: str):
    doc = await db.meme_assets.find_one({"id": asset_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Asset not found")
    return doc


async def _approve_canon(asset_id: str) -> Dict[str, Any]:
    asset = await db.meme_assets.find_one({"id": asset_id}, {"_id": 0})
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    # Recompute rarity with canon bonus
    asset["canon_approved"] = True
    asset["rarity"] = compute_rarity(asset)
    await db.meme_assets.update_one({"id": asset_id}, {"$set": {"canon_approved": True, "rarity": asset["rarity"]}})
    # Vault entry
    vault_entry = {
        "id": new_id(),
        "asset_id": asset_id,
        "seed": asset.get("seed"),
        "rarity": asset["rarity"],
        "added_at": now_iso(),
        "namespace": "wmeu.canon.v1",
    }
    await db.canon_vault.insert_one(vault_entry)
    # Certificate
    cert = {
        "id": new_id(),
        "asset_id": asset_id,
        "issued_at": now_iso(),
        "issuer": "PMOS Canon Authority",
        "owner": "Patrick Buckley © 2026",
        "hash": hashlib.sha256(f"cert::{asset_id}".encode()).hexdigest(),
    }
    await db.canon_certificates.insert_one(cert)
    await log_system_event("canon_approved", f"Asset {asset_id[:8]} entered canon", related_id=asset_id)
    return {"vault_entry": {**vault_entry}, "certificate": {**cert}}


@api.post("/meme-assets/{asset_id}/approve")
async def approve_asset(asset_id: str, user: Dict[str, Any] = Depends(require_admin)):
    result = await _approve_canon(asset_id)
    # strip _id if present
    for k in ("vault_entry", "certificate"):
        result[k].pop("_id", None)
    return result


# ---------------------------------------------------------------------------
# Canon Vault
# ---------------------------------------------------------------------------
@api.get("/canon-vault")
async def list_canon_vault(limit: int = 50):
    docs = await db.canon_vault.find({}, {"_id": 0}).sort("added_at", -1).to_list(limit)
    return docs


@api.get("/canon-vault/{asset_id}/certificate")
async def get_certificate(asset_id: str):
    doc = await db.canon_certificates.find_one({"asset_id": asset_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="No certificate")
    return doc


# ---------------------------------------------------------------------------
# Governance
# ---------------------------------------------------------------------------
@api.get("/governance/proposals")
async def list_proposals():
    docs = await db.proposals.find({}, {"_id": 0}).sort("created_at", -1).to_list(100)
    # attach vote tallies
    for p in docs:
        votes = await db.votes.find({"proposal_id": p["id"]}, {"_id": 0}).to_list(1000)
        p["tally"] = {
            "yes": sum(1 for v in votes if v["choice"] == "yes"),
            "no": sum(1 for v in votes if v["choice"] == "no"),
            "abstain": sum(1 for v in votes if v["choice"] == "abstain"),
            "total": len(votes),
        }
    return docs


@api.post("/governance/proposals")
async def create_proposal(body: ProposalCreate, user: Dict[str, Any] = Depends(get_current_user)):
    doc = {
        "id": new_id(),
        "title": body.title,
        "description": body.description,
        "target_asset_id": body.target_asset_id,
        "proposal_type": body.proposal_type,
        "created_by": user["email"],
        "created_at": now_iso(),
        "status": "open",
    }
    await db.proposals.insert_one(doc)
    await log_system_event("proposal_created", f"{user['email']} created proposal: {body.title}", related_id=doc["id"])
    doc.pop("_id", None)
    return doc


@api.post("/governance/vote")
async def cast_vote(body: VoteCreate, user: Dict[str, Any] = Depends(get_current_user)):
    if body.choice not in ("yes", "no", "abstain"):
        raise HTTPException(status_code=400, detail="Invalid choice")
    prop = await db.proposals.find_one({"id": body.proposal_id})
    if not prop:
        raise HTTPException(status_code=404, detail="Proposal not found")
    # one vote per user
    existing = await db.votes.find_one({"proposal_id": body.proposal_id, "voter_email": user["email"]})
    if existing:
        await db.votes.update_one(
            {"_id": existing["_id"]}, {"$set": {"choice": body.choice, "updated_at": now_iso()}}
        )
    else:
        await db.votes.insert_one(
            {
                "id": new_id(),
                "proposal_id": body.proposal_id,
                "voter_email": user["email"],
                "choice": body.choice,
                "cast_at": now_iso(),
            }
        )
    await log_system_event("vote_cast", f"{user['email']} voted {body.choice}", related_id=body.proposal_id)
    return {"ok": True}


@api.get("/governance/amendments")
async def list_amendments():
    docs = await db.constitution_amendments.find({}, {"_id": 0}).sort("created_at", -1).to_list(100)
    return docs


@api.post("/governance/amendments")
async def add_amendment(body: ProposalCreate, user: Dict[str, Any] = Depends(require_admin)):
    doc = {
        "id": new_id(),
        "title": body.title,
        "body": body.description,
        "created_by": user["email"],
        "created_at": now_iso(),
        "version": int(datetime.now(timezone.utc).timestamp()),
    }
    await db.constitution_amendments.insert_one(doc)
    await log_system_event("amendment_added", f"Constitution amended: {body.title}", related_id=doc["id"])
    doc.pop("_id", None)
    return doc


# ---------------------------------------------------------------------------
# Rarity + Economic + Charts
# ---------------------------------------------------------------------------
@api.post("/rarity/calculate")
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
    return {
        "score": score,
        "tier": tier,
        "formula": "Σ(traits × weight) × (1.5 if canon)",
        "weights": RARITY_WEIGHTS,
    }


@api.post("/economic/simulate")
async def economic_sim(body: EconomicSimInput):
    rows = []
    supply = body.initial_supply
    price = body.mint_cost
    for m in range(0, body.horizon_months + 1):
        rows.append({
            "month": m,
            "supply": round(supply, 2),
            "price_usd": round(price, 6),
            "market_cap": round(supply * price, 2),
        })
        # apply demand + burn
        price = price * (1 + 0.04 * body.demand_factor)
        supply = supply * (1 - body.burn_rate)
    return {"rows": rows, "inputs": body.model_dump()}


@api.get("/charts/rarity-distribution")
async def chart_rarity():
    docs = await db.meme_assets.find({}, {"_id": 0, "rarity": 1}).to_list(500)
    counts = {"common": 0, "uncommon": 0, "rare": 0, "legendary": 0, "mythic": 0}
    for d in docs:
        t = (d.get("rarity") or {}).get("tier", "common")
        counts[t] = counts.get(t, 0) + 1
    return [{"tier": k, "count": v} for k, v in counts.items()]


@api.get("/charts/faction-breakdown")
async def chart_factions():
    docs = await db.meme_assets.find({}, {"_id": 0, "engines.Faction.name": 1}).to_list(500)
    tally: Dict[str, int] = {}
    for d in docs:
        name = (((d.get("engines") or {}).get("Faction") or {}).get("name")) or "Unknown"
        tally[name] = tally.get(name, 0) + 1
    return [{"faction": k, "count": v} for k, v in tally.items()]


@api.get("/charts/economic-curve")
async def chart_econ():
    docs = await db.meme_assets.find({}, {"_id": 0, "engines.ChartEngine.economic_curve": 1}).sort("created_at", -1).limit(1).to_list(1)
    if not docs:
        return []
    return (((docs[0].get("engines") or {}).get("ChartEngine") or {}).get("economic_curve")) or []


# ---------------------------------------------------------------------------
# Docs & constitution (read-only static)
# ---------------------------------------------------------------------------
DOCS = {
    "constitution": {
        "title": "WMEU Constitution v1.0",
        "body": (
            "Article I — The PMOS pipeline shall consist of fifteen (15) ordered engines.\n"
            "Article II — All Meme Assets generated by PMOS belong to the seed-submitter, "
            "subject to the canon process and the rights reserved by Patrick Buckley © 2026.\n"
            "Article III — Canon admission requires governance approval or admin fiat.\n"
            "Article IV — The Constitution may be amended by a qualified governance vote "
            "or by direct issuance by the sole administrator while in single-admin mode.\n"
            "Article V — All sub-brands (P.BUCK, PMOS, WMEU, Waboot Meme Engine Universe) "
            "are trademarks of Patrick Buckley, to be assigned to Buckley Labs LLC upon registration."
        ),
    },
    "rarity_formula": {
        "title": "Rarity Formula",
        "body": "score = Σ(trait_count × tier_weight); tier_weight = {legendary:50, rare:20, uncommon:8, common:2}; ×1.5 if canon.",
    },
    "engine_order": {"title": "Engine Order", "body": " → ".join(ENGINE_ORDER)},
    "canon_process": {
        "title": "Canon Process",
        "body": (
            "1. Run PMOS with a seed.\n"
            "2. Review the resulting Meme Asset.\n"
            "3. Open a governance proposal (type=canon_approval) OR admin auto-approves.\n"
            "4. Upon approval, a CanonVault entry and CanonCertificate are issued.\n"
            "5. Rarity is recomputed with the canon ×1.5 bonus."
        ),
    },
    "debug_checklist": {
        "title": "Debug Checklist",
        "body": (
            "• Every engine must emit JSON with an 'engine' key matching its name.\n"
            "• run debugPMOS without engine name to test all 15.\n"
            "• Check EngineStatus and SystemEvent tables after each run.\n"
            "• Errors must update EngineStatus.last_error and emit an engine_error event."
        ),
    },
    "amendment_log": {"title": "Amendment Log", "body": "See /api/governance/amendments"},
    "legal": {
        "copyright": (
            "Copyright © 2026 Patrick Buckley. All rights reserved.\n"
            "PMOS • WMEU — Meme Civilization Engine and all derivative works, source code, "
            "engine outputs, lore, branding marks (P.BUCK, PMOS, WMEU, Waboot Meme Engine Universe), "
            "and Meme Assets generated by this system are the intellectual property of Patrick Buckley."
        ),
        "trademark": (
            "TRADEMARK NOTICE\n"
            "The marks “P.BUCK”, “PMOS”, “P.BUCK Meme Operating System”, “WMEU”, "
            "“Waboot Meme Engine Universe”, and “PMOS • WMEU — Meme Civilization Engine” "
            "are trademarks of Patrick Buckley (2026). Buckley Labs LLC designation is reserved "
            "and will replace personal attribution upon formal entity registration. "
            "Unauthorized use of these marks in connection with competing systems is prohibited."
        ),
        "license": (
            "PROPRIETARY LICENSE — PMOS • WMEU v1.0\n"
            "This software and its outputs are the proprietary work of Patrick Buckley (the “Owner”). "
            "Permission is hereby granted to authorized operators to use the hosted system for the "
            "stated purposes of meme civilization generation, governance, and canon curation. "
            "Redistribution, decompilation, reverse-engineering, or commercial fork without prior "
            "written consent of the Owner is strictly prohibited. The Owner reserves all rights "
            "not expressly granted herein. Generated Meme Assets are licensed to their seed-submitters "
            "for personal and promotional use, subject to the canon process and trademark notice."
        ),
        "to_whom_it_may_concern": (
            "TO WHOM IT MAY CONCERN\n\n"
            "Be it known that Patrick Buckley is the sole creator, owner, and rights-holder of the "
            "PMOS • WMEU — Meme Civilization Engine, including its 15-engine pipeline architecture, "
            "the runPMOS / debugPMOS / updateEngineStatus / logSystemEvent workflows, the Canon Vault "
            "and governance protocols, and all associated branding (P.BUCK, PMOS, WMEU, Waboot Meme "
            "Engine Universe). This document serves as formal notice of authorship and ownership as "
            "of 2026. All rights are reserved pending the formation of Buckley Labs LLC, at which "
            "point ownership will be assigned to said entity per a separate instrument.\n\n"
            "Signed,\nPatrick Buckley\nFounder, PMOS • WMEU\n2026"
        ),
        "universal_hub_clause": (
            "UNIVERSAL HUB CLAUSE\n"
            "PMOS • WMEU is designated by its Owner as the canonical universal hub for the "
            "addition, registration, and testing of memes within the P.BUCK / Waboot ecosystem. "
            "Third-party meme integrations are welcomed under the canon process. The Owner retains "
            "final authority over hub admission and may suspend or revoke entries that conflict with "
            "the Constitution or trademark protections."
        ),
    },
}


@api.get("/docs/all")
async def docs_all():
    amendments = await db.constitution_amendments.find({}, {"_id": 0}).sort("created_at", -1).to_list(50)
    return {**DOCS, "amendments": amendments}


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------
@api.get("/")
async def root():
    return {
        "name": "PMOS • WMEU API",
        "version": "1.0.0",
        "engines": ENGINE_ORDER,
        "copyright": "© 2026 Patrick Buckley",
    }


# ---------------------------------------------------------------------------
# Startup
# ---------------------------------------------------------------------------
@app.on_event("startup")
async def on_startup():
    # indexes
    try:
        await db.users.create_index("email", unique=True)
        await db.meme_assets.create_index("id", unique=True)
        await db.canon_vault.create_index("asset_id")
        await db.proposals.create_index("id", unique=True)
        await db.votes.create_index([("proposal_id", 1), ("voter_email", 1)], unique=True)
        await db.engine_status.create_index("engine_name", unique=True)
    except Exception as exc:
        logger.warning(f"index init: {exc}")

    # admin seed (idempotent)
    admin_email = os.environ["ADMIN_EMAIL"].lower()
    admin_pw = os.environ["ADMIN_PASSWORD"]
    existing = await db.users.find_one({"email": admin_email})
    if not existing:
        await db.users.insert_one(
            {
                "email": admin_email,
                "name": "Patrick Buckley",
                "password_hash": hash_password(admin_pw),
                "role": "admin",
                "created_at": now_iso(),
            }
        )
        logger.info("Seeded admin user")
    elif not verify_password(admin_pw, existing["password_hash"]):
        await db.users.update_one({"email": admin_email}, {"$set": {"password_hash": hash_password(admin_pw)}})
        logger.info("Updated admin password")

    # seed engine status idle entries
    for name in ENGINE_ORDER:
        await db.engine_status.update_one(
            {"engine_name": name},
            {"$setOnInsert": {"status": "idle", "last_run": None, "last_error": None, "engine_version": ENGINE_VERSION}},
            upsert=True,
        )


@app.on_event("shutdown")
async def on_shutdown():
    client.close()


app.include_router(api)
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)
