"""
Ethereum mempool listener.

Connects to an Ethereum WebSocket RPC endpoint, monitors for new block
transactions, identifies contract deployments, auto-scans them through the
full intelligence pipeline, and publishes threat alerts to all subscribed
WebSocket clients.

Architecture:
  - MempoolListener runs as a background asyncio task (started on app lifespan)
  - Scan results are queued on a shared asyncio.Queue
  - The /api/v1/realtime WebSocket endpoint drains the queue per client
"""
from __future__ import annotations

import asyncio
from typing import Any, Dict, Optional

import structlog
from web3 import AsyncWeb3
from web3.providers import WebsocketProvider

from app.config import get_settings
from app.core.ai.classifier import VulnerabilityClassifier
from app.core.analyzer.contract_profiler import profile_contract
from app.core.analyzer.risk_engine import calculate_risk_score
from app.core.analyzer.vulnerability_parser import normalise_findings
from app.core.intelligence.blockchain_client import BlockchainClient
from app.core.scanner.slither_scanner import SlitherScanner

log = structlog.get_logger(__name__)
settings = get_settings()

_classifier = VulnerabilityClassifier()

# Global broadcast queue — every detected high-risk contract alert is put here.
# The WebSocket endpoint fans it out to all connected clients.
alert_queue: asyncio.Queue = asyncio.Queue(maxsize=500)

# Track currently running listener task so it is only started once.
_listener_task: Optional[asyncio.Task] = None


async def start_listener() -> None:
    """
    Start the background mempool listener task if ETH_WS_URL is configured
    and MEMPOOL_AUTO_SCAN is enabled.  Safe to call multiple times.
    """
    global _listener_task
    if not settings.eth_ws_url or not settings.mempool_auto_scan:
        log.info(
            "mempool_listener_disabled",
            reason="ETH_WS_URL or MEMPOOL_AUTO_SCAN not set",
        )
        return

    if _listener_task and not _listener_task.done():
        return  # already running

    _listener_task = asyncio.create_task(_run_listener(), name="mempool_listener")
    log.info("mempool_listener_started", ws_url=settings.eth_ws_url)


async def stop_listener() -> None:
    """Cancel the background listener task on shutdown."""
    global _listener_task
    if _listener_task and not _listener_task.done():
        _listener_task.cancel()
        try:
            await _listener_task
        except asyncio.CancelledError:
            pass
    _listener_task = None
    log.info("mempool_listener_stopped")


async def _run_listener() -> None:
    """
    Main listener loop.

    Subscribes to new block headers, inspects every transaction in each block
    for contract deployments (``to`` is None / empty), fetches the verified
    source from Etherscan, and runs a quick Slither scan.
    """
    slither = SlitherScanner()
    blockchain = BlockchainClient()

    while True:
        try:
            async with AsyncWeb3(WebsocketProvider(settings.eth_ws_url)) as w3:
                log.info("mempool_ws_connected", url=settings.eth_ws_url)

                # web3.py 6.x: subscribe() returns an async iterator directly
                subscription = await w3.eth.subscribe("newHeads")
                async for block_data in subscription:
                    block_number = block_data.get("number")
                    if block_number is None:
                        continue

                    await _process_block(
                        w3=w3,
                        block_number=block_number,
                        slither=slither,
                        blockchain=blockchain,
                    )

        except asyncio.CancelledError:
            raise
        except Exception as exc:
            log.error("mempool_listener_error", error=str(exc))
            # Back-off and reconnect
            await asyncio.sleep(10)


async def _process_block(
    w3: AsyncWeb3,
    block_number: int,
    slither: SlitherScanner,
    blockchain: BlockchainClient,
) -> None:
    """Scan all contract-creation transactions in *block_number*."""
    try:
        block = await w3.eth.get_block(block_number, full_transactions=True)
    except Exception as exc:
        log.warning("block_fetch_error", block=block_number, error=str(exc))
        return

    for tx in block.get("transactions", []):
        # Contract creation: ``to`` is None/empty
        if tx.get("to"):
            continue

        contract_address = await _get_created_address(w3, tx["hash"])
        if not contract_address:
            continue

        log.info("new_contract_detected", address=contract_address, block=block_number)
        asyncio.create_task(
            _scan_and_alert(contract_address, slither, blockchain),
            name=f"scan_{contract_address}",
        )


async def _get_created_address(w3: AsyncWeb3, tx_hash: Any) -> Optional[str]:
    """Return the deployed contract address from a transaction receipt."""
    try:
        receipt = await w3.eth.get_transaction_receipt(tx_hash)
        return receipt.get("contractAddress")
    except Exception:
        return None


async def _scan_and_alert(
    address: str,
    slither: SlitherScanner,
    blockchain: BlockchainClient,
) -> None:
    """
    Fetch source, scan with Slither, build a risk score, and push a
    ThreatAlert onto the global queue if the score is significant.
    """
    source_code = await blockchain.get_contract_source(address)
    creator = await blockchain.get_contract_creator(address)

    if not source_code:
        # Unverified contract — still report with limited info
        alert = _build_alert(
            address=address,
            creator=creator,
            risk_score=0.0,
            risk_level="unknown",
            vulnerability_count=0,
            top_reasons=["Source code not verified on Etherscan"],
        )
        await _publish(alert)
        return

    profile = profile_contract(source_code)
    scan_result = await slither.scan_source(source_code)
    findings = normalise_findings([scan_result])

    classifications = _classifier.predict_batch(findings) if findings else []
    ai_boosts = [c for _, c in classifications] if classifications else None

    risk = calculate_risk_score(
        findings,
        is_proxy=profile.is_proxy,
        has_mint=profile.has_mint,
        has_ownership=profile.has_ownership,
        ai_boosts=ai_boosts,
    )

    # Build human-readable reasons
    reasons: list[str] = []
    if profile.has_mint:
        reasons.append("Hidden mint capability")
    if profile.has_ownership:
        reasons.append("Owner privilege detected")
    if profile.is_proxy:
        reasons.append("Upgradeable proxy")
    for f in findings[:3]:
        reasons.append(f"{f.severity.upper()}: {f.title}")

    alert = _build_alert(
        address=address,
        creator=creator,
        risk_score=risk.score,
        risk_level=risk.level.value,
        vulnerability_count=len(findings),
        top_reasons=reasons,
    )

    log.info(
        "threat_alert_generated",
        address=address,
        risk_score=risk.score,
        risk_level=risk.level.value,
    )
    await _publish(alert)


def _build_alert(
    address: str,
    creator: Optional[str],
    risk_score: float,
    risk_level: str,
    vulnerability_count: int,
    top_reasons: list[str],
) -> Dict[str, Any]:
    return {
        "type": "threat_alert",
        "address": address,
        "creator": creator,
        "risk_score": risk_score,
        "risk_level": risk_level,
        "vulnerability_count": vulnerability_count,
        "reasons": top_reasons,
    }


async def _publish(alert: Dict[str, Any]) -> None:
    """Put an alert on the queue, dropping oldest if full."""
    if alert_queue.full():
        try:
            alert_queue.get_nowait()
        except asyncio.QueueEmpty:
            pass
    await alert_queue.put(alert)
