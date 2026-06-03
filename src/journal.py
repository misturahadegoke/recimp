"""
journal.py - Append-only trade log.

Format: JSONL (one JSON object per line). Each line is a single
trade entry, with optional verification metadata added in-place
after the verifier runs.

Schema (v1):

  {
    "version": "1",
    "id": "uuid4",
    "ts": "2026-06-03T16:00:00Z",
    "strategy": "stablecoin-farming",
    "action": "OPEN" | "CLOSE" | "REBALANCE" | "CLAIM",
    "symbol": "USDC",
    "tx_hash": "0x...",
    "params": {"size_usd": 1000, "max_slippage_bps": 30},
    "pnl_usd": 12.34,
    "note": "user-initiated",
    "verify": {
      "status": "ok" | "reverted" | "pending" | "not_found",
      "block": 12345,
      "gas_used": 21000,
      "verified_at": "2026-06-03T16:05:00Z"
    }
  }

Notes:
- The journal is append-only. Editing a verification in-place
  is allowed; rewriting an old entry is not.
- A small read-modify-write step is used to attach verify
  metadata; we identify the entry by `id`.
"""
from __future__ import annotations
import json
import os
import tempfile
import time
import uuid
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional


VALID_ACTIONS = {"OPEN", "CLOSE", "REBALANCE", "CLAIM"}


@dataclass
class JournalEntry:
    version: str = "1"
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    ts: str = field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    strategy: str = ""
    action: str = "OPEN"
    symbol: str = ""
    tx_hash: str = ""
    params: Dict[str, Any] = field(default_factory=dict)
    pnl_usd: float = 0.0
    note: str = ""
    verify: Optional[Dict[str, Any]] = None

    def to_jsonl(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False)

    @classmethod
    def from_jsonl(cls, line: str) -> "JournalEntry":
        d = json.loads(line)
        return cls(**d)


def default_path() -> str:
    return os.environ.get("RECIMP_JOURNAL", "data/journal.jsonl")


def append(entry: JournalEntry, path: Optional[str] = None) -> None:
    """Append a single entry to the journal."""
    path = path or default_path()
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    line = entry.to_jsonl() + "\n"
    # Atomic append: open with append mode (POSIX guarantees O_APPEND atomicity for small writes).
    with open(path, "a", encoding="utf-8") as f:
        f.write(line)


def read_all(path: Optional[str] = None) -> List[JournalEntry]:
    path = path or default_path()
    if not os.path.exists(path):
        return []
    out: List[JournalEntry] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(JournalEntry.from_jsonl(line))
            except (json.JSONDecodeError, TypeError):
                # Skip malformed lines but don't crash
                continue
    return out


def update_verification(
    entry_id: str,
    verify: Dict[str, Any],
    path: Optional[str] = None,
) -> bool:
    """In-place attach verify metadata to the entry with the given id.

    Returns True if the entry was found and updated, False otherwise.
    """
    path = path or default_path()
    if not os.path.exists(path):
        return False
    entries = read_all(path)
    found = False
    for e in entries:
        if e.id == entry_id:
            e.verify = verify
            found = True
    if not found:
        return False
    _rewrite(entries, path)
    return True


def _rewrite(entries: List[JournalEntry], path: str) -> None:
    """Atomic rewrite of the journal file."""
    dirpath = os.path.dirname(path) or "."
    fd, tmp_path = tempfile.mkstemp(dir=dirpath, prefix=".journal.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            for e in entries:
                f.write(e.to_jsonl() + "\n")
        os.replace(tmp_path, path)
    except Exception:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise
