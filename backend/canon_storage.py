"""Object storage adapter — Emergent S3-compatible with local-disk fallback.
Used as Layer 2 (immutable canon snapshots + OG images).
"""
from __future__ import annotations

import os
import logging
from pathlib import Path
from typing import Optional, Tuple

import requests

logger = logging.getLogger(__name__)

STORAGE_URL = "https://integrations.emergentagent.com/objstore/api/v1/storage"
APP_NAME = os.environ.get("PMOS_APP_NAME", "pmos-wmeu")
LOCAL_ROOT = Path("/app/backend/_canon_local")
LOCAL_ROOT.mkdir(parents=True, exist_ok=True)

_storage_key: Optional[str] = None
_remote_ok: bool = False


def init_storage() -> Optional[str]:
    """Idempotent storage init. Returns key on success or None on fallback."""
    global _storage_key, _remote_ok
    if _storage_key:
        return _storage_key
    key = os.environ.get("EMERGENT_LLM_KEY")
    if not key:
        logger.warning("EMERGENT_LLM_KEY missing — using local-disk canon fallback")
        return None
    try:
        resp = requests.post(f"{STORAGE_URL}/init", json={"emergent_key": key}, timeout=15)
        resp.raise_for_status()
        _storage_key = resp.json()["storage_key"]
        _remote_ok = True
        logger.info("Emergent object storage initialized")
        return _storage_key
    except Exception as exc:
        logger.warning(f"Storage init failed, using local fallback: {exc}")
        _remote_ok = False
        return None


def _prefix(path: str) -> str:
    return f"{APP_NAME}/{path.lstrip('/')}"


def put_object(path: str, data: bytes, content_type: str) -> dict:
    full = _prefix(path)
    init_storage()
    if _remote_ok and _storage_key:
        try:
            resp = requests.put(
                f"{STORAGE_URL}/objects/{full}",
                headers={"X-Storage-Key": _storage_key, "Content-Type": content_type},
                data=data,
                timeout=60,
            )
            resp.raise_for_status()
            return {**resp.json(), "backend": "emergent"}
        except Exception as exc:
            logger.warning(f"Remote put failed for {full}: {exc}; using local")
    # local
    target = LOCAL_ROOT / full
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    return {"path": full, "size": len(data), "etag": str(hash(data)), "backend": "local"}


def get_object(path: str) -> Tuple[bytes, str]:
    full = _prefix(path)
    init_storage()
    if _remote_ok and _storage_key:
        try:
            resp = requests.get(
                f"{STORAGE_URL}/objects/{full}", headers={"X-Storage-Key": _storage_key}, timeout=30
            )
            if resp.status_code == 200:
                return resp.content, resp.headers.get("Content-Type", "application/octet-stream")
        except Exception as exc:
            logger.debug(f"Remote get fallback: {exc}")
    target = LOCAL_ROOT / full
    if not target.exists():
        raise FileNotFoundError(full)
    ct = "application/json" if path.endswith(".json") else "image/png" if path.endswith(".png") else "application/octet-stream"
    return target.read_bytes(), ct


def save_canon_snapshot(asset_id: str, version: int, payload: dict) -> dict:
    import json
    return put_object(f"canon/{asset_id}/v{version}.json", json.dumps(payload, indent=2).encode(), "application/json")


def save_og_image(asset_id: str, png_bytes: bytes) -> dict:
    return put_object(f"canon/{asset_id}/og.png", png_bytes, "image/png")


def get_canon_snapshot(asset_id: str, version: int) -> dict:
    import json
    raw, _ = get_object(f"canon/{asset_id}/v{version}.json")
    return json.loads(raw)
