"""General helper utilities."""
from __future__ import annotations

import re
from typing import Any


def is_valid_eth_address(address: str) -> bool:
    """Return True if *address* looks like a valid Ethereum address."""
    return bool(re.fullmatch(r"0x[0-9a-fA-F]{40}", address))


def flatten_dict(d: dict, parent_key: str = "", sep: str = ".") -> dict[str, Any]:
    """Recursively flatten a nested dictionary."""
    items: list = []
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict):
            items.extend(flatten_dict(v, new_key, sep=sep).items())
        else:
            items.append((new_key, v))
    return dict(items)


def truncate(text: str, max_len: int = 200) -> str:
    """Truncate *text* to *max_len* characters."""
    return text if len(text) <= max_len else text[:max_len] + "…"
