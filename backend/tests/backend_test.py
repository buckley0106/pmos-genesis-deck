"""PMOS • WMEU backend test suite.

Covers: health, runPMOS, debugPMOS, engine-status, system-events, meme-assets,
auth (admin login, register, /me), governance (proposals + votes), canon
(approve, vault, certificate), rarity, economic, charts, docs.
"""
import os
import time
import uuid

import pytest
import requests

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") if os.environ.get("REACT_APP_BACKEND_URL") else None
if not BASE_URL:
    # frontend/.env
    from pathlib import Path
    for line in Path("/app/frontend/.env").read_text().splitlines():
        if line.startswith("REACT_APP_BACKEND_URL="):
            BASE_URL = line.split("=", 1)[1].strip().rstrip("/")
            break

API = f"{BASE_URL}/api"
ADMIN_EMAIL = "patrick@buckleylabs.io"
ADMIN_PASSWORD = "WMEU-2026-Admin!"

ENGINES = [
    "Blueprint", "Biological", "Energy", "Artifact", "Species", "Plant",
    "Faction", "Lore", "MemeBinding", "MemeCoinBinder", "NFTMint",
    "Economic", "Governance", "CanonVaultConnector", "ChartEngine",
]


# --- fixtures ---------------------------------------------------------------
@pytest.fixture(scope="session")
def s():
    return requests.Session()


@pytest.fixture(scope="session")
def admin_token(s):
    r = s.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=30)
    assert r.status_code == 200, f"admin login failed: {r.status_code} {r.text}"
    return r.json()["token"]


@pytest.fixture(scope="session")
def member_token(s):
    # register a fresh member
    email = f"TEST_member_{uuid.uuid4().hex[:8]}@wmeu.io"
    pw = "Tester-2026!"
    r = s.post(f"{API}/auth/register", json={"email": email, "password": pw, "name": "Tester"}, timeout=30)
    assert r.status_code == 200, f"register failed: {r.status_code} {r.text}"
    return r.json()["token"]


@pytest.fixture(scope="session")
def first_asset_id(s):
    r = s.post(f"{API}/pmos/run", json={"seed": "TEST_FIXTURE_SEED"}, timeout=60)
    assert r.status_code == 200
    return r.json()["id"]


# --- health & engines list --------------------------------------------------
def test_root_engines_list(s):
    r = s.get(f"{API}/", timeout=15)
    assert r.status_code == 200
    data = r.json()
    assert data["name"] == "PMOS • WMEU API"
    assert isinstance(data["engines"], list)
    assert len(data["engines"]) == 15
    assert data["engines"] == ENGINES


# --- runPMOS ---------------------------------------------------------------
def test_pmos_run_full_pipeline(s):
    r = s.post(f"{API}/pmos/run", json={"seed": "XYZ"}, timeout=60)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["canon_approved"] is False
    assert data["errors"] == []
    for name in ENGINES:
        assert name in data["engines"], f"missing engine {name}"
        assert data["engines"][name]["engine"] == name
    rarity = data["rarity"]
    assert "score" in rarity and "tier" in rarity and "breakdown" in rarity
    assert isinstance(rarity["score"], int)


def test_engine_status_after_run(s):
    # ensure prior run completed
    s.post(f"{API}/pmos/run", json={"seed": "STATUS_SEED"}, timeout=60)
    r = s.get(f"{API}/pmos/engine-status", timeout=15)
    assert r.status_code == 200
    docs = r.json()
    assert len(docs) == 15
    names = {d["engine_name"] for d in docs}
    assert names == set(ENGINES)
    for d in docs:
        assert d["status"] == "success", f"{d['engine_name']} not success: {d}"


def test_system_events_engine_run(s):
    r = s.get(f"{API}/pmos/system-events", timeout=15)
    assert r.status_code == 200
    events = r.json()
    assert any(e["type"] == "engine_run" for e in events)


# --- debugPMOS --------------------------------------------------------------
def test_debug_all_engines(s):
    r = s.post(f"{API}/pmos/debug", json={"seed": "D"}, timeout=30)
    assert r.status_code == 200
    data = r.json()
    assert len(data["report"]) == 15
    for entry in data["report"]:
        assert entry["ok"] is True, entry


def test_debug_single_engine(s):
    r = s.post(f"{API}/pmos/debug", json={"seed": "D", "engine": "Lore"}, timeout=15)
    assert r.status_code == 200
    rep = r.json()["report"]
    assert len(rep) == 1
    assert rep[0]["engine"] == "Lore" and rep[0]["ok"] is True


# --- meme assets ------------------------------------------------------------
def test_list_meme_assets(s, first_asset_id):
    r = s.get(f"{API}/meme-assets", timeout=15)
    assert r.status_code == 200
    ids = [a["id"] for a in r.json()]
    assert first_asset_id in ids


def test_get_meme_asset(s, first_asset_id):
    r = s.get(f"{API}/meme-assets/{first_asset_id}", timeout=15)
    assert r.status_code == 200
    data = r.json()
    assert data["id"] == first_asset_id
    assert len(data["engines"]) == 15


