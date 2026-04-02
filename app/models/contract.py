"""
Contract ORM model and RiskLevel enum.
"""
from __future__ import annotations

import enum
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import DateTime, Float, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.database import Base


class RiskLevel(str, enum.Enum):
    """Normalised risk tier derived from the risk score."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Contract(Base):
    """Persisted record of a scanned smart contract."""

    __tablename__ = "contracts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    address: Mapped[Optional[str]] = mapped_column(String(42), index=True, nullable=True)
    name: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    compiler_version: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    source_code: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Risk assessment
    risk_score: Mapped[float] = mapped_column(Float, default=0.0)
    risk_level: Mapped[RiskLevel] = mapped_column(String(16), default=RiskLevel.LOW)
    vulnerability_count: Mapped[int] = mapped_column(Integer, default=0)
    scan_status: Mapped[str] = mapped_column(String(32), default="pending")
    scan_output: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Contract profile flags
    is_proxy: Mapped[bool] = mapped_column(default=False)
    has_mint: Mapped[bool] = mapped_column(default=False)
    has_ownership: Mapped[bool] = mapped_column(default=False)
    creator_address: Mapped[Optional[str]] = mapped_column(String(42), nullable=True)

    # Chain context
    chain: Mapped[str] = mapped_column(String(32), default="ethereum")

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

    # Relationships
    vulnerabilities: Mapped[list["Vulnerability"]] = relationship(  # noqa: F821
        "Vulnerability",
        back_populates="contract",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<Contract id={self.id} address={self.address!r} "
            f"risk={self.risk_level} score={self.risk_score}>"
        )
