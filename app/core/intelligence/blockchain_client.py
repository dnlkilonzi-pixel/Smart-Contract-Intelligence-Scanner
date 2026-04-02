"""
Blockchain client — fetches on-chain data via Web3.py and block explorer APIs.

Supports Ethereum, BNB Smart Chain (BSC), Polygon, and Arbitrum.
Falls back gracefully when RPC or API keys are not configured.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

import httpx
import structlog
from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import get_settings

log = structlog.get_logger(__name__)
settings = get_settings()

# ---------------------------------------------------------------------------
# Chain registry — RPC URLs, explorer API bases, and API key settings
# ---------------------------------------------------------------------------

_CHAIN_CONFIG: Dict[str, Dict[str, Any]] = {
    "ethereum": {
        "explorer_base": "https://api.etherscan.io/api",
        "rpc_url": settings.eth_rpc_url,
        "api_key": settings.etherscan_api_key,
    },
    "bsc": {
        "explorer_base": "https://api.bscscan.com/api",
        "rpc_url": settings.bsc_rpc_url,
        "api_key": settings.bscscan_api_key,
    },
    "polygon": {
        "explorer_base": "https://api.polygonscan.com/api",
        "rpc_url": settings.polygon_rpc_url,
        "api_key": settings.polygonscan_api_key,
    },
    "arbitrum": {
        "explorer_base": "https://api.arbiscan.io/api",
        "rpc_url": settings.arbitrum_rpc_url,
        "api_key": settings.arbiscan_api_key,
    },
}

# Keep the old constant for backward-compatibility
ETHERSCAN_BASE = _CHAIN_CONFIG["ethereum"]["explorer_base"]


class BlockchainClient:
    """Async client for multi-chain on-chain data.

    Parameters
    ----------
    chain:
        Target chain name. One of: ``"ethereum"`` (default), ``"bsc"``,
        ``"polygon"``, ``"arbitrum"``.
    """

    SUPPORTED_CHAINS = list(_CHAIN_CONFIG.keys())

    def __init__(self, chain: str = "ethereum") -> None:
        if chain not in _CHAIN_CONFIG:
            raise ValueError(
                f"Unsupported chain {chain!r}. "
                f"Choose from: {self.SUPPORTED_CHAINS}"
            )
        self._chain = chain
        self._cfg = _CHAIN_CONFIG[chain]
        self._explorer_base: str = self._cfg["explorer_base"]
        self._api_key: Optional[str] = self._cfg.get("api_key")
        self._http = httpx.AsyncClient(timeout=30)

    # ------------------------------------------------------------------
    # Contract data
    # ------------------------------------------------------------------

    async def get_contract_source(self, address: str) -> Optional[str]:
        """Fetch verified source code from the block explorer."""
        params = {
            "module": "contract",
            "action": "getsourcecode",
            "address": address,
            "apikey": self._api_key or "YourApiKeyToken",
        }
        data = await self._explorer_get(params)
        if data and data.get("status") == "1":
            result = data["result"][0]
            return result.get("SourceCode") or None
        return None

    async def get_contract_abi(self, address: str) -> Optional[list]:
        """Fetch ABI for a verified contract."""
        params = {
            "module": "contract",
            "action": "getabi",
            "address": address,
            "apikey": self._api_key or "YourApiKeyToken",
        }
        data = await self._explorer_get(params)
        if data and data.get("status") == "1":
            try:
                return json.loads(data["result"])
            except (json.JSONDecodeError, TypeError):
                return None
        return None

    async def get_contract_creator(self, address: str) -> Optional[str]:
        """Return the address that deployed *address*."""
        params = {
            "module": "contract",
            "action": "getcontractcreation",
            "contractaddresses": address,
            "apikey": self._api_key or "YourApiKeyToken",
        }
        data = await self._explorer_get(params)
        if data and data.get("status") == "1" and data["result"]:
            return data["result"][0].get("contractCreator")
        return None

    # ------------------------------------------------------------------
    # Wallet / transaction data
    # ------------------------------------------------------------------

    async def get_tx_list(self, address: str, page: int = 1, offset: int = 100) -> List[Dict]:
        """Fetch normal transactions for *address* from the block explorer."""
        params = {
            "module": "account",
            "action": "txlist",
            "address": address,
            "startblock": 0,
            "endblock": 99999999,
            "page": page,
            "offset": offset,
            "sort": "desc",
            "apikey": self._api_key or "YourApiKeyToken",
        }
        data = await self._explorer_get(params)
        if data and data.get("status") == "1":
            return data.get("result", [])
        return []

    async def get_eth_balance(self, address: str) -> Optional[float]:
        """Return native token balance in ether-equivalent units."""
        params = {
            "module": "account",
            "action": "balance",
            "address": address,
            "tag": "latest",
            "apikey": self._api_key or "YourApiKeyToken",
        }
        data = await self._explorer_get(params)
        if data and data.get("status") == "1":
            try:
                return int(data["result"]) / 1e18
            except (ValueError, TypeError):
                return None
        return None

    async def get_internal_tx_list(self, address: str, offset: int = 100) -> List[Dict]:
        """Fetch internal transactions for *address*."""
        params = {
            "module": "account",
            "action": "txlistinternal",
            "address": address,
            "startblock": 0,
            "endblock": 99999999,
            "page": 1,
            "offset": offset,
            "sort": "desc",
            "apikey": self._api_key or "YourApiKeyToken",
        }
        data = await self._explorer_get(params)
        if data and data.get("status") == "1":
            return data.get("result", [])
        return []

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10))
    async def _explorer_get(self, params: Dict[str, Any]) -> Optional[Dict]:
        try:
            resp = await self._http.get(self._explorer_base, params=params)
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:
            log.warning(
                "explorer_request_failed",
                chain=self._chain,
                error=str(exc),
            )
            return None

    # Keep old name as an alias for backward-compatibility
    _etherscan_get = _explorer_get

    async def close(self) -> None:
        await self._http.aclose()
