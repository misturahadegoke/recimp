"""
Append-only JSONL journal for on-chain agent trades.

Atomic per-line writes (tmp + rename). No external DB.
Schema is versioned (currently "1") so we can migrate later.
"""
from __future__ import annotations

import json
import os
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "1"


def _iso_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def new_entry(
    strategy: str,
    action: str,
    *,
    tx_hash: str | None = None,
    symbol: str | None = None,
    pnl_usd: float = 0.0,
    params: dict | None = None,
    note: str = "",
    ts: str | None = None,
) -> dict[str, Any]:
    """Build a new journal entry dict (NOT yet written)."""
    if not strategy:
        raise ValueError("strategy is required")
    if action not in {"OPEN", "CLOSE", "REBALANCE", "CLAIM", "INIT"}:
        raise ValueError(f"invalid action: {action!r}")

    return {
        "version": SCHEMA_VERSION,
        "id": str(uuid.uuid4()),
        "ts": ts or _iso_now(),
        "strategy": strategy,
        "action": action,
        "symbol": symbol,
        "tx_hash": tx_hash,
        "params": params or {},
        "pnl_usd": float(pnl_usd),
        "note": note,
        "verify": {"status": "pending"},
    }


class Journal:
    """Append-only JSONL journal with safe concurrent reads."""

    def __init__(self, path: str | Path):
        self.path = Path(path)

    def _ensure_parent(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def exists(self) -> bool:
        return self.path.exists()

    def append(self, entry: dict[str, Any]) -> None:
        """Append one entry atomically (write to tmp + os.replace)."""
        self._ensure_parent()
        line = json.dumps(entry, separators=(",", ":"), ensure_ascii=False)
        with tempfile.NamedTemporaryFile(
            mode="w",
            dir=str(self.path.parent),
            prefix=self.path.name + ".",
            suffix=".tmp",
            delete=False,
            encoding="utf-8",
        ) as tmp:
            tmp.write(line + "\n")
            tmp_path = tmp.name
        # Append to main file using a single Open(append)+rename dance so we don't
        # race with other writers; for the hosted single-agent case this is fine.
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(line + "\n")
        try:
            os.unlink(tmp_path)
        except OSError:
            pass

    def read_all(self) -> list[dict[str, Any]]:
        if not self.exists():
            return []
        entries: list[dict[str, Any]] = []
        with open(self.path, encoding="utf-8") as f:
            for lineno, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError as e:
                    raise ValueError(
                        f"journal parse error at line {lineno}: {e}"
                    ) from e
        return entries

    def update_entry(self, entry_id: str, patch: dict[str, Any]) -> bool:
        """Rewrite the journal with `patch` applied to matching entry.

        Returns True if the entry was found, False otherwise.
        """
        entries = self.read_all()
        found = False
        for e in entries:
            if e.get("id") == entry_id:
                e.update(patch)
                found = True
                break
        if not found:
            return False
        self._rewrite(entries)
        return True

    def _rewrite(self, entries: list[dict[str, Any]]) -> None:
        self._ensure_parent()
        tmp_fd, tmp_path = tempfile.mkstemp(
            dir=str(self.path.parent), prefix=self.path.name + ".", suffix=".tmp"
        )
        try:
            with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
                for e in entries:
                    f.write(json.dumps(e, separators=(",", ":"), ensure_ascii=False) + "\n")
            os.replace(tmp_path, self.path)
        except Exception:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise


def default_journal_path() -> Path:
    """Default location: $RECIMP_JOURNAL > ./data/journal.jsonl."""
    env = os.environ.get("RECIMP_JOURNAL")
    if env:
        return Path(env)
    return Path("data/journal.jsonl")
