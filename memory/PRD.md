# PMOS • WMEU — Meme Civilization Engine — PRD

## Original Problem Statement
Build a full-stack app PMOS • WMEU — Meme Civilization Engine with a 15-engine PMOS pipeline (Blueprint, Biological, Energy, Artifact, Species, Plant, Faction, Lore, MemeBinding, MemeCoinBinder, NFTMint, Economic, Governance, CanonVaultConnector, ChartEngine), runPMOS master workflow, debugPMOS, updateEngineStatus, logSystemEvent, DB tables (MemeAsset/Blueprint/CanonVault/Proposal/Vote/CanonCertificate/ConstitutionAmendment/EngineStatus/SystemEvent), screens (Dashboard, Meme Asset Viewer, Canon Vault Browser, Governance, Rarity Calculator, Economic Simulator, Chart Viewer, Control Deck, Debug Dashboard), legal docs protecting Patrick Buckley © 2026. Dark cosmic-tech UI.

## User choices (locked in)
- 15 engines: deterministic seeded procedural generation; per-engine AI Enrich toggle stub for future
- NFT Mint: simulated (`is_simulated=true`, mock chain_hash) with `chain_adapter` field for future real chain
- Auth: hybrid — generation open, governance/economics writes require JWT login; admin = Patrick Buckley
- Branding: © Patrick Buckley 2026; P.BUCK™ · PMOS™ · WMEU™ · Waboot Meme Engine Universe™; Buckley Labs LLC (pending)
- Palette: deep space indigo + neon cyan/magenta; fonts Rajdhani (display) + JetBrains Mono (body)

## User personas
- **Patrick (admin/owner)** — runs PMOS, approves canon, ratifies amendments, oversees engines.
- **Operator (member)** — registers, creates governance proposals, votes.
- **Visitor** — runs generation engines, browses canon, uses calculators, reads docs/legal.

## Architecture
- FastAPI (`/app/backend/server.py`) with all routes prefixed `/api`
- MongoDB collections: `users`, `meme_assets`, `blueprints`, `canon_vault`, `canon_certificates`, `proposals`, `votes`, `constitution_amendments`, `engine_status`, `system_events`
- JWT (HS256, Bearer) — admin seeded on startup from `.env` (`ADMIN_EMAIL`/`ADMIN_PASSWORD`/`JWT_SECRET`)
- React 19 + Tailwind + Recharts + shadcn primitives + lucide-react + sonner toasts
- Hot-reloaded by supervisor; backend on 0.0.0.0:8001, frontend on 3000

## What's implemented (2026-06)
- 15 deterministic seeded engines (`engine_*` functions) + `run_single_engine` workflow logging status + events
- `runPMOS` (POST /api/pmos/run), `debugPMOS` (POST /api/pmos/debug), `updateEngineStatus` (helper + POST endpoint), `logSystemEvent` (helper + POST endpoint)
- Canon approval flow (admin) → CanonVault entry + CanonCertificate + ×1.5 rarity bonus
- Governance proposals + votes + amendments
- Rarity Calculator, Economic Simulator, three Chart endpoints
- Docs endpoint (`/api/docs/all`) returning Constitution, Rarity Formula, Engine Order, Canon Process, Debug Checklist, Amendment Log, and the full Legal pack (Copyright, Trademark, License, To-Whom-It-May-Concern, Universal Hub Clause)
- Frontend screens: Dashboard, Meme Asset Viewer, Canon Vault Browser, Governance Panel, Rarity Calculator, Economic Simulator, Chart Viewer, Control Deck (4 panels), Debug Dashboard, Login, Legal & Docs
- Tested end-to-end via testing subagent — 18/18 backend, 12/12 critical UI journeys

## Prioritized backlog
- **P1** — Wire AI-Enrich toggle to a real Claude/GPT call that only enriches `Lore.summary` & `Artifact.name` text fields (kept deterministic core)
- **P1** — Real on-chain NFT adapter (Solana/Polygon) behind the existing `chain_adapter` field
- **P2** — Marketplace for canon Meme Assets with shareable public permalinks
- **P2** — Webhook system for engine_error events (Discord/Slack)
- **P2** — Per-engine versioning + migration runner
- **P3** — Server-Sent Events stream from `/pmos/run` for live engine-by-engine progress (replace polling)
- **P3** — Split server.py into routers (auth/pmos/governance/canon/docs)
