"""PMOS • WMEU v2.0 — Meme Civilization Engine (Universe-Class Edition).

26-engine PMOS pipeline + canon storage + OG images + public canon pages +
SSE live ticks + webhooks + marketplace + identity registry + governance.

© 2026 Patrick Buckley — All rights reserved.
P.BUCK™ · PMOS™ · WMEU™ · Waboot Meme Engine Universe™
"""
from dotenv import load_dotenv
from pathlib import Path

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

import asyncio
import hashlib
import json
import logging
import os
import re
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, AsyncGenerator, Dict, List, Optional

import bcrypt
import jwt
from bson import ObjectId
from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, StreamingResponse
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, EmailStr, Field
from starlette.middleware.cors import CORSMiddleware

from canon_storage import init_storage, save_canon_snapshot, save_og_image, get_object
from og_image import render_og
from chain_adapter import simulate_mint, store_chain_hash
import webhook as wh

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
PUBLIC_BASE_URL = os.environ.get("PUBLIC_BASE_URL", "")

app = FastAPI(title="PMOS • WMEU API", version="2.0.0")
api = APIRouter(prefix="/api")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id() -> str:
    return str(uuid.uuid4())


def seed_hash(seed: str, salt: str = "") -> int:
    h = hashlib.sha256(f"{seed}::{salt}".encode()).hexdigest()
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
        "sub": user_id, "email": email, "role": role,
        "exp": datetime.now(timezone.utc) + timedelta(days=7), "type": "access",
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
    engine: Optional[str] = None
    seed: str = "DEBUG-SEED"


class EngineStatusUpdate(BaseModel):
    engine_name: str
    status: str
    last_error: Optional[str] = None
    engine_version: str = "2.0.0"


class SystemEventCreate(BaseModel):
    type: str
    summary: str
    related_id: Optional[str] = None
    details: Optional[Dict[str, Any]] = None


class ProposalCreate(BaseModel):
    title: str
    description: str
    target_asset_id: Optional[str] = None
    proposal_type: str = "canon_approval"


class VoteCreate(BaseModel):
    proposal_id: str
    choice: str


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


class MarketplaceListingCreate(BaseModel):
    asset_id: str
    price_usd: float
    description: Optional[str] = None


class WebhookConfigCreate(BaseModel):
    url: str = Field(min_length=8)
    label: str = "default"
    event_types: List[str] = Field(default_factory=lambda: ["engine_error", "canon_approved"])


# ---------------------------------------------------------------------------
# Workflow primitives
# ---------------------------------------------------------------------------
async def update_engine_status(engine_name, status_value, last_error=None, engine_version="2.0.0"):
    doc = {
        "engine_name": engine_name, "status": status_value, "last_run": now_iso(),
        "last_error": last_error, "engine_version": engine_version,
    }
    await db.engine_status.update_one({"engine_name": engine_name}, {"$set": doc}, upsert=True)
    return doc


async def _fire_webhooks(event_type: str, summary: str, related_id: Optional[str], details: Dict[str, Any]):
    configs = await db.webhook_configs.find({"event_types": event_type}).to_list(50)
    for c in configs:
        wh.dispatch(c["url"], {"type": event_type, "summary": summary, "related_id": related_id, "details": details})


async def log_system_event(event_type, summary, related_id=None, details=None):
    doc = {
        "event_id": new_id(), "timestamp": now_iso(), "type": event_type, "summary": summary,
        "related_id": related_id, "details": details or {},
    }
    await db.system_events.insert_one(doc)
    doc.pop("_id", None)
    # fire webhooks for selected event types (engine_error, canon_approved by default)
    if event_type in ("engine_error", "canon_approved", "engine_run"):
        try:
            await _fire_webhooks(event_type, summary, related_id, details or {})
        except Exception as exc:
            logger.debug(f"webhook dispatch error: {exc}")
    return doc


# ---------------------------------------------------------------------------
# 26-engine PMOS v2.0 pipeline
# ---------------------------------------------------------------------------
ENGINE_VERSION = "2.0.0"

# --- Original 8 ---
def engine_blueprint(seed, ctx):
    return {
        "engine": "Blueprint",
        "archetype": pick(seed, "bp.archetype", ["Cosmic Wanderer", "Glyph Forger", "Void Saint", "Neon Prophet", "Quantum Jester", "Astral Trickster"]),
        "geometry": pick(seed, "bp.geo", ["dodecahedral", "fractal-spiral", "möbius", "tesseract", "klein-bottle"]),
        "dimensional_layer": pick_int(seed, "bp.dim", 3, 11),
        "schema_version": "blueprint/2.0",
    }


def engine_biological(seed, ctx):
    dna = "".join(pick(seed, f"bio.dna.{i}", ["A", "T", "G", "C"]) for i in range(16))
    return {
        "engine": "Biological", "dna_signature": dna,
        "mutation_rate": pick_float(seed, "bio.mut", 0.001, 0.25, 5),
        "lifespan_eons": pick_int(seed, "bio.life", 1, 9999),
        "consciousness_index": pick_float(seed, "bio.ci", 0.0, 1.0),
    }


def engine_energy(seed, ctx):
    return {
        "engine": "Energy",
        "signature": pick(seed, "en.sig", ["plasma", "anti-matter", "dark-flux", "photon-storm", "void-current", "hyperionic"]),
        "output_terawatts": pick_float(seed, "en.tw", 0.1, 9999.9, 2),
        "frequency_hz": pick_int(seed, "en.hz", 1, 1_000_000),
        "stability": pick_float(seed, "en.stab", 0.0, 1.0),
    }


