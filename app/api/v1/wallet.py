"""
/api/v1/wallet — wallet intelligence endpoints.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import get_db
from app.schemas.wallet import WalletIntelligenceOut
from app.services.wallet_service import WalletService
from app.utils.helpers import is_valid_eth_address

router = APIRouter(prefix="/wallet", tags=["wallet"])


@router.get(
    "/{address}/intelligence",
    response_model=WalletIntelligenceOut,
    summary="Get intelligence report for a wallet address",
)
async def wallet_intelligence(
    address: str,
    db: AsyncSession = Depends(get_db),
) -> WalletIntelligenceOut:
    """
    Fetch on-chain transaction history for *address*, detect rug-pull
    patterns, and return a full behavioural intelligence report.
    """
    if not is_valid_eth_address(address):
        raise HTTPException(
            status_code=422,
            detail="Invalid Ethereum address format",
        )

    service = WalletService(db)
    try:
        return await service.get_wallet_intelligence(address)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Wallet intelligence failed: {exc}",
        ) from exc
