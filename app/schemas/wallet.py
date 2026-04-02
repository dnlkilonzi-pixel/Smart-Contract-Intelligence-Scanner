"""Pydantic schemas for wallet intelligence."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class WalletIntelligenceOut(BaseModel):
    """Wallet intelligence report."""

    address: str
    tx_count: int
    eth_balance: Optional[float] = None
    first_seen_block: Optional[int] = None
    last_seen_block: Optional[int] = None

    is_contract_deployer: bool
    is_rug_pull_suspect: bool
    rugpull_score: Optional[float] = None
    flash_loan_count: int
    unique_contracts_interacted: int

    # Human-readable flags
    risk_indicators: List[str] = Field(default_factory=list)
    raw_intelligence: Optional[Dict[str, Any]] = None

    model_config = {"from_attributes": True}
