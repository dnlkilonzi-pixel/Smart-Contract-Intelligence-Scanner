"""Wallet intelligence orchestration service."""
from __future__ import annotations

import json
from typing import Optional

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.intelligence.blockchain_client import BlockchainClient
from app.core.intelligence.rugpull_detector import assess_rug_pull_risk
from app.core.intelligence.wallet_analyzer import analyse_wallet
from app.models.wallet import WalletProfile
from app.schemas.wallet import WalletIntelligenceOut
from sqlalchemy import select

log = structlog.get_logger(__name__)


class WalletService:
    """Orchestrates wallet data collection and rug-pull assessment."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._blockchain = BlockchainClient()

    async def get_wallet_intelligence(self, address: str) -> WalletIntelligenceOut:
        """
        Fetch on-chain data for *address*, run rug-pull assessment,
        persist the profile, and return the intelligence report.
        """
        # Check cache
        existing = await self._db.execute(
            select(WalletProfile).where(WalletProfile.address == address.lower())
        )
        cached: Optional[WalletProfile] = existing.scalar_one_or_none()

        behaviour = await analyse_wallet(address, self._blockchain)
        assessment = assess_rug_pull_risk(behaviour)

        profile_data = {
            "deployed_contracts": behaviour.deployed_contracts,
            "interacted_contracts": behaviour.interacted_contracts[:20],
            "large_outflows": behaviour.large_outflows,
            "rugpull_assessment": {
                "score": assessment.score,
                "explanation": assessment.explanation,
            },
        }

        if cached:
            cached.tx_count = behaviour.tx_count
            cached.eth_balance = behaviour.eth_balance
            cached.first_seen_block = behaviour.first_seen_block
            cached.last_seen_block = behaviour.last_seen_block
            cached.is_contract_deployer = bool(behaviour.deployed_contracts)
            cached.is_rug_pull_suspect = assessment.is_suspect
            cached.rugpull_score = assessment.score
            cached.flash_loan_count = behaviour.flash_loan_count
            cached.unique_contracts_interacted = len(behaviour.interacted_contracts)
            cached.intelligence_snapshot = json.dumps(profile_data)
            await self._db.commit()
            wallet = cached
        else:
            wallet = WalletProfile(
                address=address.lower(),
                tx_count=behaviour.tx_count,
                eth_balance=behaviour.eth_balance,
                first_seen_block=behaviour.first_seen_block or None,
                last_seen_block=behaviour.last_seen_block or None,
                is_contract_deployer=bool(behaviour.deployed_contracts),
                is_rug_pull_suspect=assessment.is_suspect,
                rugpull_score=assessment.score,
                flash_loan_count=behaviour.flash_loan_count,
                unique_contracts_interacted=len(behaviour.interacted_contracts),
                intelligence_snapshot=json.dumps(profile_data),
            )
            self._db.add(wallet)
            await self._db.commit()
            await self._db.refresh(wallet)

        return WalletIntelligenceOut(
            address=address,
            tx_count=wallet.tx_count,
            eth_balance=wallet.eth_balance,
            first_seen_block=wallet.first_seen_block,
            last_seen_block=wallet.last_seen_block,
            is_contract_deployer=wallet.is_contract_deployer,
            is_rug_pull_suspect=wallet.is_rug_pull_suspect,
            rugpull_score=wallet.rugpull_score,
            flash_loan_count=wallet.flash_loan_count,
            unique_contracts_interacted=wallet.unique_contracts_interacted,
            risk_indicators=assessment.indicators,
            raw_intelligence=profile_data,
        )
