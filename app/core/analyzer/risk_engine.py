"""
Risk scoring engine.

Assigns a normalised 0-100 risk score based on:
- Severity × frequency of vulnerability findings
- AI confidence boosting
- Contract profile flags (proxy, minting, etc.)
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from app.core.scanner.base_scanner import Finding
from app.models.contract import RiskLevel

# Base scores per severity level
_SEVERITY_WEIGHTS = {
    "high": 25.0,
    "medium": 10.0,
    "low": 3.0,
    "informational": 0.5,
}

# Profile flag penalties
_FLAG_PENALTIES = {
    "is_proxy": 5.0,
    "has_mint": 8.0,
    "has_ownership": 4.0,
}


@dataclass
class RiskScoreResult:
    score: float                   # 0-100
    level: RiskLevel
    breakdown: dict


def calculate_risk_score(
    findings: List[Finding],
    is_proxy: bool = False,
    has_mint: bool = False,
    has_ownership: bool = False,
    ai_boosts: Optional[List[float]] = None,
) -> RiskScoreResult:
    """
    Compute a dynamic risk score from scan findings and contract profile flags.

    The algorithm:
    1. Sum weighted severity scores with diminishing returns (sqrt dampening)
    2. Apply profile-flag penalties
    3. Boost by average AI confidence when available
    4. Clamp to [0, 100]
    """
    import math

    severity_counts: dict = {k: 0 for k in _SEVERITY_WEIGHTS}
    raw_score = 0.0

    for f in findings:
        sev = f.severity.lower() if f.severity else "informational"
        weight = _SEVERITY_WEIGHTS.get(sev, 0.5)
        severity_counts[sev] = severity_counts.get(sev, 0) + 1
        # Diminishing returns: each extra finding of the same severity adds less
        count = severity_counts[sev]
        raw_score += weight * (1 / math.sqrt(count))

    # Profile penalties
    flag_penalty = 0.0
    if is_proxy:
        flag_penalty += _FLAG_PENALTIES["is_proxy"]
    if has_mint:
        flag_penalty += _FLAG_PENALTIES["has_mint"]
    if has_ownership:
        flag_penalty += _FLAG_PENALTIES["has_ownership"]

    score = raw_score + flag_penalty

    # AI confidence boost: average AI confidence scaled to max +10 points
    if ai_boosts:
        avg_boost = sum(ai_boosts) / len(ai_boosts)
        score += avg_boost * 10.0

    score = min(score, 100.0)

    breakdown = {
        "severity_counts": severity_counts,
        "raw_severity_score": round(raw_score, 2),
        "flag_penalty": round(flag_penalty, 2),
        "ai_boost": round((sum(ai_boosts) / len(ai_boosts) * 10) if ai_boosts else 0, 2),
        "final_score": round(score, 2),
    }

    return RiskScoreResult(
        score=round(score, 2),
        level=_score_to_level(score),
        breakdown=breakdown,
    )


def _score_to_level(score: float) -> RiskLevel:
    if score >= 70:
        return RiskLevel.CRITICAL
    if score >= 40:
        return RiskLevel.HIGH
    if score >= 15:
        return RiskLevel.MEDIUM
    return RiskLevel.LOW
