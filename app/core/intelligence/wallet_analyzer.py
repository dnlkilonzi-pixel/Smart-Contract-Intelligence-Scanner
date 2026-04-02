"""
Wallet behavior analyzer.

Analyses on-chain transaction patterns to produce behavioural metrics
useful for threat intelligence and rug-pull detection.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import List

from app.core.intelligence.blockchain_client import BlockchainClient


@dataclass
class WalletBehaviourReport:
    address: str
    tx_count: int = 0
    eth_balance: float = 0.0
    first_seen_block: int = 0
    last_seen_block: int = 0
    deployed_contracts: List[str] = field(default_factory=list)
    interacted_contracts: List[str] = field(default_factory=list)
    flash_loan_count: int = 0
    large_outflows: int = 0          # txs where value > 1 ETH out
    self_transfer_count: int = 0
    risk_indicators: List[str] = field(default_factory=list)


async def analyse_wallet(address: str, client: BlockchainClient) -> WalletBehaviourReport:
    """
    Fetch transaction data and build a behavioural report for *address*.
    """
    report = WalletBehaviourReport(address=address)

    txs = await client.get_tx_list(address, offset=200)
    internal_txs = await client.get_internal_tx_list(address, offset=200)
    balance = await client.get_eth_balance(address)

    if balance is not None:
        report.eth_balance = balance

    if not txs:
        return report

    report.tx_count = len(txs)
    blocks = [int(tx.get("blockNumber", 0)) for tx in txs if tx.get("blockNumber")]
    if blocks:
        report.first_seen_block = min(blocks)
        report.last_seen_block = max(blocks)

    contract_interactions: Counter = Counter()

    for tx in txs:
        is_contract_creation = tx.get("to", "") == ""
        to_addr = tx.get("to", "").lower()
        from_addr = tx.get("from", "").lower()

        if is_contract_creation and tx.get("contractAddress"):
            report.deployed_contracts.append(tx["contractAddress"])

        if to_addr and to_addr != address.lower():
            contract_interactions[to_addr] += 1

        # Large outflow detection (> 1 ETH)
        try:
            value_eth = int(tx.get("value", 0)) / 1e18
            if value_eth > 1.0 and from_addr == address.lower():
                report.large_outflows += 1
        except (ValueError, TypeError):
            pass

        # Self-transfer detection
        if to_addr == from_addr == address.lower():
            report.self_transfer_count += 1

    # Flash loan proxy detection in internal txs
    for itx in internal_txs:
        if itx.get("type") == "call" and int(itx.get("value", 0)) > 0:
            report.flash_loan_count += 1

    report.interacted_contracts = list(contract_interactions.keys())

    # Build human-readable risk indicators
    if report.deployed_contracts:
        report.risk_indicators.append(
            f"Deployed {len(report.deployed_contracts)} contract(s)"
        )
    if report.large_outflows >= 3:
        report.risk_indicators.append(
            f"{report.large_outflows} large outflow transactions (>1 ETH each)"
        )
    if report.flash_loan_count >= 5:
        report.risk_indicators.append(
            f"{report.flash_loan_count} possible flash loan interactions"
        )

    return report
