# PMOS • WMEU v2.0 — Meme Civilization Engine (Universe-Class Edition)

## Original Problem Statement (v2)
26-engine PMOS pipeline + 4-layer storage (Mongo + Emergent Object Storage + backend-served public canon pages with OG meta + simulated chain adapter) + SSE live ticks + webhooks + marketplace + safety + governance + full legal pack protecting Patrick Buckley © 2026 (P.BUCK™ · PMOS™ · WMEU™ · Waboot Meme Engine Universe™ · Buckley Labs LLC pending). Universe-class platform within ~20 build credits.

## User choices (locked in v2)
- All engines deterministic seeded; AI Enrich toggle flag (no-op stub for future LLM lore enrichment)
- Layer 2: Emergent object storage with local fallback at /app/backend/_canon_local
- Layer 3: backend-served public canon HTML at /api/canon/{id}/page + Pillow-rendered OG PNG at /api/public/og/{id}.png
- Layer 4: chain_adapter.simulate_mint (simulated EVM); pluggable Solana/Polygon/Base later
- OG images: Pillow neon cosmic card (1200×630)
- Webhook engine: config-only; admin pastes Discord/Slack URL into Control Deck → WebhookManager
- SSE: real GET /api/pmos/run/stream?seed=… replacing dashboard polling
- Auth: hybrid (open generation, JWT for governance/marketplace writes, admin for canon approval / amendments / webhooks)

## Architecture
- FastAPI (`/app/backend/server.py` + helpers: canon_storage.py, og_image.py, chain_adapter.py, webhook.py); all routes under /api
- Mongo collections: users, meme_assets, blueprints, canon_vault, canon_certificates, proposals, votes, constitution_amendments, engine_status, system_events, marketplace_listings, public_canon_pages, identity_registry, webhook_configs
- JWT (HS256 Bearer) — admin seeded from .env on startup
- React 19 + Tailwind + Recharts + lucide-react + sonner + EventSource for SSE
- Cosmic-tech UI: Rajdhani (display) + JetBrains Mono (body); deep space indigo + neon cyan/magenta

## 26-engine pipeline order
1. Blueprint 2. Biological 3. Energy 4. Artifact 5. Species 6. Plant 7. Faction 8. Lore
9. Identity 10. Continuity 11. Influence 12. SocialGraph 13. UniverseTime 14. Safety 15. RateLimit
16. MemeBinding 17. MemeCoinBinder 18. NFTMint 19. Economic 20. Marketplace 21. Governance
22. CanonVaultConnector 23. PublicCanonPage 24. Webhook 25. ChartEngine 26. SSELiveTick

## What's implemented (v2.0 — 2026-06)
- 26 deterministic engines; runPMOS, runPMOS/stream (SSE), debugPMOS, updateEngineStatus, logSystemEvent
- Canon flow: admin approve enforces Safety engine; on success writes vault entry, certificate, public_canon_pages doc, Layer-2 snapshot, Layer-2 OG image, fires canon_approved webhook
- Public canon: /api/canon/{id}/page (HTML with og:image/title/url + twitter:card), /api/public/og/{id}.png, /api/public/canon/{id}.json
- Marketplace: canon-only + Safety-checked listings, create/delete, admin or member-as-seller
- Governance: proposals + votes + amendments
- Webhook fan-out: per-event-type (engine_error, canon_approved, engine_run, ...); admin manages via Control Deck
- Frontend (12 screens): Dashboard (SSE), Asset Viewer, Canon Vault, Marketplace, Governance, Rarity, Econ Sim, Charts, Control Deck (+ WebhookManager), Debug, Public Canon (/public/:id), Legal pack
- Legal pack: Copyright, Trademark, License, To-Whom-It-May-Concern, Universal Hub Clause — downloadable .txt
- 21/21 backend pytests pass; UI deltas all verified

## Prioritized backlog
- **P1** — Real LLM call from AI Enrich toggle (Claude/GPT) for Lore.summary + Artifact.name only
- **P1** — Real chain adapter (Solana/Polygon/Base) plugged into chain_adapter.simulate_mint
- **P2** — Move SAFETY_BLOCKLIST from hard-coded tuple to a Mongo config collection editable from Control Deck
- **P2** — Split server.py into routers/{pmos,canon,marketplace,webhooks,auth}.py (current ~1320 lines)
- **P2** — Auto-generated public canon thumbnails for the Marketplace grid (reuse OG PNG)
- **P3** — Remove legacy /canon/{id} top-level alias once external testers no longer reference it
- **P3** — Wrap render_og with placeholder fallback for missing font cases
- **P3** — Constitution amendment versioning UI with full diff view
