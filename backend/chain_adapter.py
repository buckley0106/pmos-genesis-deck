"""Simulated chain adapter — swap real Solana/Polygon/Base later.
All real chains plug in by implementing simulate_mint -> {token_id, chain_hash, chain}.
"""
import hashlib
import os
from typing import Dict


def simulate_mint(asset_id: str, chain: str = "simulated-evm") -> Dict[str, object]:
    token_id = int(hashlib.sha256(f"mint::{asset_id}".encode()).hexdigest()[:10], 16) % 999_999_999
    chain_hash = "0x" + hashlib.sha256(f"chain::{asset_id}::{chain}".encode()).hexdigest()
    return {
        "token_id": token_id,
        "chain_hash": chain_hash,
        "chain": chain,
        "metadata_uri": f"wmeu://meta/{token_id}",
        "is_simulated": True,
    }


def store_chain_hash(asset_id: str, chain_hash: str) -> Dict[str, str]:
    # Anchor record only — real implementation would broadcast a tx
    return {"asset_id": asset_id, "chain_hash": chain_hash, "anchored": "true"}
