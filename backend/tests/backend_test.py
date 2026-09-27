"""PMOS • WMEU v2.0 backend test suite (26 engines, marketplace, webhooks, canon public)."""
import os
import uuid

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL")
if not BASE_URL:
    from pathlib import Path
    for line in Path("/app/frontend/.env").read_text().splitlines():
        if line.startswith("REACT_APP_BACKEND_URL="):
            BASE_URL = line.split("=", 1)[1].strip()
            break
BASE_URL = BASE_URL.rstrip("/")
API = f"{BASE_URL}/api"
ADMIN_EMAIL = "patrick@buckleylabs.io"
ADMIN_PASSWORD = "WMEU-2026-Admin!"

ENGINES_V2 = [
    "Blueprint", "Biological", "Energy", "Artifact", "Species", "Plant", "Faction", "Lore",
    "Identity", "Continuity", "Influence", "SocialGraph", "UniverseTime", "Safety", "RateLimit",
    "MemeBinding", "MemeCoinBinder", "Governance", "Economic", "CanonVaultConnector",
    "PublicCanonPage", "NFTMint", "Marketplace", "Webhook", "ChartEngine", "SSELiveTick",
]


# --- fixtures ---------------------------------------------------------------
@pytest.fixture(scope="session")
def s():
    return requests.Session()


@pytest.fixture(scope="session")
def admin_token(s):
    r = s.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=30)
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="session")
def member_token(s):
    email = f"TEST_member_{uuid.uuid4().hex[:8]}@wmeu.io"
    r = s.post(f"{API}/auth/register", json={"email": email, "password": "Tester-2026!", "name": "Tester"}, timeout=30)
    assert r.status_code == 200, r.text
    return r.json()["token"]


# --- v2 root + engine list --------------------------------------------------
def test_root_v2(s):
    r = s.get(f"{API}/", timeout=15)
    assert r.status_code == 200
    d = r.json()
    assert d["version"] == "2.0.0"
    assert d["engine_count"] == 26
    assert d["engines"] == ENGINES_V2


# --- runPMOS 26 engines -----------------------------------------------------
def test_pmos_run_26_engines(s):
    r = s.post(f"{API}/pmos/run", json={"seed": "TEST_V2_XYZ"}, timeout=90)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["canon_approved"] is False
    assert d["errors"] == []
    for name in ENGINES_V2:
        assert name in d["engines"], f"missing {name}"
        assert d["engines"][name]["engine"] == name
    # token_id + chain_hash populated by NFTMint simulate
    assert d.get("token_id")
    assert d.get("chain_hash")
    nft = d["engines"]["NFTMint"]
    assert nft.get("is_simulated") is True


def test_debug_all_26(s):
    r = s.post(f"{API}/pmos/debug", json={"seed": "TEST_D"}, timeout=60)
    assert r.status_code == 200
    rep = r.json()["report"]
    assert len(rep) == 26
    for entry in rep:
        assert entry["ok"] is True, entry


# --- SSE stream -------------------------------------------------------------
def test_sse_stream(s):
    seed = f"TEST_SSE_{uuid.uuid4().hex[:6]}"
    with requests.get(f"{API}/pmos/run/stream", params={"seed": seed}, stream=True, timeout=120) as r:
        assert r.status_code == 200
        assert "text/event-stream" in r.headers.get("content-type", "")
        events = []
        body = b""
        for chunk in r.iter_content(chunk_size=512):
            if chunk:
                body += chunk
                if b"event: complete" in body:
                    break
        text = body.decode(errors="ignore")
        # parse named events
        event_names = [ln.split(":", 1)[1].strip() for ln in text.splitlines() if ln.startswith("event:")]
    assert "start" in event_names
    assert event_names.count("engine_start") == 26
    assert event_names.count("engine_done") == 26
    assert "complete" in event_names


# --- canon flow (auto_approve + public pages) ------------------------------
@pytest.fixture(scope="session")
def canon_asset_id(s):
    r = s.post(f"{API}/pmos/run", json={"seed": "TEST_CANON_AUTO", "auto_approve": True}, timeout=90)
    assert r.status_code == 200
    d = r.json()
    assert d["canon_approved"] is True
    return d["id"]


def test_canon_html_page(s, canon_asset_id):
    r = s.get(f"{API}/canon/{canon_asset_id}/page", timeout=30)
    assert r.status_code == 200
    assert "text/html" in r.headers.get("content-type", "")
    body = r.text
    assert 'property="og:image"' in body
    assert 'property="og:url"' in body
    assert 'property="og:title"' in body
    assert 'name="twitter:card"' in body
    assert f"/api/public/og/{canon_asset_id}.png" in body


def test_canon_og_png(s, canon_asset_id):
    r = s.get(f"{API}/public/og/{canon_asset_id}.png", timeout=30)
    assert r.status_code == 200
    assert r.headers.get("content-type") == "image/png"
    assert len(r.content) > 1000
    assert r.content[:8] == b"\x89PNG\r\n\x1a\n"