def engine_artifact(seed, ctx):
    return {
        "engine": "Artifact",
        "name": pick(seed, "art.name", ["Glyph of Recursion", "Mask of the Pepe", "Doge Compass", "Wojak Locket", "Chad Sigil", "Wabi Crown"]),
        "material": pick(seed, "art.mat", ["void-steel", "meme-crystal", "ether-glass", "neon-bone"]),
        "power_rating": pick_int(seed, "art.pwr", 1, 100),
    }


def engine_species(seed, ctx):
    return {
        "engine": "Species",
        "name": pick(seed, "sp.name", ["Pepeling", "Wojakaur", "Dogir", "Chadnoid", "Wabithian", "Bonkari"]),
        "kingdom": pick(seed, "sp.king", ["Memeota", "Glyphota", "Voidanimalia", "Hyperia"]),
        "population_est": pick_int(seed, "sp.pop", 100, 10_000_000),
    }


def engine_plant(seed, ctx):
    return {
        "engine": "Plant",
        "name": pick(seed, "pl.name", ["Glyphvine", "Memebloom", "Voidshroom", "Pepetree", "Wojakberry", "Coinroot"]),
        "habitat": pick(seed, "pl.hab", ["nebula-floor", "crater-rim", "data-stream", "void-cliff"]),
        "psychoactive": bool(seed_hash(seed, "pl.psy") % 2),
    }


def engine_faction(seed, ctx):
    return {
        "engine": "Faction",
        "name": pick(seed, "fc.name", ["Order of P.BUCK", "Waboot Collective", "Glyph Wardens", "Neon Hyperborea", "Cult of the Coin"]),
        "alignment": pick(seed, "fc.al", ["lawful-meme", "chaotic-meme", "neutral-glyph", "ascended"]),
        "influence": pick_int(seed, "fc.inf", 1, 100),
    }


def engine_lore(seed, ctx):
    archetype = ctx.get("Blueprint", {}).get("archetype", "Entity")
    species = ctx.get("Species", {}).get("name", "Unknown")
    faction = ctx.get("Faction", {}).get("name", "Unbound")
    snippet = (
        f"In the {pick(seed, 'lore.era', ['First', 'Second', 'Tenth', 'Final'])} Cycle of the WMEU, "
        f"a {archetype} of the {species} rose under the banner of {faction}, channeling "
        f"{ctx.get('Energy', {}).get('signature', 'unknown')} energy through the "
        f"{ctx.get('Artifact', {}).get('name', 'Relic')}."
    )
    return {"engine": "Lore", "summary": snippet, "tags": [pick(seed, "lore.t1", ["origin", "rebirth", "ascension"]), pick(seed, "lore.t2", ["myth", "prophecy", "saga"])]}


# --- New v2.0 engines (9-15) ---
def engine_identity(seed, ctx):
    species = ctx.get("Species", {}).get("name", "Entity")
    faction = ctx.get("Faction", {}).get("name", "Unbound")
    return {
        "engine": "Identity",
        "true_name": f"{species}-{hashlib.sha1(seed.encode()).hexdigest()[:6].upper()}",
        "epithet": pick(seed, "id.ep", ["the Unwritten", "the Coiled", "the Echoing", "the First-Bound", "the Untethered"]),
        "house": faction,
        "soul_index": pick_float(seed, "id.soul", 0.0, 1.0, 4),
    }


def engine_continuity(seed, ctx):
    return {
        "engine": "Continuity",
        "parent_seed_hash": hashlib.sha256(f"parent::{seed}".encode()).hexdigest()[:24],
        "generation": pick_int(seed, "cont.gen", 1, 9999),
        "lineage_branch": pick(seed, "cont.br", ["primary", "schism", "hidden", "ancient"]),
        "is_genesis": seed_hash(seed, "cont.gen") % 17 == 0,
    }


def engine_influence(seed, ctx):
    base = ctx.get("Faction", {}).get("influence", 50)
    pop = ctx.get("Species", {}).get("population_est", 1000)
    score = min(1000, base * 8 + int(pop / 10_000))
    return {
        "engine": "Influence",
        "influence_score": score,
        "reach_class": "global" if score > 600 else "regional" if score > 250 else "local",
        "vector": pick(seed, "inf.v", ["cultural", "economic", "esoteric", "memetic", "martial"]),
    }


def engine_social_graph(seed, ctx):
    nodes = pick_int(seed, "sg.n", 3, 18)
    edges = [
        {"from": i, "to": (i + 1 + seed_hash(seed, f"sg.e.{i}") % max(1, nodes - 1)) % nodes,
         "weight": pick_float(seed, f"sg.w.{i}", 0.1, 1.0, 3)}
        for i in range(nodes)
    ]
    return {"engine": "SocialGraph", "nodes": nodes, "edges": edges, "density": round(len(edges) / max(1, nodes * (nodes - 1)), 4)}


def engine_universe_time(seed, ctx):
    cycle = pick_int(seed, "ut.cy", 1, 1_000_000)
    return {
        "engine": "UniverseTime",
        "wmeu_epoch": cycle,
        "era": pick(seed, "ut.era", ["First Ignition", "Glyph Bloom", "Coin Schism", "Void Quiet", "Final Saga"]),
        "iso_canonical": now_iso(),
        "is_solstice": cycle % 365 in (79, 172, 265, 355),
    }


SAFETY_BLOCKLIST = ("kill", "csam", "exploit-violence")


def engine_safety(seed, ctx):
    text = (seed + " " + ctx.get("Lore", {}).get("summary", "")).lower()
    flagged = [w for w in SAFETY_BLOCKLIST if w in text]
    return {
        "engine": "Safety",
        "safe": len(flagged) == 0,
        "flags": flagged,
        "policy_version": "wmeu.safety.v1",
    }


