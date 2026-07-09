"""
Verifier — re-reads each journal entry's tx hash via JSON-RPC and attaches
confirmation status, block number, and gas used.

For entries without a tx_hash (e.g. actions recorded before a tx was mined,
or the synthetic INIT entry), the verifier marks them as "no_tx" and skips.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable

from rpc import RpcError, RpcClient

from journal import Journal


_VERIFY_NO_TX = {"status": "no_tx"}


def _iso_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_receipt(receipt: dict | None, tx: dict | None) -> dict:
    """Build a `verify` block from a (possibly None) receipt and tx."""
    if receipt is None and tx is None:
        return {"status": "not_found"}
    if receipt is None:
        # Tx seen in mempool but no receipt yet → still pending
        return {"status": "pending"}
    status = receipt.get("status")
    status_hex = hex(int(status)) if status is not None else "0x0"
    block_hex = receipt.get("blockNumber")
    block = int(block_hex, 16) if block_hex else None
    gas_used_hex = receipt.get("gasUsed")
    gas_used = int(gas_used_hex, 16) if gas_used_hex else 0
    ok = status_hex == "0x1"
    return {
        "status": "ok" if ok else "reverted",
        "block": block,
        "gas_used": gas_used,
        "verified_at": _iso_now(),
    }


def verify_entries(
    entries: Iterable[dict],
    rpc: RpcClient,
    *,
    progress: bool = False,
) -> list[dict]:
    """Verify all entries that have a tx_hash and aren't already verified.

    Returns the list of entries that were actually re-checked (caller is
    responsible for writing back to disk if needed).
    """
    updated: list[dict] = []
    n = 0
    for entry in entries:
        n += 1
        if progress and n % 50 == 0:
            print(f"  verified {n} entries...", flush=True)

        if entry.get("verify", {}).get("status") not in ("pending", "not_found", None):
            # already terminal — skip
            continue

        tx_hash = entry.get("tx_hash")
        if not tx_hash:
            # mark as no_tx once, then skip forever
            if entry.get("verify", {}).get("status") != "no_tx":
                entry["verify"] = dict(_VERIFY_NO_TX)
                updated.append(entry)
            continue

        try:
            receipt = rpc.tx_receipt(tx_hash)
        except RpcError as e:
            entry["verify"] = {"status": "rpc_error", "error": str(e)}
            updated.append(entry)
            continue

        tx = None
        if receipt is None:
            try:
                tx = rpc.tx_by_hash(tx_hash)
            except RpcError:
                tx = None

        entry["verify"] = _parse_receipt(receipt, tx)
        updated.append(entry)

    return updated


def run(
    journal: Journal,
    rpc: RpcClient,
    *,
    strategy: str | None = None,
    since: str | None = None,
    progress: bool = True,
) -> dict:
    """CLI-style entry point: re-verify matching entries and persist.

    Returns a summary dict.
    """
    entries = journal.read_all()
    if not entries:
        return {"checked": 0, "skipped": 0, "updated": 0}

    # simple filters
    since_ts = since  # ISO 8601; comparison happens below if set

    targets = []
    for e in entries:
        if strategy and e.get("strategy") != strategy:
            continue
        if since_ts and e.get("ts", "") < since_ts:
            continue
        targets.append(e)

    if not targets:
        return {"checked": 0, "skipped": 0, "updated": 0}

    updated = verify_entries(targets, rpc, progress=progress)
    if not updated:
        return {"checked": len(targets), "updated": 0}

    # persist
    by_id = {e["id"]: e for e in updated}
    for original in entries:
        if original["id"] in by_id:
            original.update(by_id[original["id"]])
    journal._rewrite(entries)

    ok = sum(1 for e in updated if e["verify"].get("status") == "ok")
    rev = sum(1 for e in updated if e["verify"].get("status") == "reverted")
    pend = sum(1 for e in updated if e["verify"].get("status") == "pending")
    miss = sum(1 for e in updated if e["verify"].get("status") == "not_found")
    no_tx = sum(1 for e in updated if e["verify"].get("status") == "no_tx")
    errs = sum(1 for e in updated if e["verify"].get("status") == "rpc_error")

    return {
        "checked": len(targets),
        "updated": len(updated),
        "ok": ok,
        "reverted": rev,
        "pending": pend,
        "not_found": miss,
        "no_tx": no_tx,
        "rpc_error": errs,
    }
