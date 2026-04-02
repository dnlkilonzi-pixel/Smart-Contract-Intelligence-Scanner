"""
WalletProfile ORM model — persisted wallet intelligence record.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import DateTime, Float, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.database import Base


class WalletProfile(Base):
    """Cached on-chain behaviour profile for an Ethereum address."""

    __tablename__ = "wallet_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    address: Mapped[str] = mapped_column(String(42), unique=True, index=True)

    # Transaction statistics
    tx_count: Mapped[int] = mapped_column(Integer, default=0)
    eth_balance: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    first_seen_block: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    last_seen_block: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Behaviour flags
    is_contract_deployer: Mapped[bool] = mapped_column(default=False)
    is_rug_pull_suspect: Mapped[bool] = mapped_column(default=False)
    rugpull_score: Mapped[float] = mapped_column(Float, default=0.0)
    flash_loan_count: Mapped[int] = mapped_column(Integer, default=0)
    unique_contracts_interacted: Mapped[int] = mapped_column(Integer, default=0)

    # JSON snapshot of full intelligence output
    intelligence_snapshot: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<WalletProfile address={self.address!r} "
            f"rugpull_score={self.rugpull_score} suspect={self.is_rug_pull_suspect}>"
        )