# --- auth -------------------------------------------------------------------
def test_admin_login_and_me(s, admin_token):
    r = s.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {admin_token}"}, timeout=15)
    assert r.status_code == 200
    me = r.json()
    assert me["email"] == ADMIN_EMAIL
    assert me["role"] == "admin"


def test_member_register_and_login(s):
    email = f"test_reg_{uuid.uuid4().hex[:8]}@wmeu.io"
    pw = "Tester-2026!"
    r = s.post(f"{API}/auth/register", json={"email": email, "password": pw}, timeout=15)
    assert r.status_code == 200
    assert r.json()["user"]["role"] == "member"
    # login
    r2 = s.post(f"{API}/auth/login", json={"email": email, "password": pw}, timeout=15)
    assert r2.status_code == 200
    assert r2.json()["user"]["email"] == email


# --- governance -------------------------------------------------------------
def test_proposal_requires_auth(s):
    r = s.post(f"{API}/governance/proposals", json={"title": "t", "description": "d"}, timeout=15)
    assert r.status_code == 401


def test_governance_proposal_and_vote(s, member_token):
    h = {"Authorization": f"Bearer {member_token}"}
    r = s.post(f"{API}/governance/proposals", json={"title": "TEST_prop", "description": "desc"}, headers=h, timeout=15)
    assert r.status_code == 200
    pid = r.json()["id"]
    # vote yes
    r2 = s.post(f"{API}/governance/vote", json={"proposal_id": pid, "choice": "yes"}, headers=h, timeout=15)
    assert r2.status_code == 200
    # update vote to no
    r3 = s.post(f"{API}/governance/vote", json={"proposal_id": pid, "choice": "no"}, headers=h, timeout=15)
    assert r3.status_code == 200
    # tally
    r4 = s.get(f"{API}/governance/proposals", timeout=15)
    assert r4.status_code == 200
    found = next((p for p in r4.json() if p["id"] == pid), None)
    assert found is not None
    assert found["tally"]["no"] == 1
    assert found["tally"]["yes"] == 0
    assert found["tally"]["total"] == 1


# --- canon ------------------------------------------------------------------
def test_approve_canon_admin(s, admin_token):
    # create new asset
    r = s.post(f"{API}/pmos/run", json={"seed": "CANON_SEED"}, timeout=60)
    asset = r.json()
    aid = asset["id"]
    pre_score = asset["rarity"]["score"]

    h = {"Authorization": f"Bearer {admin_token}"}
    r2 = s.post(f"{API}/meme-assets/{aid}/approve", headers=h, timeout=15)
    assert r2.status_code == 200, r2.text
    data = r2.json()
    assert data["vault_entry"]["asset_id"] == aid
    assert data["certificate"]["asset_id"] == aid

    r3 = s.get(f"{API}/meme-assets/{aid}", timeout=15)
    asset2 = r3.json()
    assert asset2["canon_approved"] is True
    # rarity ×1.5
    if pre_score > 0:
        assert asset2["rarity"]["score"] == int(pre_score * 1.5)

    # canon vault list
    r4 = s.get(f"{API}/canon-vault", timeout=15)
    assert any(v["asset_id"] == aid for v in r4.json())

    # certificate
    r5 = s.get(f"{API}/canon-vault/{aid}/certificate", timeout=15)
    assert r5.status_code == 200
    assert r5.json()["asset_id"] == aid


def test_approve_canon_non_admin(s, member_token):
    r = s.post(f"{API}/pmos/run", json={"seed": "NON_ADMIN_SEED"}, timeout=60)
    aid = r.json()["id"]
    h = {"Authorization": f"Bearer {member_token}"}
    r2 = s.post(f"{API}/meme-assets/{aid}/approve", headers=h, timeout=15)
    assert r2.status_code == 403


# --- rarity / economic / charts --------------------------------------------
def test_rarity_calculate(s):
    r = s.post(f"{API}/rarity/calculate", json={
        "trait_count": 8, "legendary_traits": 1, "rare_traits": 2,
        "uncommon_traits": 3, "common_traits": 2, "canon_status": False
    }, timeout=15)
    assert r.status_code == 200
    data = r.json()
    assert "score" in data and "tier" in data and "formula" in data


def test_economic_simulate(s):
    r = s.post(f"{API}/economic/simulate", json={"horizon_months": 12}, timeout=15)
    assert r.status_code == 200
    rows = r.json()["rows"]
    assert len(rows) == 13
    for row in rows:
        assert {"month", "supply", "price_usd", "market_cap"} <= set(row.keys())


def test_charts(s):
    for ep in ["rarity-distribution", "faction-breakdown", "economic-curve"]:
        r = s.get(f"{API}/charts/{ep}", timeout=15)
        assert r.status_code == 200, ep
        assert isinstance(r.json(), list)


# --- docs -------------------------------------------------------------------
def test_docs_all(s):
    r = s.get(f"{API}/docs/all", timeout=15)
    assert r.status_code == 200
    d = r.json()
    for key in ["constitution", "rarity_formula", "engine_order", "canon_process", "debug_checklist", "legal"]:
        assert key in d, f"missing {key}"
    for k in ["copyright", "trademark", "license", "to_whom_it_may_concern", "universal_hub_clause"]:
        assert k in d["legal"], f"missing legal.{k}"
