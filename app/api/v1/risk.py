"""
/api/v1/risk — risk scoring endpoints.
"""
from __future__ import annotations

from typing import List

from fastapi import APIRouter
from pydantic import BaseModel

from app.core.analyzer.risk_engine import RiskScoreResult, calculate_risk_score
from app.core.scanner.base_scanner import Finding

router = APIRouter(prefix="/risk", tags=["risk"])


class FindingIn(BaseModel):
    tool: str = "slither"
    check: str
    severity: str
    confidence: str = "medium"
    file_path: str = ""
    line_start: int = 0


class RiskScoreRequest(BaseModel):
    findings: List[FindingIn]
    is_proxy: bool = False
    has_mint: bool = False
    has_ownership: bool = False


class RiskScoreOut(BaseModel):
    score: float
    level: str
    breakdown: dict


@router.post(
    "/score",
    response_model=RiskScoreOut,
    summary="Calculate a risk score from a list of findings",
)
async def risk_score(body: RiskScoreRequest) -> RiskScoreOut:
    """
    Given a list of vulnerability findings and contract profile flags,
    return a normalised risk score (0-100) with severity breakdown.
    """
    findings = [
        Finding(
            tool=f.tool,
            check=f.check,
            title=f.check.replace("-", " ").title(),
            severity=f.severity,
            confidence=f.confidence,
            file_path=f.file_path or None,
            line_start=f.line_start or None,
        )
        for f in body.findings
    ]

    result: RiskScoreResult = calculate_risk_score(
        findings,
        is_proxy=body.is_proxy,
        has_mint=body.has_mint,
        has_ownership=body.has_ownership,
    )

    return RiskScoreOut(
        score=result.score,
        level=result.level.value,
        breakdown=result.breakdown,
    )
