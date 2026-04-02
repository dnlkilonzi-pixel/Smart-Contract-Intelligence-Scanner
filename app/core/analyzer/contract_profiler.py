"""
Contract profiler.

Analyses Solidity source code to extract capability flags:
- Proxy / upgradeability patterns
- Minting capability
- Ownership / access control patterns
"""
from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class ContractProfile:
    is_proxy: bool = False
    has_mint: bool = False
    has_ownership: bool = False
    has_selfdestruct: bool = False
    has_delegatecall: bool = False
    has_flash_loan: bool = False
    compiler_pragmas: list[str] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.compiler_pragmas is None:
            self.compiler_pragmas = []


# Regex patterns for capability detection
_PATTERNS = {
    "is_proxy": [
        r"\bdelegatecall\b",
        r"\bfallback\b.*\bdelegatecall\b",
        r"ERC1967Proxy|TransparentUpgradeableProxy|UUPSUpgradeable",
        r"_implementation\(\)",
    ],
    "has_mint": [
        r"\bmint\s*\(",
        r"\b_mint\s*\(",
        r"\bmintTo\s*\(",
        r"function\s+mint\b",
    ],
    "has_ownership": [
        r"\bOwnable\b",
        r"\bonlyOwner\b",
        r"\bowner\s*==\s*msg\.sender\b",
        r"AccessControl",
        r"Roles\.",
    ],
    "has_selfdestruct": [
        r"\bselfdestruct\b",
        r"\bsuicide\b",
    ],
    "has_delegatecall": [
        r"\.delegatecall\s*\(",
    ],
    "has_flash_loan": [
        r"flashLoan\b",
        r"flash_loan\b",
        r"IFlashLoan",
        r"onFlashLoan\b",
    ],
}


def profile_contract(source_code: str) -> ContractProfile:
    """
    Scan *source_code* for known capability patterns and return a ContractProfile.

    This is purely regex-based (fast); for deeper analysis Slither detectors
    already cover most cases.
    """
    profile = ContractProfile()

    # Extract pragma versions
    profile.compiler_pragmas = re.findall(r"pragma\s+solidity\s+([^;]+);", source_code)

    # Evaluate each capability flag
    for flag, patterns in _PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, source_code, re.IGNORECASE | re.MULTILINE):
                setattr(profile, flag, True)
                break

    return profile
