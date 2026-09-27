"""Marketplace router — canon-only listings, safety-gated create."""
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException

from deps import db, get_current_user, log_system_event, new_id, now_iso
from models import MarketplaceListingCreate

router = APIRouter(prefix="/api/marketplace", tags=["marketplace"])


@router.get("")
async def list_marketplace():
    return await db.marketplace_listings.find({"active": True}, {"_id": 0}).sort("created_at", -1).to_list(200)


@router.post("")
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
        "og_url": f"/api/public/og/{body.asset_id}.png",
    }
    await db.marketplace_listings.insert_one(doc)
    doc.pop("_id", None)
    await log_system_event(
        "marketplace_listed",
        f"{user['email']} listed {body.asset_id[:8]} @ ${body.price_usd}",
        related_id=doc["id"],
    )
    return doc


@router.delete("/{listing_id}")
async def delist(listing_id: str, user: Dict[str, Any] = Depends(get_current_user)):
    res = await db.marketplace_listings.update_one({"id": listing_id}, {"$set": {"active": False}})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Listing not found")
    return {"ok": True}
