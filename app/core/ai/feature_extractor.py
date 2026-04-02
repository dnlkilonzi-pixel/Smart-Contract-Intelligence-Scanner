"""
Feature extractor for AI vulnerability classification.

Converts a Finding into a numeric feature vector suitable for
scikit-learn classifiers.
"""
from __future__ import annotations

from typing import List

import numpy as np

from app.core.scanner.base_scanner import Finding

# One-hot encoding maps
_TOOL_MAP = {"slither": 0, "mythril": 1}
_SEVERITY_MAP = {"high": 3, "medium": 2, "low": 1, "informational": 0}
_CONFIDENCE_MAP = {"high": 2, "medium": 1, "low": 0, "unknown": 0}

# Top-N vulnerability check names (known at training time)
_KNOWN_CHECKS = [
    "reentrancy-eth",
    "reentrancy-no-eth",
    "reentrancy-benign",
    "integer-overflow",
    "suicidal",
    "arbitrary-send-eth",
    "arbitrary-send-erc20",
    "controlled-delegatecall",
    "unchecked-return-value",
    "locked-ether",
    "tx-origin",
    "SWC-107",
    "SWC-101",
    "SWC-105",
    "SWC-106",
    "SWC-115",
    "SWC-104",
]

FEATURE_DIM = 4 + len(_KNOWN_CHECKS)  # tool, severity, confidence, has_location + check one-hot


def extract_features(finding: Finding) -> np.ndarray:
    """
    Convert a Finding into a fixed-length feature vector.

    Features:
        [0] tool id (slither=0, mythril=1)
        [1] severity (0-3)
        [2] confidence (0-2)
        [3] has source location (0/1)
        [4:] one-hot encoding of check name
    """
    vec = np.zeros(FEATURE_DIM, dtype=np.float32)

    vec[0] = float(_TOOL_MAP.get(finding.tool, 0))
    vec[1] = float(_SEVERITY_MAP.get(finding.severity.lower() if finding.severity else "", 0))
    vec[2] = float(_CONFIDENCE_MAP.get(finding.confidence.lower() if finding.confidence else "", 0))
    vec[3] = 1.0 if finding.file_path else 0.0

    if finding.check in _KNOWN_CHECKS:
        idx = _KNOWN_CHECKS.index(finding.check)
        vec[4 + idx] = 1.0

    return vec


def extract_batch(findings: List[Finding]) -> np.ndarray:
    """Return a 2-D feature matrix for a list of findings."""
    if not findings:
        return np.empty((0, FEATURE_DIM), dtype=np.float32)
    return np.vstack([extract_features(f) for f in findings])
