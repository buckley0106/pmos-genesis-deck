"""26-engine PMOS v2.0 pipeline + canon flow (persist / approve / render / OG)."""
from __future__ import annotations

import hashlib
import io
import logging
import re
from typing import Any, Dict, List

from fastapi import HTTPException
from fastapi.responses import HTMLResponse
from PIL import Image as _PILImage

from deps import (
    ENGINE_VERSION, PUBLIC_BASE_URL, db, log_system_event, new_id, now_iso,
    pick, pick_float, pick_int, safety_flags, seed_hash, update_engine_status,
)
from canon_storage import save_canon_snapshot, save_og_image
from chain_adapter import simulate_mint, store_chain_hash
from og_image import render_og

logger = logging.getLogger("pmos.engines")


# ---------------------------------------------------------------------------
# Engines
# ---------------------------------------------------------------------------
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


def engine_safety(seed, ctx):
    text = seed + " " + ctx.get("Lore", {}).get("summary", "")
    flagged = safety_flags(text)
    return {
        "engine": "Safety",
        "safe": len(flagged) == 0,
        "flags": flagged,
        "policy_version": "wmeu.safety.v2",
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
        "permalink_path": "/api/canon/{asset_id}/page",
        "og_path": "/api/public/og/{asset_id}.png",
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


ENGINE_ORDER: List[str] = [
    "Blueprint", "Biological", "Energy", "Artifact", "Species", "Plant", "Faction", "Lore",
    "Identity", "Continuity", "Influence", "SocialGraph", "UniverseTime", "Safety", "RateLimit",
    "MemeBinding", "MemeCoinBinder", "Governance", "Economic", "CanonVaultConnector",
    "PublicCanonPage", "NFTMint", "Marketplace", "Webhook", "ChartEngine", "SSELiveTick",
]

ENGINE_FUNCS: Dict[str, Any] = {
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


async def run_single_engine(name: str, seed: str, ctx: Dict[str, Any]) -> Dict[str, Any]:
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


def compute_rarity(asset: Dict[str, Any]) -> Dict[str, Any]:
    engines = asset.get("engines", {})
    buckets = engines.get("ChartEngine", {}).get("rarity_distribution", [])
    score = 0
    breakdown: Dict[str, Any] = {}
    for b in buckets:
        w = RARITY_WEIGHTS.get(b.get("tier"), 1)
        sub = w * int(b.get("count", 0))
        score += sub
        breakdown[b["tier"]] = sub
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
# Canon persistence + approve + render
# ---------------------------------------------------------------------------
async def persist_meme_asset(seed: str, ctx: Dict[str, Any], errors: List[Dict[str, Any]]) -> Dict[str, Any]:
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


async def _save_canon_artifacts(asset_id: str, asset: Dict[str, Any]) -> Dict[str, Any]:
    snap = save_canon_snapshot(asset_id, asset.get("version", 1), asset)
    engines = asset.get("engines", {})
    species = engines.get("Species", {}).get("name", "Entity")
    faction = engines.get("Faction", {}).get("name", "Unbound")
    ticker = engines.get("MemeCoinBinder", {}).get("ticker", "$MEME")
    try:
        png = render_og(
            seed=asset.get("seed", ""),
            rarity_tier=asset.get("rarity", {}).get("tier", "common"),
            rarity_score=asset.get("rarity", {}).get("score", 0),
            faction=faction, species=species, ticker=ticker, asset_id=asset_id,
        )
    except Exception as exc:
        logger.warning(f"render_og failed: {exc}; using placeholder")
        _img = _PILImage.new("RGB", (1200, 630), (5, 5, 10))
        _buf = io.BytesIO(); _img.save(_buf, "PNG"); png = _buf.getvalue()
    og = save_og_image(asset_id, png)
    return {"snapshot": snap, "og_image": og}


async def approve_canon(asset_id: str) -> Dict[str, Any]:
    asset = await db.meme_assets.find_one({"id": asset_id}, {"_id": 0})
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    safe = asset.get("engines", {}).get("Safety", {}).get("safe", True)
    if not safe:
        raise HTTPException(status_code=400, detail="Asset failed Safety engine; cannot canonize")
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
    slug = asset.get("engines", {}).get("PublicCanonPage", {}).get("slug", asset_id[:8])
    public_doc = {
        "id": new_id(), "asset_id": asset_id, "slug": slug,
        "url": f"/api/canon/{asset_id}/page",
        "og_url": f"/api/public/og/{asset_id}.png",
        "published_at": now_iso(),
    }
    await db.public_canon_pages.update_one({"asset_id": asset_id}, {"$set": public_doc}, upsert=True)
    artifacts = await _save_canon_artifacts(asset_id, asset)
    await log_system_event("canon_approved", f"Asset {asset_id[:8]} entered canon", related_id=asset_id, details={"artifacts": artifacts})
    return {"vault_entry": vault_entry, "certificate": cert, "public": public_doc, "artifacts": artifacts}


async def render_public_canon_html(asset_id: str) -> HTMLResponse:
    asset = await db.meme_assets.find_one({"id": asset_id}, {"_id": 0})
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    if not asset.get("canon_approved"):
        raise HTTPException(status_code=403, detail="Asset not in canon")
    e = asset.get("engines", {})
    species = e.get("Species", {}).get("name", "Entity")
    faction = e.get("Faction", {}).get("name", "Unbound")
    identity = e.get("Identity", {}).get("true_name", asset.get("seed", ""))
    epithet = e.get("Identity", {}).get("epithet", "")
    ticker = e.get("MemeCoinBinder", {}).get("ticker", "$MEME")
    lore = e.get("Lore", {}).get("summary", "")
    rarity = asset.get("rarity", {})
    base = PUBLIC_BASE_URL or ""
    og_url = f"{base}/api/public/og/{asset_id}.png"
    canon_url = f"{base}/api/canon/{asset_id}/page"
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
