"""Pydantic request/response models."""
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6)
    name: Optional[str] = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RunPMOSRequest(BaseModel):
    seed: str = Field(min_length=1, max_length=200)
    enrich_ai: bool = False
    auto_approve: bool = False


class DebugPMOSRequest(BaseModel):
    engine: Optional[str] = None
    seed: str = "DEBUG-SEED"


class EngineStatusUpdate(BaseModel):
    engine_name: str
    status: str
    last_error: Optional[str] = None
    engine_version: str = "2.0.0"


class SystemEventCreate(BaseModel):
    type: str
    summary: str
    related_id: Optional[str] = None
    details: Optional[Dict[str, Any]] = None


class ProposalCreate(BaseModel):
    title: str
    description: str
    target_asset_id: Optional[str] = None
    proposal_type: str = "canon_approval"


class VoteCreate(BaseModel):
    proposal_id: str
    choice: str


class RarityInput(BaseModel):
    trait_count: int = 8
    legendary_traits: int = 1
    rare_traits: int = 2
    uncommon_traits: int = 3
    common_traits: int = 2
    canon_status: bool = False


class EconomicSimInput(BaseModel):
    initial_supply: float = 1_000_000.0
    mint_cost: float = 0.01
    demand_factor: float = 1.5
    burn_rate: float = 0.02
    horizon_months: int = 12


class MarketplaceListingCreate(BaseModel):
    asset_id: str
    price_usd: float
    description: Optional[str] = None


class WebhookConfigCreate(BaseModel):
    url: str = Field(min_length=8)
    label: str = "default"
    event_types: List[str] = Field(default_factory=lambda: ["engine_error", "canon_approved"])


class SafetyWordCreate(BaseModel):
    word: str = Field(min_length=1, max_length=64)
