"""
Scan orchestration service.

Coordinates Slither (+ optionally Mythril), the vulnerability parser,
risk engine, contract profiler, and AI classifier into a single pipeline.
"""
from __future__ import annotations

import json
from typing import List, Optional

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.ai.classifier import VulnerabilityClassifier
from app.core.analyzer.contract_profiler import ContractProfile, profile_contract
from app.core.analyzer.risk_engine import RiskScoreResult, calculate_risk_score
from app.core.analyzer.vulnerability_parser import normalise_findings
from app.core.intelligence.blockchain_client import BlockchainClient
from app.core.scanner.base_scanner import Finding, ScanResult
from app.core.scanner.mythril_scanner import MythrilScanner
from app.core.scanner.slither_scanner import SlitherScanner
from app.models.contract import Contract, RiskLevel
from app.models.vulnerability import Vulnerability
from app.schemas.contract import ContractProfileOut, ScanResponse, VulnerabilityOut

log = structlog.get_logger(__name__)

_classifier = VulnerabilityClassifier()


class ScanService:
    """Orchestrates the full scanning pipeline."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._slither = SlitherScanner()
        self._mythril = MythrilScanner()
        self._blockchain = BlockchainClient()

    async def scan(
        self,
        source_code: Optional[str],
        address: Optional[str],
        compiler_version: str = "0.8.19",
        enable_mythril: bool = False,
    ) -> ScanResponse:
        """
        Run the full intelligence pipeline:

        1. Fetch source from chain if only address provided
        2. Profile the contract
        3. Run Slither (and optionally Mythril)
        4. Normalise + de-duplicate findings
        5. Run AI classifier on findings
        6. Calculate risk score
        7. Persist to database
        8. Return structured response
        """
        creator_address: Optional[str] = None

        # Step 1 — fetch source from chain
        if not source_code and address:
            log.info("fetching_source_from_chain", address=address)
            source_code = await self._blockchain.get_contract_source(address)
            creator_address = await self._blockchain.get_contract_creator(address)

        if not source_code:
            raise ValueError("No source code available — provide source_code or a verified address")

        # Step 2 — profile the contract
        profile: ContractProfile = profile_contract(source_code)

        # Step 3 — static analysis
        scan_results: List[ScanResult] = []

        slither_result = await self._slither.scan_source(source_code, compiler_version)
        scan_results.append(slither_result)

        if enable_mythril:
            mythril_result = await self._mythril.scan_source(source_code, compiler_version)
            scan_results.append(mythril_result)

        # Step 4 — normalise
        findings: List[Finding] = normalise_findings(scan_results)

        # Step 5 — AI classification
        if findings:
            classifications = _classifier.predict_batch(findings)
        else:
            classifications = []

        # Step 6 — risk score
        ai_boosts = [conf for _, conf in classifications] if classifications else None
        risk: RiskScoreResult = calculate_risk_score(
            findings,
            is_proxy=profile.is_proxy,
            has_mint=profile.has_mint,
            has_ownership=profile.has_ownership,
            ai_boosts=ai_boosts,
        )

        # Step 7 — persist
        contract = await self._persist_contract(
            address=address,
            source_code=source_code,
            compiler_version=compiler_version,
            risk=risk,
            profile=profile,
            findings=findings,
            classifications=classifications,
            creator_address=creator_address,
        )

        # Step 8 — build response
        vuln_outs: List[VulnerabilityOut] = []
        for finding, (ai_cat, ai_conf) in zip(findings, classifications or []):
            vuln_outs.append(
                VulnerabilityOut(
                    tool=finding.tool,
                    check=finding.check,
                    title=finding.title,
                    description=finding.description,
                    severity=finding.severity,
                    confidence=finding.confidence,
                    file_path=finding.file_path,
                    line_start=finding.line_start,
                    line_end=finding.line_end,
                    ai_category=ai_cat,
                    ai_confidence=round(ai_conf, 3),
                )
            )

        return ScanResponse(
            contract_id=contract.id,
            address=address,
            name=None,
            risk_score=risk.score,
            risk_level=risk.level.value,
            vulnerability_count=len(findings),
            vulnerabilities=vuln_outs,
            profile=ContractProfileOut(
                is_proxy=profile.is_proxy,
                has_mint=profile.has_mint,
                has_ownership=profile.has_ownership,
                creator_address=creator_address,
            ),
            scan_status="completed",
        )

    # ------------------------------------------------------------------
    # Persistence helpers
    # ------------------------------------------------------------------

    async def _persist_contract(
        self,
        address: Optional[str],
        source_code: str,
        compiler_version: str,
        risk: RiskScoreResult,
        profile: ContractProfile,
        findings: List[Finding],
        classifications: list,
        creator_address: Optional[str],
    ) -> Contract:
        contract = Contract(
            address=address,
            source_code=source_code,
            compiler_version=compiler_version,
            risk_score=risk.score,
            risk_level=risk.level,
            vulnerability_count=len(findings),
            scan_status="completed",
            scan_output=json.dumps(risk.breakdown),
            is_proxy=profile.is_proxy,
            has_mint=profile.has_mint,
            has_ownership=profile.has_ownership,
            creator_address=creator_address,
        )
        self._db.add(contract)
        await self._db.flush()  # get contract.id

        for i, finding in enumerate(findings):
            ai_cat: Optional[str] = None
            ai_conf: Optional[float] = None
            if classifications and i < len(classifications):
                ai_cat, ai_conf = classifications[i]

            vuln = Vulnerability(
                contract_id=contract.id,
                tool=finding.tool,
                check=finding.check,
                title=finding.title,
                description=finding.description or "",
                severity=finding.severity,
                confidence=finding.confidence,
                file_path=finding.file_path,
                line_start=finding.line_start,
                line_end=finding.line_end,
                ai_category=ai_cat,
                ai_confidence=ai_conf,
            )
            self._db.add(vuln)

        await self._db.commit()
        await self._db.refresh(contract)
        return contract
