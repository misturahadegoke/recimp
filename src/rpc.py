"""
JSON-RPC client for EVM-compatible chains (Pharos Pacific + Atlantic).

Exponential-backoff retry on rate limits and transient errors.
No third-party deps (urllib only).
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from typing import Any


class RpcError(Exception):
    """Raised when the RPC endpoint returns a structured error or is unreachable."""


class RpcClient:
    """Minimal JSON-RPC client with retry+backoff."""

    def __init__(
        self,
        url: str,
        timeout: float = 15.0,
        max_retries: int = 4,
        backoff: tuple[float, ...] = (0.4, 0.8, 1.6, 3.2),
    ):
        self.url = url
        self.timeout = timeout
        self.max_retries = max_retries
        self.backoff = backoff

    def call(self, method: str, params: list[Any] | None = None) -> Any:
        params = params or []
        body = json.dumps(
            {"jsonrpc": "2.0", "method": method, "params": params, "id": 1}
        ).encode("utf-8")

        last_err: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                req = urllib.request.Request(
                    self.url,
                    data=body,
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    raw = resp.read().decode("utf-8")
                payload = json.loads(raw)
                if "error" in payload and payload["error"]:
                    raise RpcError(
                        f"RPC error for {method}: "
                        f"{payload['error'].get('message', payload['error'])}"
                    )
                return payload.get("result")
            except urllib.error.HTTPError as e:
                # 429 / 5xx → backoff + retry. 4xx (other) → fail.
                if e.code in (429, 502, 503, 504) and attempt < self.max_retries:
                    time.sleep(self.backoff[min(attempt, len(self.backoff) - 1)])
                    last_err = e
                    continue
                raise RpcError(f"HTTP {e.code} from RPC: {e.reason}") from e
            except (urllib.error.URLError, TimeoutError) as e:
                if attempt < self.max_retries:
                    time.sleep(self.backoff[min(attempt, len(self.backoff) - 1)])
                    last_err = e
                    continue
                raise RpcError(f"RPC unreachable: {e}") from e
            except json.JSONDecodeError as e:
                raise RpcError(f"Non-JSON response from RPC: {e}") from e
        raise RpcError(f"RPC call failed after {self.max_retries + 1} attempts") from last_err

    # ---- Convenience helpers ----

    def chain_id(self) -> int:
        return int(self.call("eth_chainId"), 16)

    def block_number(self) -> int:
        return int(self.call("eth_blockNumber"), 16)

    def tx_receipt(self, tx_hash: str) -> dict | None:
        """Returns the receipt dict, or None if the tx is unknown / pending."""
        return self.call("eth_getTransactionReceipt", [tx_hash])

    def tx_by_hash(self, tx_hash: str) -> dict | None:
        return self.call("eth_getTransactionByHash", [tx_hash])
