from dataclasses import dataclass

import requests
from eth_account import Account
from eth_account.messages import encode_defunct


class AdapterError(Exception):
    pass


class AdapterNotConfiguredError(AdapterError):
    pass


def build_challenge_message(network: str, address: str, nonce: str, issued_at: str) -> str:
    return (
        "AML+18 wallet ownership verification\n"
        f"network: {network}\n"
        f"address: {address}\n"
        f"nonce: {nonce}\n"
        f"issued_at: {issued_at}\n"
        "Signing this message proves control of the private key for the "
        "address above. It does not authorize any transaction."
    )


def recover_signer_address(message: str, signature: str) -> str:
    try:
        signable = encode_defunct(text=message)
        return Account.recover_message(signable, signature=signature)
    except Exception as exc:
        raise AdapterError(f"could not recover signer address: {exc}") from exc


@dataclass
class TestTransferResult:
    tx_hash: str


@dataclass
class TestTransferStatus:
    status: str  # "pending" | "confirmed" | "failed"
    confirmations: int = 0


class EVMTestTransferAdapter:
    """Sends a small, fixed-amount native-token transfer to a self-hosted
    address and polls for confirmation -- EBA Travel Rule guidelines option
    (c). Requires a funded sender account; see
    WALLET_OWNERSHIP_EVM_SENDER_PRIVATE_KEY / WALLET_OWNERSHIP_EVM_RPC_URL.
    """

    def __init__(
        self,
        rpc_url: str,
        sender_private_key: str,
        chain_id: int,
        amount_wei: int,
        min_confirmations: int,
        timeout_seconds: float,
    ):
        self.rpc_url = (rpc_url or "").strip()
        self.sender_private_key = (sender_private_key or "").strip()
        self.chain_id = chain_id
        self.amount_wei = amount_wei
        self.min_confirmations = min_confirmations
        self.timeout_seconds = timeout_seconds

    def _ensure_configured(self) -> None:
        if not self.rpc_url or not self.sender_private_key:
            raise AdapterNotConfiguredError("EVM test-transfer adapter is not configured")

    def _rpc(self, method: str, params: list):
        try:
            response = requests.post(
                self.rpc_url,
                json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params},
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
            data = response.json()
        except requests.RequestException as exc:
            raise AdapterError(f"EVM RPC call {method} failed: {exc}") from exc
        except ValueError as exc:
            raise AdapterError(f"EVM RPC call {method} returned non-json response") from exc

        if "error" in data:
            raise AdapterError(f"EVM RPC error on {method}: {data['error']}")
        return data["result"]

    def start_transfer(self, address: str) -> TestTransferResult:
        self._ensure_configured()
        sender = Account.from_key(self.sender_private_key)

        nonce_hex = self._rpc("eth_getTransactionCount", [sender.address, "pending"])
        gas_price_hex = self._rpc("eth_gasPrice", [])

        tx = {
            "nonce": int(nonce_hex, 16),
            "to": address,
            "value": self.amount_wei,
            "gas": 21000,
            "gasPrice": int(gas_price_hex, 16),
            "chainId": self.chain_id,
        }
        signed = Account.sign_transaction(tx, self.sender_private_key)
        tx_hash = self._rpc("eth_sendRawTransaction", ["0x" + signed.raw_transaction.hex()])
        return TestTransferResult(tx_hash=tx_hash)

    def get_transfer_status(self, tx_hash: str) -> TestTransferStatus:
        self._ensure_configured()
        receipt = self._rpc("eth_getTransactionReceipt", [tx_hash])
        if receipt is None:
            return TestTransferStatus(status="pending")

        if receipt.get("status") != "0x1":
            return TestTransferStatus(status="failed")

        latest_block_hex = self._rpc("eth_blockNumber", [])
        confirmations = int(latest_block_hex, 16) - int(receipt["blockNumber"], 16) + 1
        if confirmations >= self.min_confirmations:
            return TestTransferStatus(status="confirmed", confirmations=confirmations)
        return TestTransferStatus(status="pending", confirmations=confirmations)
