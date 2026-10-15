"""Deposit monitor: scans new blocks of an EVM testnet for transfers to the
registered deposit addresses and opens a case for each. Read-only RPC, no
keys. Deposits seen on-chain carry no KYC data, so they are opened without
a counterparty name and (by the screening rule) land with a human unless
the client supplies identity data."""

from decimal import Decimal

from app.agent.models import AgentCase, DepositAddress
from app.extensions import db

MAX_BLOCKS_PER_SCAN = 50


def scan_address(rpc, dep: DepositAddress, max_blocks: int = MAX_BLOCKS_PER_SCAN) -> list[AgentCase]:
    """rpc(method, params) -> result. Returns newly created (unprocessed) cases."""
    latest = int(rpc("eth_blockNumber", []), 16)
    start = (dep.last_scanned_block + 1) if dep.last_scanned_block is not None else latest
    end = min(latest, start + max_blocks - 1)
    created = []
    for number in range(start, end + 1):
        block = rpc("eth_getBlockByNumber", [hex(number), True])
        for tx in (block or {}).get("transactions", []):
            if (tx.get("to") or "").lower() != dep.address.lower():
                continue
            if AgentCase.query.filter_by(developer_project_id=dep.developer_project_id, tx_hash=tx["hash"]).first():
                continue
            case = AgentCase(
                developer_project_id=dep.developer_project_id, chain=dep.chain, asset=dep.asset,
                amount=Decimal(int(tx["value"], 16)) / Decimal(10**18), tx_hash=tx["hash"],
                deposit_address=dep.address, counterparty_address=tx.get("from"),
            )
            db.session.add(case)
            created.append(case)
    if end >= start:
        dep.last_scanned_block = end
    db.session.commit()
    return created
