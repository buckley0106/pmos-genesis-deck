"""PMOS • WMEU v2.0 — slim FastAPI app (routers live in /app/backend/routers/).

Startup responsibilities: env loading, indexes, admin seed, engine-status seed,
safety blocklist seed + cache warm, object-storage init.

© 2026 Patrick Buckley — All rights reserved.
"""
from dotenv import load_dotenv
from pathlib import Path

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

import logging  # noqa: E402
import os  # noqa: E402

from fastapi import FastAPI  # noqa: E402
from starlette.middleware.cors import CORSMiddleware  # noqa: E402

from canon_storage import init_storage  # noqa: E402
from deps import (  # noqa: E402
    ENGINE_VERSION, db, hash_password, mongo_client, now_iso, refresh_safety_cache,
    seed_safety_defaults, verify_password,
)
from engines import ENGINE_ORDER  # noqa: E402
from routers import auth as auth_router  # noqa: E402
from routers import canon as canon_router  # noqa: E402
from routers import marketplace as marketplace_router  # noqa: E402
from routers import misc as misc_router  # noqa: E402
from routers import pmos as pmos_router  # noqa: E402
from routers import webhooks as webhooks_router  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("pmos")

app = FastAPI(title="PMOS • WMEU API", version="2.0.0")

app.include_router(auth_router.router)
app.include_router(pmos_router.router)
app.include_router(canon_router.router)
app.include_router(marketplace_router.router)
app.include_router(webhooks_router.router)
app.include_router(misc_router.router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)


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
        await db.safety_blocklist.create_index("word", unique=True)
    except Exception as exc:
        logger.warning(f"index init: {exc}")

    admin_email = os.environ["ADMIN_EMAIL"].lower()
    admin_pw = os.environ["ADMIN_PASSWORD"]
    existing = await db.users.find_one({"email": admin_email})
    if not existing:
        await db.users.insert_one({
            "email": admin_email, "name": "Patrick Buckley",
            "password_hash": hash_password(admin_pw), "role": "admin", "created_at": now_iso(),
        })
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
        await seed_safety_defaults()
        words = await refresh_safety_cache()
        logger.info(f"safety blocklist loaded ({len(words)} words)")
    except Exception as exc:
        logger.warning(f"safety init: {exc}")

    try:
        init_storage()
    except Exception as exc:
        logger.warning(f"storage startup: {exc}")


@app.on_event("shutdown")
async def on_shutdown():
    mongo_client.close()
