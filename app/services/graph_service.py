"""
Graph service — builds wallet→contract→wallet relationship graphs.

Returns a node/edge structure consumable by D3-force or vis-network
without requiring Neo4j (pure in-memory construction from Etherscan data).
The data model can be swapped for Neo4j transparently by replacing this
service while keeping the API shape identical.
"""
from __future__ import annotations

from typing import Any, Dict, List

import structlog

from app.core.intelligence.blockchain_client import BlockchainClient

log = structlog.get_logger(__name__)

# Node type constants
NODE_WALLET = "wallet"
NODE_CONTRACT = "contract"

# Edge type constants
EDGE_DEPLOYED = "deployed"
EDGE_CALLED = "called"
EDGE_FUNDED = "funded"


def _node(id_: str, node_type: str, **extra: Any) -> Dict[str, Any]:
    return {"id": id_, "type": node_type, **extra}


def _edge(source: str, target: str, edge_type: str, **extra: Any) -> Dict[str, Any]:
    return {"source": source, "target": target, "type": edge_type, **extra}


class GraphService:
    """Builds a wallet-relationship graph from on-chain transaction data."""

    def __init__(self) -> None:
        self._blockchain = BlockchainClient()

    async def build_wallet_graph(
        self,
        address: str,
        depth: int = 1,
        max_nodes: int = 50,
    ) -> Dict[str, Any]:
        """
        Return a graph dict with ``nodes`` and ``edges`` lists centred on *address*.

        - depth=1 : direct relationships only (fast)
        - depth=2 : also expand one level from each discovered node

        Each node: {"id", "type", "label", ...metadata}
        Each edge: {"source", "target", "type", "tx_hash"?, "value_eth"?}
        """
        nodes: Dict[str, Dict] = {}
        edges: List[Dict] = []
        visited: set = set()

        await self._expand_wallet(
            address=address.lower(),
            nodes=nodes,
            edges=edges,
            visited=visited,
            current_depth=0,
            max_depth=depth,
            max_nodes=max_nodes,
        )

        return {
            "center": address.lower(),
            "nodes": list(nodes.values()),
            "edges": edges,
            "stats": {
                "node_count": len(nodes),
                "edge_count": len(edges),
                "depth": depth,
            },
        }

    async def _expand_wallet(
        self,
        address: str,
        nodes: Dict[str, Dict],
        edges: List[Dict],
        visited: set,
        current_depth: int,
        max_depth: int,
        max_nodes: int,
    ) -> None:
        if address in visited or len(nodes) >= max_nodes:
            return
        visited.add(address)

        # Add the wallet node itself
        balance = await self._blockchain.get_eth_balance(address)
        nodes[address] = _node(
            address,
            NODE_WALLET,
            label=_short(address),
            eth_balance=balance,
        )

        txs = await self._blockchain.get_tx_list(address, offset=100)
        if not txs:
            return

        for tx in txs:
            if len(nodes) >= max_nodes:
                break

            tx_from = (tx.get("from") or "").lower()
            tx_to = (tx.get("to") or "").lower()
            is_deployment = tx_to == ""

            try:
                value_eth = int(tx.get("value", 0)) / 1e18
            except (ValueError, TypeError):
                value_eth = 0.0

            # Contract deployment
            if is_deployment and tx.get("contractAddress"):
                contract_addr = tx["contractAddress"].lower()
                if contract_addr not in nodes:
                    nodes[contract_addr] = _node(
                        contract_addr,
                        NODE_CONTRACT,
                        label=_short(contract_addr),
                    )
                edges.append(
                    _edge(
                        source=address,
                        target=contract_addr,
                        edge_type=EDGE_DEPLOYED,
                        tx_hash=tx.get("hash", ""),
                    )
                )
                continue

            # Outgoing call / transfer to another address
            if tx_from == address and tx_to and tx_to not in visited:
                if tx_to not in nodes:
                    # We don't know if it's a contract yet; mark as wallet
                    nodes[tx_to] = _node(
                        tx_to,
                        NODE_WALLET,
                        label=_short(tx_to),
                    )
                edge_type = EDGE_FUNDED if value_eth > 0 else EDGE_CALLED
                edges.append(
                    _edge(
                        source=address,
                        target=tx_to,
                        edge_type=edge_type,
                        value_eth=round(value_eth, 6),
                        tx_hash=tx.get("hash", ""),
                    )
                )

                # Recurse if depth allows
                if current_depth < max_depth and len(nodes) < max_nodes:
                    await self._expand_wallet(
                        address=tx_to,
                        nodes=nodes,
                        edges=edges,
                        visited=visited,
                        current_depth=current_depth + 1,
                        max_depth=max_depth,
                        max_nodes=max_nodes,
                    )


def _short(address: str) -> str:
    """Return a shortened address label for display."""
    return f"{address[:6]}…{address[-4:]}" if len(address) >= 10 else address
