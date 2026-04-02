"""
/api/v1/graph — wallet relationship graph endpoints.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.services.graph_service import GraphService
from app.utils.helpers import is_valid_eth_address

router = APIRouter(prefix="/graph", tags=["graph"])


@router.get(
    "/wallet/{address}",
    summary="Get wallet relationship graph (wallet → contract → wallet)",
)
async def wallet_graph(
    address: str,
    depth: int = Query(1, ge=1, le=2, description="Traversal depth (1 = direct links only)"),
    max_nodes: int = Query(50, ge=5, le=200, description="Max nodes to return"),
) -> dict:
    """
    Build and return a wallet-centric relationship graph.

    Returns:
    ```json
    {
      "center": "0x...",
      "nodes": [{"id": "0x...", "type": "wallet"|"contract", "label": "0x12…ab"}],
      "edges": [{"source": "0x...", "target": "0x...", "type": "deployed"|"called"|"funded"}],
      "stats": {"node_count": N, "edge_count": M, "depth": D}
    }
    ```
    """
    if not is_valid_eth_address(address):
        raise HTTPException(status_code=422, detail="Invalid Ethereum address format")

    service = GraphService()
    try:
        return await service.build_wallet_graph(address, depth=depth, max_nodes=max_nodes)
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Graph build failed: {exc}"
        ) from exc
