"""Admin config routers — webhooks + safety blocklist."""
from typing import Any, Dict, List

from fastapi import APIRouter, Depends

from deps import (
    db, new_id, now_iso, refresh_safety_cache, require_admin,
)
from models import SafetyWordCreate, WebhookConfigCreate

router = APIRouter(prefix="/api", tags=["admin-config"])


# --- Webhooks ---------------------------------------------------------------
@router.get("/webhooks")
async def list_webhooks(user: Dict[str, Any] = Depends(require_admin)):
    return await db.webhook_configs.find({}, {"_id": 0}).to_list(50)


@router.post("/webhooks")
async def add_webhook(body: WebhookConfigCreate, user: Dict[str, Any] = Depends(require_admin)):
    doc = {
        "id": new_id(), "url": body.url, "label": body.label, "event_types": body.event_types,
        "created_at": now_iso(), "created_by": user["email"],
    }
    await db.webhook_configs.insert_one(doc)
    doc.pop("_id", None)
    return doc


@router.delete("/webhooks/{wid}")
async def delete_webhook(wid: str, user: Dict[str, Any] = Depends(require_admin)):
    await db.webhook_configs.delete_one({"id": wid})
    return {"ok": True}


# --- Safety blocklist -------------------------------------------------------
@router.get("/safety/blocklist")
async def list_safety_words(user: Dict[str, Any] = Depends(require_admin)) -> Dict[str, List[str]]:
    words = await refresh_safety_cache()
    return {"words": words}


@router.post("/safety/blocklist")
async def add_safety_word(body: SafetyWordCreate, user: Dict[str, Any] = Depends(require_admin)):
    word = body.word.strip().lower()
    if not word:
        return {"ok": False, "detail": "empty word"}
    await db.safety_blocklist.update_one(
        {"word": word},
        {"$setOnInsert": {"word": word, "created_at": now_iso(), "created_by": user["email"]}},
        upsert=True,
    )
    words = await refresh_safety_cache()
    return {"ok": True, "words": words}


@router.delete("/safety/blocklist/{word}")
async def remove_safety_word(word: str, user: Dict[str, Any] = Depends(require_admin)):
    await db.safety_blocklist.delete_one({"word": word.lower()})
    words = await refresh_safety_cache()
    return {"ok": True, "words": words}