def test_canon_public_json(s, canon_asset_id):
    r = s.get(f"{API}/public/canon/{canon_asset_id}.json", timeout=15)
    assert r.status_code == 200
    assert r.json()["canon_approved"] is True


def test_public_canon_json_404_for_non_canon(s):
    r = s.post(f"{API}/pmos/run", json={"seed": "TEST_NOTCANON"}, timeout=90)
    aid = r.json()["id"]
    r2 = s.get(f"{API}/public/canon/{aid}.json", timeout=15)
    assert r2.status_code == 404


def test_canon_html_403_for_non_canon(s):
    r = s.post(f"{API}/pmos/run", json={"seed": "TEST_NOTCANON2"}, timeout=90)
    aid = r.json()["id"]
    r2 = s.get(f"{API}/canon/{aid}/page", timeout=15)
    assert r2.status_code == 403


def test_canon_html_404_for_unknown(s):
    r = s.get(f"{API}/canon/nonexistent-asset-xyz/page", timeout=15)
    assert r.status_code == 404


# --- approve via admin api -------------------------------------------------
def test_admin_approve(s, admin_token):
    r = s.post(f"{API}/pmos/run", json={"seed": "TEST_ADMIN_APPROVE"}, timeout=90)
    aid = r.json()["id"]
    h = {"Authorization": f"Bearer {admin_token}"}
    r2 = s.post(f"{API}/meme-assets/{aid}/approve", headers=h, timeout=30)
    assert r2.status_code == 200, r2.text
    d = r2.json()
    assert d["vault_entry"]["asset_id"] == aid
    assert d["certificate"]["asset_id"] == aid
    assert d["public"]["asset_id"] == aid
    assert "artifacts" in d


def test_member_cannot_approve(s, member_token):
    r = s.post(f"{API}/pmos/run", json={"seed": "TEST_MEMBER_DENY"}, timeout=90)
    aid = r.json()["id"]
    h = {"Authorization": f"Bearer {member_token}"}
    r2 = s.post(f"{API}/meme-assets/{aid}/approve", headers=h, timeout=15)
    assert r2.status_code == 403


# --- marketplace -----------------------------------------------------------
def test_marketplace_open_get(s):
    r = s.get(f"{API}/marketplace", timeout=15)
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_marketplace_post_requires_auth(s):
    r = s.post(f"{API}/marketplace", json={"asset_id": "x", "price_usd": 10}, timeout=15)
    assert r.status_code == 401


def test_marketplace_non_canon_rejected(s, member_token):
    r = s.post(f"{API}/pmos/run", json={"seed": "TEST_NOCANON_LIST"}, timeout=90)
    aid = r.json()["id"]
    h = {"Authorization": f"Bearer {member_token}"}
    r2 = s.post(f"{API}/marketplace", json={"asset_id": aid, "price_usd": 9.99}, headers=h, timeout=15)
    assert r2.status_code == 400


def test_marketplace_canon_list_ok(s, admin_token, canon_asset_id):
    h = {"Authorization": f"Bearer {admin_token}"}
    r = s.post(f"{API}/marketplace", json={"asset_id": canon_asset_id, "price_usd": 42.5, "description": "test"}, headers=h, timeout=15)
    assert r.status_code == 200, r.text
    listing = r.json()
    assert listing["asset_id"] == canon_asset_id
    assert listing["price_usd"] == 42.5
    # GET reflects
    r2 = s.get(f"{API}/marketplace", timeout=15)
    assert any(l["id"] == listing["id"] for l in r2.json())
    # DELETE works
    r3 = s.delete(f"{API}/marketplace/{listing['id']}", headers=h, timeout=15)
    assert r3.status_code == 200


def test_marketplace_delete_missing_404(s, admin_token):
    h = {"Authorization": f"Bearer {admin_token}"}
    r = s.delete(f"{API}/marketplace/nonexistent-xxx", headers=h, timeout=15)
    assert r.status_code == 404


# --- safety ----------------------------------------------------------------
def test_safety_blocks_approve(s, admin_token):
    # run with "kill" → safety flagged unsafe; admin approve must now be rejected 400
    r = s.post(f"{API}/pmos/run", json={"seed": "kill someone"}, timeout=90)
    assert r.status_code == 200
    aid = r.json()["id"]
    assert r.json()["engines"]["Safety"]["safe"] is False
    h = {"Authorization": f"Bearer {admin_token}"}
    rapp = s.post(f"{API}/meme-assets/{aid}/approve", headers=h, timeout=30)
    assert rapp.status_code == 400, rapp.text
    assert "Safety engine" in rapp.json().get("detail", "")
    assert "cannot canonize" in rapp.json().get("detail", "")


# --- webhooks (admin only) -------------------------------------------------
def test_webhooks_member_forbidden(s, member_token):
    h = {"Authorization": f"Bearer {member_token}"}
    r = s.get(f"{API}/webhooks", headers=h, timeout=15)
    assert r.status_code == 403


