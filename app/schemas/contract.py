"""Pydantic schemas for contract scanning requests/responses."""
from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


class ScanRequest(BaseModel):
    """Request body for a new contract scan."""

    source_code: Optional[str] = Field(
        None, description="Raw Solidity source code to analyse"
    )
    address: Optional[str] = Field(
        None, description="Deployed contract address (0x…) to fetch & analyse"
    )
    compiler_version: Optional[str] = Field(
        None,
        description="Solidity compiler version",
        json_schema_extra={"example": "0.8.19"},
    )
    enable_mythril: bool = Field(
        False, description="Also run Mythril (slower but deeper symbolic execution)"
    )
    chain: str = Field(
        "ethereum",
        description="Target blockchain network",
        json_schema_extra={"example": "ethereum", "enum": ["ethereum", "bsc", "polygon", "arbitrum"]},
    )

    @field_validator("address")
    @classmethod
    def validate_address(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not v.startswith("0x"):
            raise ValueError("address must start with 0x")
        return v

    @field_validator("chain")
    @classmethod
    def validate_chain(cls, v: str) -> str:
        allowed = {"ethereum", "bsc", "polygon", "arbitrum"}
        if v not in allowed:
            raise ValueError(f"chain must be one of: {sorted(allowed)}")
        return v


class VulnerabilityOut(BaseModel):
    """Single vulnerability finding."""

    tool: str
    check: str
    title: str
    description: Optional[str] = None
    severity: str
    confidence: Optional[str] = None
    file_path: Optional[str] = None
    line_start: Optional[int] = None
    line_end: Optional[int] = None
    ai_category: Optional[str] = None
    ai_confidence: Optional[float] = None
    explanation: Optional[str] = None

    model_config = {"from_attributes": True}


class ContractProfileOut(BaseModel):
    """Contract capability profile."""

    is_proxy: bool
    has_mint: bool
    has_ownership: bool
    creator_address: Optional[str] = None


class ScanResponse(BaseModel):
    """Full scan response returned to the caller."""

    contract_id: int
    address: Optional[str] = None
    name: Optional[str] = None
    risk_score: float
    risk_level: str
    vulnerability_count: int
    vulnerabilities: List[VulnerabilityOut]
    profile: ContractProfileOut
    scan_status: str

    model_config = {"from_attributes": True}