def engine_rate_limit(seed, ctx):
    bucket = hashlib.sha1(seed.encode()).hexdigest()[:6]
    return {
        "engine": "RateLimit",
        "bucket": bucket,
        "tokens_remaining": pick_int(seed, "rl.tok", 1, 999),
        "reset_in_sec": pick_int(seed, "rl.reset", 5, 3600),
        "policy": "anon:30/min admin:unlimited",
    }


# --- Existing 16-19 + 21-22 + 25 (renumbered) ---
def engine_meme_binding(seed, ctx):
    return {
        "engine": "MemeBinding",
        "binding_id": hashlib.sha1(seed.encode()).hexdigest()[:16].upper(),
        "resonance": pick_float(seed, "mb.res", 0.0, 1.0, 3),
        "bind_strength": pick_int(seed, "mb.str", 1, 100),
    }


def engine_meme_coin_binder(seed, ctx):
    species = ctx.get("Species", {}).get("name", "MEME")
    ticker = "$" + "".join(c for c in species.upper() if c.isalpha())[:5]
    return {
        "engine": "MemeCoinBinder",
        "ticker": ticker,
        "decimals": 9,
        "max_supply": pick_int(seed, "mcb.sup", 100_000, 1_000_000_000),
        "chain_adapter": "simulated-evm",
    }


def engine_nft_mint(seed, ctx):
    mint = simulate_mint(seed)
    return {"engine": "NFTMint", **mint}


def engine_economic(seed, ctx):
    supply = ctx.get("MemeCoinBinder", {}).get("max_supply", 1_000_000)
    price = pick_float(seed, "econ.p", 0.0001, 0.5, 6)
    return {
        "engine": "Economic",
        "initial_price_usd": price,
        "circulating_supply": int(supply * pick_float(seed, "econ.circ", 0.05, 0.4, 3)),
        "market_cap_usd_est": round(supply * price * 0.2, 2),
        "burn_rate_pct": pick_float(seed, "econ.burn", 0.0, 5.0, 2),
    }


def engine_marketplace(seed, ctx):
    base_price = ctx.get("Economic", {}).get("initial_price_usd", 0.01) * 1000
    floor = round(base_price * pick_float(seed, "mkt.fl", 0.5, 0.95, 3), 4)
    return {
        "engine": "Marketplace",
        "listable": ctx.get("Safety", {}).get("safe", True),
        "suggested_price_usd": round(base_price, 4),
        "floor_price_usd": floor,
        "royalty_pct": pick_int(seed, "mkt.roy", 2, 12),
    }


def engine_governance(seed, ctx):
    return {
        "engine": "Governance",
        "voting_power": pick_int(seed, "gov.vp", 1, 1000),
        "quorum_pct": pick_int(seed, "gov.q", 10, 75),
        "proposal_window_days": pick_int(seed, "gov.w", 1, 14),
    }


def engine_canon_vault_connector(seed, ctx):
    return {
        "engine": "CanonVaultConnector",
        "vault_namespace": "wmeu.canon.v2",
        "intake_status": "pending_approval",
        "submission_hash": hashlib.sha256(seed.encode()).hexdigest()[:32],
    }


def engine_public_canon_page(seed, ctx):
    slug = re.sub(r"[^a-z0-9-]", "-", seed.lower()).strip("-")[:48] or "asset"
    return {
        "engine": "PublicCanonPage",
        "slug": slug,
        "permalink_path": f"/canon/{{asset_id}}",
        "og_path": f"/api/public/og/{{asset_id}}.png",
        "share_text": f"PMOS•WMEU canon: {ctx.get('Identity', {}).get('true_name', seed)}",
    }


def engine_webhook(seed, ctx):
    return {
        "engine": "Webhook",
        "channels_configured": "see /api/webhooks (admin)",
        "fanout_policy": "per-event-type",
        "default_events": ["engine_error", "canon_approved", "engine_run"],
    }


def engine_chart_engine(seed, ctx):
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
    return {"engine": "ChartEngine", "rarity_distribution": rarity_buckets, "economic_curve": economic_curve}


def engine_sse_live_tick(seed, ctx):
    return {
        "engine": "SSELiveTick",
        "stream_endpoint": "/api/pmos/run/stream",
        "tick_count": 26,
        "transport": "text/event-stream",
        "finalized": True,
    }


ENGINE_ORDER = [
    "Blueprint", "Biological", "Energy", "Artifact", "Species", "Plant", "Faction", "Lore",
    "Identity", "Continuity", "Influence", "SocialGraph", "UniverseTime", "Safety", "RateLimit",
    "MemeBinding", "MemeCoinBinder", "NFTMint", "Economic", "Marketplace", "Governance",
    "CanonVaultConnector", "PublicCanonPage", "Webhook", "ChartEngine", "SSELiveTick",
]

ENGINE_FUNCS = {
    "Blueprint": engine_blueprint, "Biological": engine_biological, "Energy": engine_energy,
    "Artifact": engine_artifact, "Species": engine_species, "Plant": engine_plant,
    "Faction": engine_faction, "Lore": engine_lore, "Identity": engine_identity,
    "Continuity": engine_continuity, "Influence": engine_influence,
    "SocialGraph": engine_social_graph, "UniverseTime": engine_universe_time,
    "Safety": engine_safety, "RateLimit": engine_rate_limit,
    "MemeBinding": engine_meme_binding, "MemeCoinBinder": engine_meme_coin_binder,
    "NFTMint": engine_nft_mint, "Economic": engine_economic, "Marketplace": engine_marketplace,
    "Governance": engine_governance, "CanonVaultConnector": engine_canon_vault_connector,
    "PublicCanonPage": engine_public_canon_page, "Webhook": engine_webhook,
    "ChartEngine": engine_chart_engine, "SSELiveTick": engine_sse_live_tick,
}


