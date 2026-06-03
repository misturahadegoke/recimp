"""
verifier.py - Re-read each journal entry's tx hash via RPC and
attach confirmation metadata to the journal.

Status taxonomy:
  - ok         : tx was included and the status field is 0x1
  - reverted   : tx was included but the status field is 0x0
  - pending    : tx is in the mempool (no receipt yet)
  - not_found  : RPC doesn't know about the hash (wrong chain?)
"""
from __future__ import annotations
import time
from typing import Any, Dict, List, Optional

from rpc import RpcClient, RpcError, hex_to_int
from journal import JournalEntry, read_all, update_verification


def verify_one(rpc: RpcClient, entry: JournalEntry) -> Dict[str, Any]:
    """Look up an entry's tx hash and return a verify dict."""
    if not entry.tx_hash:
        return {
            "status":       "no_tx_hash",
            "block":        None,
            "gas_used":     None,
            "verified_at":  time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
    try:
        receipt = rpc.get_tx_receipt(entry.tx_hash)
    except RpcError as e:
        return {
            "status":       "rpc_error",
            "error":        str(e),
            "verified_at":  time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
    if receipt is None:
        # Not in a block yet — could be pending or wrong chain
        try:
            tx = rpc.get_tx(entry.tx_hash)
        except RpcError:
            tx = None
        if tx is None:
            return {
                "status":      "not_found",
                "verified_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            }
        return {
            "status":      "pending",
            "verified_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
    status_int = hex_to_int(receipt.get("status"), 1)
    return {
        "status":      "ok" if status_int == 1 else "reverted",
        "block":       hex_to_int(receipt.get("blockNumber")),
        "gas_used":    hex_to_int(receipt.get("gasUsed")),
        "verified_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


def verify_all(
    rpc: RpcClient,
    path: Optional[str] = None,
    strategy: Optional[str] = None,
    since: Optional[str] = None,
) -> Dict[str, int]:
    """Verify all matching entries in the journal. Returns a count
    summary {ok, reverted, pending, not_found, no_tx_hash, error}."""
    entries = read_all(path)
    summary = {"ok": 0, "reverted": 0, "pending": 0, "not_found": 0, "no_tx_hash": 0, "rpc_error": 0, "total": 0}
    for e in entries:
        if strategy and e.strategy != strategy:
            continue
        if since and e.ts < since:
            continue
        summary["total"] += 1
        v = verify_one(rpc, e)
        update_verification(e.id, v, path)
        status = v.get("status", "rpc_error")
        summary[status] = summary.get(status, 0) + 1
    return summary
