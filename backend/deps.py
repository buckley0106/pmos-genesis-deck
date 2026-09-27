"""Shared runtime primitives — DB client, auth, helpers, workflows, docs, safety cache."""
from __future__ import annotations

import hashlib
import logging
import os
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Set

import bcrypt
import jwt
from bson import ObjectId
from fastapi import Depends, HTTPException, Request
from motor.motor_asyncio import AsyncIOMotorClient

import webhook as wh

logger = logging.getLogger("pmos")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
JWT_SECRET = os.environ["JWT_SECRET"]
JWT_ALG = "HS256"
PUBLIC_BASE_URL = os.environ.get("PUBLIC_BASE_URL", "")
ENGINE_VERSION = "2.0.0"

# ---------------------------------------------------------------------------
# Mongo
# ---------------------------------------------------------------------------
mongo_client = AsyncIOMotorClient(os.environ["MONGO_URL"])
db = mongo_client[os.environ["DB_NAME"]]


# ---------------------------------------------------------------------------
# Timestamps / ids
# ---------------------------------------------------------------------------
def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id() -> str:
    return str(uuid.uuid4())


# ---------------------------------------------------------------------------
# Seed helpers
# ---------------------------------------------------------------------------
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
# Auth
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
# Workflow primitives
# ---------------------------------------------------------------------------
async def update_engine_status(engine_name: str, status_value: str, last_error: Optional[str] = None, engine_version: str = ENGINE_VERSION):
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


async def log_system_event(event_type: str, summary: str, related_id: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
    doc = {
        "event_id": new_id(), "timestamp": now_iso(), "type": event_type, "summary": summary,
        "related_id": related_id, "details": details or {},
    }
    await db.system_events.insert_one(doc)
    doc.pop("_id", None)
    if event_type in ("engine_error", "canon_approved", "engine_run"):
        try:
            await _fire_webhooks(event_type, summary, related_id, details or {})
        except Exception as exc:
            logger.debug(f"webhook dispatch error: {exc}")
    return doc


# ---------------------------------------------------------------------------
# Safety blocklist — Mongo-backed with in-memory cache
# ---------------------------------------------------------------------------
DEFAULT_SAFETY_BLOCKLIST: List[str] = ["kill", "csam", "exploit-violence"]
_safety_cache: Set[str] = set(DEFAULT_SAFETY_BLOCKLIST)


async def refresh_safety_cache() -> List[str]:
    """Reload the safety blocklist from Mongo into the in-memory cache."""
    global _safety_cache
    docs = await db.safety_blocklist.find({}, {"_id": 0}).to_list(1000)
    _safety_cache = {d["word"].lower() for d in docs if d.get("word")}
    if not _safety_cache:
        _safety_cache = set(DEFAULT_SAFETY_BLOCKLIST)
    return sorted(_safety_cache)


def safety_flags(text: str) -> List[str]:
    """Return matched blocklist words in the given text (uses the in-memory cache)."""
    if not text:
        return []
    lower = text.lower()
    return sorted([w for w in _safety_cache if w and w in lower])


async def seed_safety_defaults() -> None:
    """Idempotent — inserts default words only if the collection is empty."""
    count = await db.safety_blocklist.count_documents({})
    if count == 0:
        for w in DEFAULT_SAFETY_BLOCKLIST:
            await db.safety_blocklist.update_one(
                {"word": w}, {"$setOnInsert": {"word": w, "created_at": now_iso(), "created_by": "system"}}, upsert=True,
            )


# ---------------------------------------------------------------------------
# Docs pack
# ---------------------------------------------------------------------------
def build_docs(engine_order: List[str]) -> Dict[str, Any]:
    return {
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
                "Article VI — Safety and RateLimit engines may veto admission. Marketplace listings "
                "require canon status and a passing Safety result. Public canon pages are immutable once published."
            ),
        },
        "rarity_formula": {"title": "Rarity Formula", "body": "score = Σ(trait_count × tier_weight) + influence_bonus; ×1.5 if canon. tier_weight = {legendary:50, rare:20, uncommon:8, common:2}."},
        "engine_order": {"title": "Engine Order (26)", "body": " → ".join(f"{i+1}.{n}" for i, n in enumerate(engine_order))},
        "canon_process": {"title": "Canon Process", "body": "1. Run PMOS. 2. Review. 3. Open governance proposal OR admin auto-approves. 4. Canon snapshot + OG image are written; public page is published. 5. Rarity recomputed with ×1.5 bonus."},
        "debug_checklist": {"title": "Debug Checklist", "body": "• Every engine emits JSON with 'engine' key matching name.\n• debugPMOS without name tests all 26.\n• EngineStatus + SystemEvent updated for every run.\n• engine_error events fan out to configured webhooks."},
        "amendment_log": {"title": "Amendment Log", "body": "See /api/governance/amendments"},
        "storage_layers": {
            "title": "Storage Architecture (4 Layers)",
            "body": (
                "Layer 1 — MongoDB (primary): 15 collections including safety_blocklist.\n"
                "Layer 2 — Immutable canon storage (Emergent object storage with local fallback): canon/{id}/v{n}.json + og.png.\n"
                "Layer 3 — Public CDN substitute (backend-served at /api/canon/{id}/page + /api/public/og/{id}.png with full OG meta).\n"
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
