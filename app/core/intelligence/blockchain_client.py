"""
Blockchain client — fetches on-chain data via Web3.py and Etherscan API.

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

ETHERSCAN_BASE = "https://api.etherscan.io/api"


class BlockchainClient:
    """Async client for Ethereum on-chain data."""

    def __init__(self) -> None:
        self._http = httpx.AsyncClient(timeout=30)

    # ------------------------------------------------------------------
    # Contract data
    # ------------------------------------------------------------------

    async def get_contract_source(self, address: str) -> Optional[str]:
        """Fetch verified source code from Etherscan."""
        params = {
            "module": "contract",
            "action": "getsourcecode",
            "address": address,
            "apikey": settings.etherscan_api_key or "YourApiKeyToken",
        }
        data = await self._etherscan_get(params)
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
            "apikey": settings.etherscan_api_key or "YourApiKeyToken",
        }
        data = await self._etherscan_get(params)
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
            "apikey": settings.etherscan_api_key or "YourApiKeyToken",
        }
        data = await self._etherscan_get(params)
        if data and data.get("status") == "1" and data["result"]:
            return data["result"][0].get("contractCreator")
        return None

    # ------------------------------------------------------------------
    # Wallet / transaction data
    # ------------------------------------------------------------------

    async def get_tx_list(self, address: str, page: int = 1, offset: int = 100) -> List[Dict]:
        """Fetch normal transactions for *address* from Etherscan."""
        params = {
            "module": "account",
            "action": "txlist",
            "address": address,
            "startblock": 0,
            "endblock": 99999999,
            "page": page,
            "offset": offset,
            "sort": "desc",
            "apikey": settings.etherscan_api_key or "YourApiKeyToken",
        }
        data = await self._etherscan_get(params)
        if data and data.get("status") == "1":
            return data.get("result", [])
        return []

    async def get_eth_balance(self, address: str) -> Optional[float]:
        """Return ETH balance in ether."""
        params = {
            "module": "account",
            "action": "balance",
            "address": address,
            "tag": "latest",
            "apikey": settings.etherscan_api_key or "YourApiKeyToken",
        }
        data = await self._etherscan_get(params)
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
            "apikey": settings.etherscan_api_key or "YourApiKeyToken",
        }
        data = await self._etherscan_get(params)
        if data and data.get("status") == "1":
            return data.get("result", [])
        return []

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10))
    async def _etherscan_get(self, params: Dict[str, Any]) -> Optional[Dict]:
        try:
            resp = await self._http.get(ETHERSCAN_BASE, params=params)
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:
            log.warning("etherscan_request_failed", error=str(exc))
            return None

    async def close(self) -> None:
        await self._http.aclose()