def test_webhooks_admin_crud(s, admin_token):
    h = {"Authorization": f"Bearer {admin_token}"}
    r = s.get(f"{API}/webhooks", headers=h, timeout=15)
    assert r.status_code == 200
    payload = {"url": "https://example.com/hook-test", "label": "TEST_hook", "event_types": ["engine_error"]}
    r2 = s.post(f"{API}/webhooks", json=payload, headers=h, timeout=15)
    assert r2.status_code == 200
    wid = r2.json()["id"]
    r3 = s.get(f"{API}/webhooks", headers=h, timeout=15)
    assert any(w["id"] == wid for w in r3.json())
    r4 = s.delete(f"{API}/webhooks/{wid}", headers=h, timeout=15)
    assert r4.status_code == 200


# --- engine order endpoint --------------------------------------------------
def test_engine_order_endpoint(s):
    r = s.get(f"{API}/pmos/engine-order", timeout=15)
    assert r.status_code == 200
    d = r.json()
    assert d["count"] == 26
    assert d["order"] == ENGINES_V2


# --- v2.0 regression: safety blocklist CRUD (admin-only) -------------------
def test_safety_blocklist_get_defaults(s, admin_token):
    h = {"Authorization": f"Bearer {admin_token}"}
    r = s.get(f"{API}/safety/blocklist", headers=h, timeout=15)
    assert r.status_code == 200, r.text
    d = r.json()
    assert "words" in d
    assert isinstance(d["words"], list)
    # sorted
    assert d["words"] == sorted(d["words"])
    # defaults present
    for w in ["kill", "csam", "exploit-violence"]:
        assert w in d["words"], f"default '{w}' missing"


def test_safety_blocklist_post_requires_admin(s, member_token):
    h = {"Authorization": f"Bearer {member_token}"}
    r = s.post(f"{API}/safety/blocklist", json={"word": "TEST_denied"}, headers=h, timeout=15)
    assert r.status_code in (401, 403)


def test_safety_blocklist_add_and_delete(s, admin_token):
    h = {"Authorization": f"Bearer {admin_token}"}
    word = f"testword{uuid.uuid4().hex[:6]}"
    # add
    r = s.post(f"{API}/safety/blocklist", json={"word": word}, headers=h, timeout=15)
    assert r.status_code == 200, r.text
    # idempotent
    r2 = s.post(f"{API}/safety/blocklist", json={"word": word}, headers=h, timeout=15)
    assert r2.status_code == 200
    # verify persisted
    rg = s.get(f"{API}/safety/blocklist", headers=h, timeout=15)
    assert word in rg.json()["words"]
    # delete
    rd = s.delete(f"{API}/safety/blocklist/{word}", headers=h, timeout=15)
    assert rd.status_code == 200
    rg2 = s.get(f"{API}/safety/blocklist", headers=h, timeout=15)
    assert word not in rg2.json()["words"]


def test_safety_blocklist_hot_reload(s, admin_token):
    """Adding a word should flag subsequent PMOS runs without restart."""
    h = {"Authorization": f"Bearer {admin_token}"}
    word = f"htw{uuid.uuid4().hex[:6]}"
    try:
        s.post(f"{API}/safety/blocklist", json={"word": word}, headers=h, timeout=15)
        r = s.post(f"{API}/pmos/run", json={"seed": f"benign seed with {word} inside"}, timeout=90)
        assert r.status_code == 200
        safety = r.json()["engines"]["Safety"]
        assert safety["safe"] is False, safety
        assert word in [f.lower() for f in safety.get("flags", [])], safety
    finally:
        s.delete(f"{API}/safety/blocklist/{word}", headers=h, timeout=15)


# --- v2.0 regression: marketplace og_url field -----------------------------
def test_marketplace_listing_has_og_url(s, admin_token, canon_asset_id):
    h = {"Authorization": f"Bearer {admin_token}"}
    r = s.post(f"{API}/marketplace", json={"asset_id": canon_asset_id, "price_usd": 12.34}, headers=h, timeout=15)
    assert r.status_code == 200, r.text
    listing = r.json()
    assert listing.get("og_url") == f"/api/public/og/{canon_asset_id}.png"
    # cleanup
    s.delete(f"{API}/marketplace/{listing['id']}", headers=h, timeout=15)


# --- v2.0 regression: legacy /canon/{id} removed from OpenAPI --------------
def test_openapi_no_legacy_canon_route(s):
    # openapi.json is not exposed via /api ingress; hit backend directly
    r = s.get("http://localhost:8001/openapi.json", timeout=15)
    assert r.status_code == 200
    paths = r.json().get("paths", {})
    # legacy top-level route must be gone
    assert "/canon/{asset_id}" not in paths
    # new prefixed route must exist
    assert "/api/canon/{asset_id}/page" in paths


# --- v2.0 regression: root endpoint edition --------------------------------
def test_root_edition(s):
    r = s.get(f"{API}/", timeout=15)
    d = r.json()
    assert d.get("edition") == "Universe-Class"

