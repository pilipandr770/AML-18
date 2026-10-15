"""Read-only blockchain adapters used by verify_incoming_funds. Testnet and
mock only -- there is deliberately no mainnet configuration and no signing
or key handling anywhere in this module."""

from dataclasses import dataclass
from decimal import Decimal


class ChainError(Exception):
    pass


@dataclass
class FundsCheck:
    found: bool
    confirmations: int = 0
    amount: Decimal | None = None
    to_address: str | None = None
    address_match: bool = False
    amount_match: bool = False
    sufficient_confirmations: bool = False
    detail: str = ""

    @property
    def verified(self) -> bool:
        return self.found and self.address_match and self.amount_match and self.sufficient_confirmations

    def as_dict(self) -> dict:
        return {
            "found": self.found,
            "confirmations": self.confirmations,
            "amount": None if self.amount is None else str(self.amount),
            "to_address": self.to_address,
            "address_match": self.address_match,
            "amount_match": self.amount_match,
            "sufficient_confirmations": self.sufficient_confirmations,
            "verified": self.verified,
            "detail": self.detail,
        }


def _evaluate(found, confirmations, amount, to_address, expected_address, expected_amount, min_confirmations) -> FundsCheck:
    if not found:
        return FundsCheck(found=False, detail="transaction not found")
    return FundsCheck(
        found=True,
        confirmations=confirmations,
        amount=amount,
        to_address=to_address,
        address_match=(to_address or "").lower() == (expected_address or "").lower(),
        amount_match=amount is not None and Decimal(amount) == Decimal(expected_amount),
        sufficient_confirmations=confirmations >= min_confirmations,
    )


class MockLedger:
    """Deterministic in-memory ledger for tests and the demo."""

    def __init__(self, min_confirmations: int = 1):
        self.min_confirmations = min_confirmations
        self._txs: dict[str, dict] = {}

    def add(self, tx_hash: str, to_address: str, amount, confirmations: int = 12):
        self._txs[tx_hash.lower()] = {"to": to_address, "amount": Decimal(str(amount)), "confirmations": confirmations}

    def verify(self, tx_hash: str, expected_address: str, expected_amount) -> FundsCheck:
        tx = self._txs.get((tx_hash or "").lower())
        if tx is None:
            return _evaluate(False, 0, None, None, expected_address, expected_amount, self.min_confirmations)
        return _evaluate(True, tx["confirmations"], tx["amount"], tx["to"], expected_address, expected_amount, self.min_confirmations)


class EvmRpcLedger:
    """Reads a native-asset transfer from an EVM JSON-RPC endpoint (intended
    for Sepolia). Read-only: eth_getTransactionByHash + eth_blockNumber."""

    def __init__(self, rpc_url: str, min_confirmations: int = 3, timeout_seconds: float = 10):
        self.rpc_url = (rpc_url or "").strip()
        self.min_confirmations = min_confirmations
        self.timeout_seconds = timeout_seconds

    def _rpc(self, method, params):
        import requests

        if not self.rpc_url:
            raise ChainError("EVM RPC URL is not configured")
        try:
            r = requests.post(
                self.rpc_url, json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params},
                timeout=self.timeout_seconds,
            )
            r.raise_for_status()
            data = r.json()
        except (requests.RequestException, ValueError) as exc:
            raise ChainError(f"RPC {method} failed: {exc}") from exc
        if "error" in data:
            raise ChainError(f"RPC error on {method}: {data['error']}")
        return data["result"]

    def verify(self, tx_hash: str, expected_address: str, expected_amount) -> FundsCheck:
        tx = self._rpc("eth_getTransactionByHash", [tx_hash])
        if tx is None or tx.get("blockNumber") is None:
            return _evaluate(False, 0, None, None, expected_address, expected_amount, self.min_confirmations)
        latest = int(self._rpc("eth_blockNumber", []), 16)
        confirmations = latest - int(tx["blockNumber"], 16) + 1
        amount = Decimal(int(tx["value"], 16)) / Decimal(10**18)
        return _evaluate(True, confirmations, amount, tx.get("to"), expected_address, expected_amount, self.min_confirmations)


def build_ledger(config):
    """Chain adapter selection from config. 'mock' is the default so nothing
    reaches a real network unless explicitly configured with a testnet RPC."""
    kind = (config.get("AGENT_CHAIN_ADAPTER") or "mock").lower()
    if kind == "evm":
        return EvmRpcLedger(
            config.get("AGENT_EVM_RPC_URL", ""),
            int(config.get("AGENT_MIN_CONFIRMATIONS", 3)),
            float(config.get("AGENT_EVM_RPC_TIMEOUT_SECONDS", 10)),
        )
    return MockLedger(int(config.get("AGENT_MIN_CONFIRMATIONS", 1)))