async def run_single_engine(name, seed, ctx):
    if name not in ENGINE_FUNCS:
        raise ValueError(f"Unknown engine: {name}")
    await update_engine_status(name, "running", engine_version=ENGINE_VERSION)
    try:
        output = ENGINE_FUNCS[name](seed, ctx)
        if not isinstance(output, dict) or output.get("engine") != name:
            raise ValueError("Invalid engine output")
        await update_engine_status(name, "success", engine_version=ENGINE_VERSION)
        await log_system_event("engine_run", f"{name} completed", details={"engine": name})
        return output
    except Exception as exc:
        await update_engine_status(name, "error", last_error=str(exc), engine_version=ENGINE_VERSION)
        await log_system_event("engine_error", f"{name} failed: {exc}", details={"engine": name, "error": str(exc)})
        raise


# ---------------------------------------------------------------------------
# Rarity
# ---------------------------------------------------------------------------
RARITY_WEIGHTS = {"legendary": 50, "rare": 20, "uncommon": 8, "common": 2}


def compute_rarity(asset):
    engines = asset.get("engines", {})
    buckets = engines.get("ChartEngine", {}).get("rarity_distribution", [])
    score = 0
    breakdown = {}
    for b in buckets:
        w = RARITY_WEIGHTS.get(b.get("tier"), 1)
        sub = w * int(b.get("count", 0))
        score += sub
        breakdown[b["tier"]] = sub
    # v2: factor in influence
    influence = engines.get("Influence", {}).get("influence_score", 0)
    score += influence // 20
    breakdown["influence_bonus"] = influence // 20
    if asset.get("canon_approved"):
        score = int(score * 1.5)
        breakdown["canon_bonus_x1.5"] = 1
    if score >= 700:
        tier = "mythic"
    elif score >= 400:
        tier = "legendary"
    elif score >= 200:
        tier = "rare"
    elif score >= 90:
        tier = "uncommon"
    else:
        tier = "common"
    return {"score": score, "tier": tier, "breakdown": breakdown}


# ---------------------------------------------------------------------------
# Asset persistence + canon flow
# ---------------------------------------------------------------------------
async def persist_meme_asset(seed, ctx, errors):
    asset_id = new_id()
    rarity = compute_rarity({"engines": ctx, "canon_approved": False})
    nft = ctx.get("NFTMint", {})
    asset = {
        "id": asset_id, "seed": seed, "created_at": now_iso(), "completed_at": now_iso(),
        "engines": ctx, "errors": errors, "rarity": rarity, "canon_approved": False,
        "version": 1,
        "chain_hash": nft.get("chain_hash"), "token_id": nft.get("token_id"),
    }
    await db.meme_assets.insert_one({**asset, "_doc_kind": "MemeAsset"})
    if "Blueprint" in ctx:
        await db.blueprints.insert_one({"asset_id": asset_id, "blueprint": ctx["Blueprint"], "created_at": asset["created_at"]})
    if "Identity" in ctx:
        await db.identity_registry.insert_one({"asset_id": asset_id, "identity": ctx["Identity"], "created_at": asset["created_at"]})
    if nft.get("chain_hash"):
        store_chain_hash(asset_id, nft["chain_hash"])
    return asset


async def _save_canon_artifacts(asset_id: str, asset: dict) -> dict:
    """Layer 2: snapshot JSON. Layer 3: render+save OG image. Returns paths."""
    snap = save_canon_snapshot(asset_id, asset.get("version", 1), asset)
    species = asset.get("engines", {}).get("Species", {}).get("name", "Entity")
    faction = asset.get("engines", {}).get("Faction", {}).get("name", "Unbound")
    ticker = asset.get("engines", {}).get("MemeCoinBinder", {}).get("ticker", "$MEME")
    png = render_og(
        seed=asset.get("seed", ""),
        rarity_tier=asset.get("rarity", {}).get("tier", "common"),
        rarity_score=asset.get("rarity", {}).get("score", 0),
        faction=faction, species=species, ticker=ticker, asset_id=asset_id,
    )
    og = save_og_image(asset_id, png)
    return {"snapshot": snap, "og_image": og}


async def _approve_canon(asset_id: str) -> Dict[str, Any]:
    asset = await db.meme_assets.find_one({"id": asset_id}, {"_id": 0})
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    asset["canon_approved"] = True
    asset["rarity"] = compute_rarity(asset)
    await db.meme_assets.update_one({"id": asset_id}, {"$set": {"canon_approved": True, "rarity": asset["rarity"]}})
    vault_entry = {
        "id": new_id(), "asset_id": asset_id, "seed": asset.get("seed"),
        "rarity": asset["rarity"], "added_at": now_iso(), "namespace": "wmeu.canon.v2",
    }
    await db.canon_vault.insert_one(vault_entry)
    vault_entry.pop("_id", None)
    cert = {
        "id": new_id(), "asset_id": asset_id, "issued_at": now_iso(),
        "issuer": "PMOS Canon Authority", "owner": "Patrick Buckley © 2026",
        "hash": hashlib.sha256(f"cert::{asset_id}".encode()).hexdigest(),
    }
    await db.canon_certificates.insert_one(cert)
    cert.pop("_id", None)
    # Publish public canon page record
    slug = asset.get("engines", {}).get("PublicCanonPage", {}).get("slug", asset_id[:8])
    public_doc = {
        "id": new_id(), "asset_id": asset_id, "slug": slug,
        "url": f"/canon/{asset_id}",
        "og_url": f"/api/public/og/{asset_id}.png",
        "published_at": now_iso(),
    }
    await db.public_canon_pages.update_one(
        {"asset_id": asset_id}, {"$set": public_doc}, upsert=True,
    )
    # save canon artifacts
    artifacts = await _save_canon_artifacts(asset_id, asset)
    await log_system_event("canon_approved", f"Asset {asset_id[:8]} entered canon", related_id=asset_id, details={"artifacts": artifacts})
    return {"vault_entry": vault_entry, "certificate": cert, "public": public_doc, "artifacts": artifacts}


