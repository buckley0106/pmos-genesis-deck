"""Canon router — meme-assets, canon-vault, public canon page + OG, admin approve."""
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import HTMLResponse

from canon_storage import get_object, save_og_image
from deps import db, require_admin
from engines import approve_canon, render_public_canon_html
from og_image import render_og

router = APIRouter(prefix="/api", tags=["canon"])


# --- meme assets ------------------------------------------------------------
@router.get("/meme-assets")
async def list_meme_assets(limit: int = 50):
    return await db.meme_assets.find({}, {"_id": 0}).sort("created_at", -1).to_list(limit)


@router.get("/meme-assets/{asset_id}")
async def get_meme_asset(asset_id: str):
    doc = await db.meme_assets.find_one({"id": asset_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Asset not found")
    return doc


@router.post("/meme-assets/{asset_id}/approve")
async def approve_asset(asset_id: str, user: Dict[str, Any] = Depends(require_admin)):
    return await approve_canon(asset_id)


# --- canon vault ------------------------------------------------------------
@router.get("/canon-vault")
async def list_canon_vault(limit: int = 50):
    return await db.canon_vault.find({}, {"_id": 0}).sort("added_at", -1).to_list(limit)


@router.get("/canon-vault/{asset_id}/certificate")
async def get_certificate(asset_id: str):
    doc = await db.canon_certificates.find_one({"asset_id": asset_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="No certificate")
    return doc


# --- public canon (Layer 3 served by backend) -------------------------------
@router.get("/public/og/{asset_id}.png")
async def public_og(asset_id: str):
    try:
        data, _ct = get_object(f"canon/{asset_id}/og.png")
        return Response(content=data, media_type="image/png")
    except FileNotFoundError:
        asset = await db.meme_assets.find_one({"id": asset_id}, {"_id": 0})
        if not asset:
            raise HTTPException(status_code=404, detail="Asset not found")
        engines = asset.get("engines", {})
        species = engines.get("Species", {}).get("name", "Entity")
        faction = engines.get("Faction", {}).get("name", "Unbound")
        ticker = engines.get("MemeCoinBinder", {}).get("ticker", "$MEME")
        png = render_og(
            asset.get("seed", ""),
            asset.get("rarity", {}).get("tier", "common"),
            asset.get("rarity", {}).get("score", 0),
            faction, species, ticker, asset_id,
        )
        save_og_image(asset_id, png)
        return Response(content=png, media_type="image/png")


@router.get("/public/canon/{asset_id}.json")
async def public_canon_json(asset_id: str):
    asset = await db.meme_assets.find_one({"id": asset_id}, {"_id": 0})
    if not asset or not asset.get("canon_approved"):
        raise HTTPException(status_code=404, detail="Not in canon")
    return asset


@router.get("/canon/{asset_id}/page", response_class=HTMLResponse)
async def public_canon_page(asset_id: str):
    return await render_public_canon_html(asset_id)
