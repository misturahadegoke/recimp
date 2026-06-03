"""
reflection.py - Per-strategy performance stats.

For each strategy in the journal, compute:
  - trade_count      : number of entries
  - verified_count   : number with on-chain confirmation
  - win_count        : number of CLOSE entries with pnl_usd > 0
  - win_rate         : win_count / close_count
  - realized_pnl_usd : sum of pnl_usd for CLOSE entries
  - avg_pnl_usd      : mean of pnl_usd for CLOSE entries
  - total_gas        : sum of gas_used from verified entries
  - avg_gas_per_tx   : mean gas per verified tx
  - max_drawdown_usd : worst peak-to-trough drop in cumulative P&L
  - current_params   : most-recent params dict seen
  - verdict          : HEALTHY / UNDERPERFORMING / BROKEN / INSUFFICIENT_DATA
"""
from __future__ import annotations
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from journal import JournalEntry, read_all


VERDICT_HEALTHY           = "HEALTHY"
VERDICT_UNDERPERFORMING   = "UNDERPERFORMING"
VERDICT_BROKEN            = "BROKEN"
VERDICT_INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


@dataclass
class StrategyStats:
    strategy: str
    trade_count: int = 0
    verified_count: int = 0
    close_count: int = 0
    win_count: int = 0
    win_rate: float = 0.0
    realized_pnl_usd: float = 0.0
    avg_pnl_usd: float = 0.0
    total_gas: int = 0
    avg_gas_per_tx: float = 0.0
    max_drawdown_usd: float = 0.0
    current_params: Dict[str, Any] = field(default_factory=dict)
    verdict: str = VERDICT_INSUFFICIENT_DATA
    verdict_reason: str = ""
    first_seen: str = ""
    last_seen: str = ""


def _max_drawdown(closes_sorted: List[JournalEntry]) -> float:
    """Compute the worst peak-to-trough drop in cumulative P&L.

    Returns 0.0 if no closes, or if cumulative P&L never went down.
    """
    if not closes_sorted:
        return 0.0
    cum = 0.0
    peak = 0.0
    mdd = 0.0
    for e in closes_sorted:
        cum += e.pnl_usd
        if cum > peak:
            peak = cum
        dd = peak - cum
        if dd > mdd:
            mdd = dd
    return mdd


def _verdict(stats: StrategyStats) -> tuple[str, str]:
    if stats.close_count < 5:
        return VERDICT_INSUFFICIENT_DATA, f"Only {stats.close_count} closed trades; need at least 5 for a verdict."
    if stats.realized_pnl_usd < 0 and stats.win_rate < 0.4:
        return VERDICT_BROKEN, f"Negative P&L (${stats.realized_pnl_usd:.2f}) and low win rate ({stats.win_rate:.0%}). Pause this strategy."
    if stats.win_rate < 0.5 or stats.realized_pnl_usd < 0:
        return VERDICT_UNDERPERFORMING, f"Win rate {stats.win_rate:.0%} or P&L ${stats.realized_pnl_usd:.2f} is below target. Tighten entry rules."
    return VERDICT_HEALTHY, f"Win rate {stats.win_rate:.0%} and P&L ${stats.realized_pnl_usd:.2f} are healthy."


def compute(
    path: Optional[str] = None,
    strategy: Optional[str] = None,
    window_days: int = 30,
) -> List[StrategyStats]:
    """Read the journal and return per-strategy stats.

    `window_days` filters entries by `ts` (we compare against
    `now - window_days`). Pass 0 to disable the window.
    """
    entries = read_all(path)
    if not entries:
        return []

    # Optional window filter
    if window_days > 0:
        from datetime import datetime, timezone, timedelta
        cutoff = (datetime.now(timezone.utc) - timedelta(days=window_days)).strftime("%Y-%m-%dT%H:%M:%SZ")
        entries = [e for e in entries if e.ts >= cutoff]

    by_strat: Dict[str, List[JournalEntry]] = defaultdict(list)
    for e in entries:
        if strategy and e.strategy != strategy:
            continue
        by_strat[e.strategy].append(e)

    out: List[StrategyStats] = []
    for strat, es in by_strat.items():
        es.sort(key=lambda e: e.ts)
        closes = [e for e in es if e.action == "CLOSE"]
        wins = [e for e in closes if e.pnl_usd > 0]
        total_gas = sum(
            (e.verify or {}).get("gas_used") or 0
            for e in es
            if (e.verify or {}).get("status") == "ok"
        )
        verified = sum(1 for e in es if (e.verify or {}).get("status") == "ok")
        avg_gas = (total_gas / verified) if verified > 0 else 0.0
        avg_pnl = (sum(c.pnl_usd for c in closes) / len(closes)) if closes else 0.0
        win_rate = (len(wins) / len(closes)) if closes else 0.0
        current_params = es[-1].params if es else {}
        mdd = _max_drawdown(closes)
        s = StrategyStats(
            strategy=strat,
            trade_count=len(es),
            verified_count=verified,
            close_count=len(closes),
            win_count=len(wins),
            win_rate=win_rate,
            realized_pnl_usd=sum(c.pnl_usd for c in closes),
            avg_pnl_usd=avg_pnl,
            total_gas=total_gas,
            avg_gas_per_tx=avg_gas,
            max_drawdown_usd=mdd,
            current_params=current_params,
            first_seen=es[0].ts,
            last_seen=es[-1].ts,
        )
        s.verdict, s.verdict_reason = _verdict(s)
        out.append(s)
    out.sort(key=lambda s: -s.realized_pnl_usd)
    return out
