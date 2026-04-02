"""
Rug-pull pattern detector.

Uses heuristics and ML-ready feature extraction to classify wallets
and contracts as potential rug-pull suspects.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List

from app.core.intelligence.wallet_analyzer import WalletBehaviourReport

# Rug-pull heuristic thresholds
_THRESHOLDS = {
    "min_contracts_deployed": 2,
    "large_outflow_threshold": 5,
    "flash_loan_threshold": 3,
    "min_tx_for_analysis": 5,
}

# Score weights for each indicator
_WEIGHTS = {
    "deployed_multiple_contracts": 20,
    "large_outflows": 25,
    "flash_loans": 15,
    "self_transfers": 10,
    "low_activity_deployer": 15,
}


@dataclass
class RugPullAssessment:
    score: float            # 0-100
    is_suspect: bool
    indicators: List[str]
    explanation: str


def assess_rug_pull_risk(report: WalletBehaviourReport) -> RugPullAssessment:
    """
    Evaluate *report* for rug-pull behavioural patterns and return a scored assessment.

    The score is a weighted sum of heuristic indicators, clamped to [0, 100].
    """
    score = 0.0
    indicators: List[str] = list(report.risk_indicators)

    # --- Heuristic 1: deployed multiple contracts ---
    if len(report.deployed_contracts) >= _THRESHOLDS["min_contracts_deployed"]:
        score += _WEIGHTS["deployed_multiple_contracts"]
        indicators.append(f"Deployed {len(report.deployed_contracts)} contracts (suspicious pattern)")

    # --- Heuristic 2: many large outflows (funds draining) ---
    if report.large_outflows >= _THRESHOLDS["large_outflow_threshold"]:
        score += _WEIGHTS["large_outflows"]
        indicators.append(f"High number of large outflows: {report.large_outflows}")

    # --- Heuristic 3: flash loan activity ---
    if report.flash_loan_count >= _THRESHOLDS["flash_loan_threshold"]:
        score += _WEIGHTS["flash_loans"]
        indicators.append(f"Flash loan activity detected: {report.flash_loan_count} txs")

    # --- Heuristic 4: self-transfers (obfuscation attempt) ---
    if report.self_transfer_count >= 3:
        score += _WEIGHTS["self_transfers"]
        indicators.append("Multiple self-transfers detected (possible fund obfuscation)")

    # --- Heuristic 5: low activity deployer (deploy & dump) ---
    if (
        len(report.deployed_contracts) > 0
        and report.tx_count < _THRESHOLDS["min_tx_for_analysis"]
    ):
        score += _WEIGHTS["low_activity_deployer"]
        indicators.append("Low activity deployer: deployed contract with few other transactions")

    score = min(score, 100.0)
    is_suspect = score >= 40.0

    explanation = (
        f"Rug-pull risk score: {score:.1f}/100. "
        + ("Wallet flagged as potential rug-pull suspect." if is_suspect else "No strong rug-pull signals detected.")
    )

    return RugPullAssessment(
        score=round(score, 2),
        is_suspect=is_suspect,
        indicators=indicators,
        explanation=explanation,
    )
