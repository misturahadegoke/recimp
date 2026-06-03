"""
rpc.py - JSON-RPC client.

Used by the verifier to look up a tx hash, get its receipt, and
read native-token price. No web3 framework dependency.
"""
from __future__ import annotations
import time
import requests
from typing import Any, Dict, List, Optional


class RpcError(Exception):
    pass


class RpcClient:
    def __init__(self, url: str, timeout: int = 30, max_retries: int = 4):
        self.url = url
        self.timeout = timeout
        self.max_retries = max_retries
        self._id = 0

    def call(self, method: str, params: List[Any]) -> Any:
        self._id += 1
        payload = {"jsonrpc": "2.0", "id": self._id, "method": method, "params": params}
        last_err: Optional[Exception] = None
        for attempt in range(self.max_retries):
            try:
                r = requests.post(self.url, json=payload, timeout=self.timeout)
                if r.status_code == 429 or r.status_code >= 500:
                    raise RpcError(f"HTTP {r.status_code}: {r.text[:200]}")
                data = r.json()
                if "error" in data:
                    raise RpcError(data["error"].get("message", "rpc error"))
                return data.get("result")
            except (requests.RequestException, RpcError) as e:
                last_err = e
                time.sleep(0.4 * (2 ** attempt))
        raise RpcError(f"RPC {method} failed after {self.max_retries} attempts: {last_err}")

    def get_tx_receipt(self, tx_hash: str) -> Optional[Dict[str, Any]]:
        r = self.call("eth_getTransactionReceipt", [tx_hash])
        return r if r else None

    def get_tx(self, tx_hash: str) -> Optional[Dict[str, Any]]:
        r = self.call("eth_getTransactionByHash", [tx_hash])
        return r if r else None

    def get_block(self, num: int) -> Dict[str, Any]:
        return self.call("eth_getBlockByNumber", [hex(num), False]) or {}

    def chain_id(self) -> int:
        return int(self.call("eth_chainId", []), 16)

    def block_number(self) -> int:
        return int(self.call("eth_blockNumber", []), 16)


def hex_to_int(v: Any, default: int = 0) -> int:
    if v is None:
        return default
    if isinstance(v, int):
        return v
    if not v or v == "0x":
        return default
    try:
        return int(v, 16)
    except ValueError:
        return default