# ---------------------------------------------------------------------------
# Auth endpoints
# ---------------------------------------------------------------------------
@api.post("/auth/register")
async def register(body: RegisterRequest):
    email = body.email.lower()
    if await db.users.find_one({"email": email}):
        raise HTTPException(status_code=400, detail="Email already registered")
    doc = {
        "email": email, "name": body.name or email.split("@")[0],
        "password_hash": hash_password(body.password), "role": "member", "created_at": now_iso(),
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
    return {"token": token, "user": {"id": uid, "email": email, "name": user.get("name"), "role": user.get("role", "member")}}


@api.get("/auth/me")
async def me(user: Dict[str, Any] = Depends(get_current_user)):
    return user


# ---------------------------------------------------------------------------
# PMOS endpoints
# ---------------------------------------------------------------------------
@api.post("/pmos/run")
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
        await _approve_canon(asset["id"])
        refreshed = await db.meme_assets.find_one({"id": asset["id"]}, {"_id": 0})
        if refreshed:
            asset = refreshed
    await log_system_event("engine_run", f"runPMOS completed for seed={body.seed[:24]}", related_id=asset["id"], details={"errors": errors, "rarity": asset["rarity"]})
    return asset


@api.get("/pmos/run/stream")
async def run_pmos_stream(seed: str, enrich_ai: bool = False):
    """SSE — yields engine-by-engine status, then the final asset."""
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

    return StreamingResponse(gen(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


def _sse(event: str, data: Any) -> bytes:
    return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n".encode()


@api.post("/pmos/debug")
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


@api.post("/pmos/engine-status/update")
async def api_update_engine_status(body: EngineStatusUpdate):
    return await update_engine_status(body.engine_name, body.status, body.last_error, body.engine_version)


@api.get("/pmos/engine-status")
async def list_engine_status():
    docs = await db.engine_status.find({}, {"_id": 0}).to_list(200)
    by_name = {d["engine_name"]: d for d in docs}
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
    return {"order": ENGINE_ORDER, "version": ENGINE_VERSION, "count": len(ENGINE_ORDER)}


# ---------------------------------------------------------------------------
# Meme assets
# ---------------------------------------------------------------------------
@api.get("/meme-assets")
async def list_meme_assets(limit: int = 50):
    return await db.meme_assets.find({}, {"_id": 0}).sort("created_at", -1).to_list(limit)


@api.get("/meme-assets/{asset_id}")
async def get_meme_asset(asset_id: str):
    doc = await db.meme_assets.find_one({"id": asset_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Asset not found")
    return doc


@api.post("/meme-assets/{asset_id}/approve")
async def approve_asset(asset_id: str, user: Dict[str, Any] = Depends(require_admin)):
    return await _approve_canon(asset_id)


# ---------------------------------------------------------------------------
# Canon Vault
# ---------------------------------------------------------------------------
@api.get("/canon-vault")
async def list_canon_vault(limit: int = 50):
    return await db.canon_vault.find({}, {"_id": 0}).sort("added_at", -1).to_list(limit)


@api.get("/canon-vault/{asset_id}/certificate")
async def get_certificate(asset_id: str):
    doc = await db.canon_certificates.find_one({"asset_id": asset_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="No certificate")
    return doc


# ---------------------------------------------------------------------------
# Marketplace
# ---------------------------------------------------------------------------
@api.get("/marketplace")
async def list_marketplace():
    return await db.marketplace_listings.find({"active": True}, {"_id": 0}).sort("created_at", -1).to_list(200)


@api.post("/marketplace")
async def create_listing(body: MarketplaceListingCreate, user: Dict[str, Any] = Depends(get_current_user)):
    asset = await db.meme_assets.find_one({"id": body.asset_id}, {"_id": 0})
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    if not asset.get("canon_approved"):
        raise HTTPException(status_code=400, detail="Only canon-approved assets can be listed")
    if not asset.get("engines", {}).get("Safety", {}).get("safe", True):
        raise HTTPException(status_code=400, detail="Asset failed safety check")
    doc = {
        "id": new_id(), "asset_id": body.asset_id, "price_usd": body.price_usd,
        "description": body.description, "seller_email": user["email"],
        "active": True, "created_at": now_iso(),
        "rarity": asset.get("rarity"), "seed": asset.get("seed"),
    }
    await db.marketplace_listings.insert_one(doc)
    doc.pop("_id", None)
    await log_system_event("marketplace_listed", f"{user['email']} listed {body.asset_id[:8]} @ ${body.price_usd}", related_id=doc["id"])
    return doc


@api.delete("/marketplace/{listing_id}")
async def delist(listing_id: str, user: Dict[str, Any] = Depends(get_current_user)):
    res = await db.marketplace_listings.update_one({"id": listing_id}, {"$set": {"active": False}})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Listing not found")
    return {"ok": True}


# ---------------------------------------------------------------------------
# Governance
# ---------------------------------------------------------------------------
@api.get("/governance/proposals")
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


@api.post("/governance/proposals")
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


@api.post("/governance/vote")
async def cast_vote(body: VoteCreate, user: Dict[str, Any] = Depends(get_current_user)):
    if body.choice not in ("yes", "no", "abstain"):
        raise HTTPException(status_code=400, detail="Invalid choice")
    if not await db.proposals.find_one({"id": body.proposal_id}):
        raise HTTPException(status_code=404, detail="Proposal not found")
    existing = await db.votes.find_one({"proposal_id": body.proposal_id, "voter_email": user["email"]})
    if existing:
        await db.votes.update_one({"_id": existing["_id"]}, {"$set": {"choice": body.choice, "updated_at": now_iso()}})
    else:
        await db.votes.insert_one({"id": new_id(), "proposal_id": body.proposal_id, "voter_email": user["email"], "choice": body.choice, "cast_at": now_iso()})
    await log_system_event("vote_cast", f"{user['email']} voted {body.choice}", related_id=body.proposal_id)
    return {"ok": True}


@api.get("/governance/amendments")
async def list_amendments():
    return await db.constitution_amendments.find({}, {"_id": 0}).sort("created_at", -1).to_list(100)


@api.post("/governance/amendments")
async def add_amendment(body: ProposalCreate, user: Dict[str, Any] = Depends(require_admin)):
    doc = {
        "id": new_id(), "title": body.title, "body": body.description, "created_by": user["email"],
        "created_at": now_iso(), "version": int(datetime.now(timezone.utc).timestamp()),
    }
    await db.constitution_amendments.insert_one(doc)
    doc.pop("_id", None)
    await log_system_event("amendment_added", f"Constitution amended: {body.title}", related_id=doc["id"])
    return doc


# ---------------------------------------------------------------------------
# Webhooks (admin)
# ---------------------------------------------------------------------------
@api.get("/webhooks")
async def list_webhooks(user: Dict[str, Any] = Depends(require_admin)):
    return await db.webhook_configs.find({}, {"_id": 0}).to_list(50)


@api.post("/webhooks")
async def add_webhook(body: WebhookConfigCreate, user: Dict[str, Any] = Depends(require_admin)):
    doc = {"id": new_id(), "url": body.url, "label": body.label, "event_types": body.event_types, "created_at": now_iso(), "created_by": user["email"]}
    await db.webhook_configs.insert_one(doc)
    doc.pop("_id", None)
    return doc


@api.delete("/webhooks/{wid}")
async def delete_webhook(wid: str, user: Dict[str, Any] = Depends(require_admin)):
    await db.webhook_configs.delete_one({"id": wid})
    return {"ok": True}


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
    return {"score": score, "tier": tier, "formula": "Σ(traits × weight) × (1.5 if canon)", "weights": RARITY_WEIGHTS}


@api.post("/economic/simulate")
async def economic_sim(body: EconomicSimInput):
    rows, supply, price = [], body.initial_supply, body.mint_cost
    for m in range(0, body.horizon_months + 1):
        rows.append({"month": m, "supply": round(supply, 2), "price_usd": round(price, 6), "market_cap": round(supply * price, 2)})
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
# Public canon pages + OG (Layer 3 served by backend)
# ---------------------------------------------------------------------------
@api.get("/public/og/{asset_id}.png")
async def public_og(asset_id: str):
    try:
        data, ct = get_object(f"canon/{asset_id}/og.png")
        return Response(content=data, media_type="image/png")
    except FileNotFoundError:
        # regenerate on the fly if asset exists
        asset = await db.meme_assets.find_one({"id": asset_id}, {"_id": 0})
        if not asset:
            raise HTTPException(status_code=404, detail="Asset not found")
        species = asset.get("engines", {}).get("Species", {}).get("name", "Entity")
        faction = asset.get("engines", {}).get("Faction", {}).get("name", "Unbound")
        ticker = asset.get("engines", {}).get("MemeCoinBinder", {}).get("ticker", "$MEME")
        png = render_og(asset.get("seed", ""), asset.get("rarity", {}).get("tier", "common"), asset.get("rarity", {}).get("score", 0), faction, species, ticker, asset_id)
        save_og_image(asset_id, png)
        return Response(content=png, media_type="image/png")


@api.get("/public/canon/{asset_id}.json")
async def public_canon_json(asset_id: str):
    asset = await db.meme_assets.find_one({"id": asset_id}, {"_id": 0})
    if not asset or not asset.get("canon_approved"):
        raise HTTPException(status_code=404, detail="Not in canon")
    return asset


@app.get("/canon/{asset_id}", response_class=HTMLResponse)
async def public_canon_page(asset_id: str):
    """Server-rendered public canon page (Layer 3 — public CDN substitute).
    OG meta tags are critical for shareability.
    """
    asset = await db.meme_assets.find_one({"id": asset_id}, {"_id": 0})
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    if not asset.get("canon_approved"):
        raise HTTPException(status_code=403, detail="Asset not in canon")
    species = asset.get("engines", {}).get("Species", {}).get("name", "Entity")
    faction = asset.get("engines", {}).get("Faction", {}).get("name", "Unbound")
    identity = asset.get("engines", {}).get("Identity", {}).get("true_name", asset.get("seed", ""))
    epithet = asset.get("engines", {}).get("Identity", {}).get("epithet", "")
    ticker = asset.get("engines", {}).get("MemeCoinBinder", {}).get("ticker", "$MEME")
    lore = asset.get("engines", {}).get("Lore", {}).get("summary", "")
    rarity = asset.get("rarity", {})
    base = PUBLIC_BASE_URL or ""
    og_url = f"{base}/api/public/og/{asset_id}.png"
    canon_url = f"{base}/canon/{asset_id}"
    return HTMLResponse(f"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>{identity} {epithet} · PMOS•WMEU Canon</title>
<meta name="description" content="{species} of {faction} — {rarity.get('tier','common').upper()} canon Meme Asset. Mint your own at PMOS•WMEU."/>
<meta property="og:title" content="{identity} {epithet}"/>
<meta property="og:description" content="{species} · {faction} · {rarity.get('tier','common').upper()} · score {rarity.get('score',0)}"/>
<meta property="og:image" content="{og_url}"/>
<meta property="og:url" content="{canon_url}"/>
<meta property="og:type" content="article"/>
<meta name="twitter:card" content="summary_large_image"/>
<meta name="twitter:image" content="{og_url}"/>
<link rel="preconnect" href="https://fonts.googleapis.com"/>
<link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;700&family=Rajdhani:wght@400;600;700&display=swap" rel="stylesheet"/>
<style>
body {{ margin:0; background:#05050A; color:#E2E8F0; font-family: 'JetBrains Mono', monospace; }}
.wrap {{ max-width: 920px; margin: 0 auto; padding: 48px 24px; }}
h1, .display {{ font-family: 'Rajdhani', sans-serif; font-weight: 700; letter-spacing: -0.5px; }}
.eyebrow {{ font-family: 'Rajdhani'; text-transform: uppercase; letter-spacing: 0.28em; color: #00F0FF; font-size: 12px; }}
.card {{ background:#0B0C15; border:1px solid #1A1D2E; padding: 24px; margin-bottom: 16px; }}
.glow {{ border-color: rgba(0,240,255,0.3); box-shadow: 0 0 24px rgba(0,240,255,0.06); }}
.badge {{ display:inline-block; border:1px solid; padding: 4px 10px; font-size: 11px; text-transform: uppercase; letter-spacing: 0.18em; margin-right: 8px; font-family:'Rajdhani'; }}
.b-cyan {{ color:#00F0FF; border-color:#00F0FF; }}
.b-mag {{ color:#FF00FF; border-color:#FF00FF; }}
.b-emer {{ color:#00FF66; border-color:#00FF66; }}
img.og {{ max-width:100%; border:1px solid #1A1D2E; display:block; margin-bottom: 24px; }}
.cta a {{ display:inline-block; padding: 10px 18px; border: 1px solid #00F0FF; color:#00F0FF; text-decoration:none; font-family:'Rajdhani'; text-transform:uppercase; letter-spacing:0.18em; margin-right: 8px; }}
.cta a:hover {{ background:#00F0FF; color:#000; }}
hr {{ border:none; border-top:1px solid #1A1D2E; margin: 24px 0; }}
.foot {{ color:#475569; font-size: 11px; }}
.kv {{ font-size: 12px; line-height: 1.8; }}
.kv span:first-child {{ color:#475569; display:inline-block; min-width: 130px; }}
.kv span:last-child {{ color:#00F0FF; }}
</style></head>
<body><div class="wrap">
<img class="og" src="{og_url}" alt="OG image for {identity}"/>
<div class="eyebrow">PMOS • WMEU Canon Entry</div>
<h1 style="font-size:48px;margin:8px 0 4px;">{identity}</h1>
<div class="display" style="color:#FF00FF;font-size:22px;">{epithet}</div>
<div style="margin:18px 0;">
  <span class="badge b-mag">{rarity.get('tier','common')}</span>
  <span class="badge b-cyan">score {rarity.get('score',0)}</span>
  <span class="badge b-emer">canon</span>
  <span class="badge b-cyan">{ticker}</span>
</div>
<div class="card glow">
  <div class="eyebrow">Lore</div>
  <p style="line-height:1.7;">{lore}</p>
</div>
<div class="card">
  <div class="eyebrow">Identity Record</div>
  <div class="kv">
    <div><span>Species</span><span>{species}</span></div>
    <div><span>Faction</span><span>{faction}</span></div>
    <div><span>Seed</span><span>{asset.get('seed','')}</span></div>
    <div><span>Token ID</span><span>{asset.get('token_id','—')}</span></div>
    <div><span>Chain hash</span><span style="word-break:break-all;">{asset.get('chain_hash','—')}</span></div>
  </div>
</div>
<div class="cta">
  <a href="{base}/">Mint your own</a>
  <a href="{base}/api/public/canon/{asset_id}.json">View JSON</a>
</div>
<hr/>
<div class="foot">© 2026 Patrick Buckley · P.BUCK™ · PMOS™ · WMEU™ · Waboot Meme Engine Universe™ · Buckley Labs LLC (pending). This page is part of the WMEU canon and protected under the Universal Hub Clause.</div>
</div></body></html>""")


# ---------------------------------------------------------------------------
# Docs
# ---------------------------------------------------------------------------
DOCS = {
    "constitution": {
        "title": "WMEU Constitution v2.0",
        "body": (
            "Article I — The PMOS pipeline shall consist of twenty-six (26) ordered engines.\n"
            "Article II — All Meme Assets generated by PMOS belong to the seed-submitter, subject to "
            "the canon process and rights reserved by Patrick Buckley © 2026.\n"
            "Article III — Canon admission requires governance approval or admin fiat.\n"
            "Article IV — Amendments require a qualified governance vote or direct admin issuance.\n"
            "Article V — All sub-brands (P.BUCK, PMOS, WMEU, Waboot Meme Engine Universe) are "
            "trademarks of Patrick Buckley, to be assigned to Buckley Labs LLC upon registration.\n"
            "Article VI (NEW v2) — Safety and RateLimit engines may veto admission. Marketplace listings "
            "require canon status and a passing Safety result. Public canon pages are immutable once published; "
            "amendments produce new versions, not edits."
        ),
    },
    "rarity_formula": {"title": "Rarity Formula", "body": "score = Σ(trait_count × tier_weight) + influence_bonus; ×1.5 if canon. tier_weight = {legendary:50, rare:20, uncommon:8, common:2}."},
    "engine_order": {"title": "Engine Order (26)", "body": " → ".join(f"{i+1}.{n}" for i, n in enumerate(ENGINE_ORDER))},
    "canon_process": {"title": "Canon Process", "body": "1. Run PMOS. 2. Review. 3. Open governance proposal OR admin auto-approves. 4. Canon snapshot + OG image are written; public page is published. 5. Rarity recomputed with ×1.5 bonus."},
    "debug_checklist": {"title": "Debug Checklist", "body": "• Every engine emits JSON with 'engine' key matching name.\n• debugPMOS without name tests all 26.\n• EngineStatus + SystemEvent updated for every run.\n• engine_error events fan out to configured webhooks."},
    "amendment_log": {"title": "Amendment Log", "body": "See /api/governance/amendments"},
    "storage_layers": {
        "title": "Storage Architecture (4 Layers)",
        "body": (
            "Layer 1 — MongoDB (primary): 12 collections.\n"
            "Layer 2 — Immutable canon storage (Emergent object storage with local fallback): canon/{id}/v{n}.json + og.png.\n"
            "Layer 3 — Public CDN substitute (backend-served at /canon/{id} + /api/public/og/{id}.png with full OG meta).\n"
            "Layer 4 — Chain adapter (simulated EVM today; pluggable Solana/Polygon/Base later)."
        ),
    },
    "legal": {
        "copyright": (
            "Copyright © 2026 Patrick Buckley. All rights reserved.\n"
            "PMOS • WMEU — Meme Civilization Engine (Universe-Class Edition) and all derivative works, "
            "source code, engine outputs, lore, branding marks (P.BUCK, PMOS, WMEU, Waboot Meme Engine "
            "Universe), Meme Assets, canon certificates, OG renditions, and public canon pages generated "
            "by this system are the intellectual property of Patrick Buckley."
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
            "PROPRIETARY LICENSE — PMOS • WMEU v2.0\n"
            "This software and its outputs are the proprietary work of Patrick Buckley (the “Owner”). "
            "Permission is hereby granted to authorized operators to use the hosted system for the "
            "stated purposes of meme civilization generation, governance, marketplace listing, and canon "
            "curation. Redistribution, decompilation, reverse-engineering, or commercial fork without "
            "prior written consent of the Owner is strictly prohibited. Generated Meme Assets are "
            "licensed to their seed-submitters for personal and promotional use, subject to canon process, "
            "Safety engine rulings, and trademark notice."
        ),
        "to_whom_it_may_concern": (
            "TO WHOM IT MAY CONCERN\n\n"
            "Be it known that Patrick Buckley is the sole creator, owner, and rights-holder of the "
            "PMOS • WMEU — Meme Civilization Engine, including its 26-engine pipeline architecture, "
            "the runPMOS / debugPMOS / updateEngineStatus / logSystemEvent / SSE Live Tick workflows, "
            "the Canon Vault, governance protocols, Marketplace, and Public Canon Page system, and all "
            "associated branding (P.BUCK, PMOS, WMEU, Waboot Meme Engine Universe). This document "
            "serves as formal notice of authorship and ownership as of 2026. All rights are reserved "
            "pending the formation of Buckley Labs LLC.\n\n"
            "Signed,\nPatrick Buckley\nFounder, PMOS • WMEU\n2026"
        ),
        "universal_hub_clause": (
            "UNIVERSAL HUB CLAUSE\n"
            "PMOS • WMEU is designated by its Owner as the canonical universal hub for the addition, "
            "registration, marketplace listing, and testing of memes within the P.BUCK / Waboot "
            "ecosystem. Third-party meme integrations are welcomed under the canon process and the "
            "Safety / RateLimit engines. The Owner retains final authority over hub admission and may "
            "suspend or revoke entries that conflict with the Constitution or trademark protections."
        ),
    },
}


@api.get("/docs/all")
async def docs_all():
    amendments = await db.constitution_amendments.find({}, {"_id": 0}).sort("created_at", -1).to_list(50)
    return {**DOCS, "amendments": amendments}


# ---------------------------------------------------------------------------
# Root
# ---------------------------------------------------------------------------
@api.get("/")
async def root():
    return {
        "name": "PMOS • WMEU API",
        "version": "2.0.0",
        "engine_count": len(ENGINE_ORDER),
        "engines": ENGINE_ORDER,
        "copyright": "© 2026 Patrick Buckley",
        "edition": "Universe-Class",
    }


# ---------------------------------------------------------------------------
# Startup
# ---------------------------------------------------------------------------
@app.on_event("startup")
async def on_startup():
    try:
        await db.users.create_index("email", unique=True)
        await db.meme_assets.create_index("id", unique=True)
        await db.canon_vault.create_index("asset_id")
        await db.proposals.create_index("id", unique=True)
        await db.votes.create_index([("proposal_id", 1), ("voter_email", 1)], unique=True)
        await db.engine_status.create_index("engine_name", unique=True)
        await db.marketplace_listings.create_index("id", unique=True)
        await db.public_canon_pages.create_index("asset_id", unique=True)
        await db.identity_registry.create_index("asset_id")
        await db.webhook_configs.create_index("id", unique=True)
    except Exception as exc:
        logger.warning(f"index init: {exc}")

    admin_email = os.environ["ADMIN_EMAIL"].lower()
    admin_pw = os.environ["ADMIN_PASSWORD"]
    existing = await db.users.find_one({"email": admin_email})
    if not existing:
        await db.users.insert_one({"email": admin_email, "name": "Patrick Buckley", "password_hash": hash_password(admin_pw), "role": "admin", "created_at": now_iso()})
        logger.info("Seeded admin user")
    elif not verify_password(admin_pw, existing["password_hash"]):
        await db.users.update_one({"email": admin_email}, {"$set": {"password_hash": hash_password(admin_pw)}})
        logger.info("Updated admin password")

    for name in ENGINE_ORDER:
        await db.engine_status.update_one(
            {"engine_name": name},
            {"$setOnInsert": {"status": "idle", "last_run": None, "last_error": None, "engine_version": ENGINE_VERSION}},
            upsert=True,
        )

    try:
        init_storage()
    except Exception as exc:
        logger.warning(f"storage startup: {exc}")


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
