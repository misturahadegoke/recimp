"""
Reflection engine — per-strategy stats from the journal.

Computes trade_count, win_rate, realized_pnl_usd, avg_pnl_usd,
max_drawdown_usd, total/avg gas, first/last_seen, and a verdict.

Verdict rule (from references/pnl-math.md):
    if close_count < 5:                  INSUFFICIENT_DATA
    elif PnL<0 and WR<0.4:               BROKEN
    elif WR<0.5 OR PnL<0:                 UNDERPERFORMING
    else:                                HEALTHY
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta, timezone
from typing import Iterable


@dataclass
class StrategyStats:
    strategy: str
    trade_count: int = 0          # all entries (OPEN+CLOSE+REB+CLAIM)
    verified_count: int = 0
    close_count: int = 0
    win_count: int = 0
    realized_pnl_usd: float = 0.0
    avg_pnl_usd: float = 0.0
    max_drawdown_usd: float = 0.0
    total_gas: int = 0
    avg_gas_per_tx: float = 0.0
    first_seen: str = ""
    last_seen: str = ""
    last_params: dict = field(default_factory=dict)
    verdict: str = "INSUFFICIENT_DATA"
    verdict_reason: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def _parse_ts(ts: str) -> datetime:
    try:
        return datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except Exception:
        return datetime.fromtimestamp(0, tz=timezone.utc)


def _in_window(ts: str, window_days: int | None) -> bool:
    if not window_days:
        return True
    when = _parse_ts(ts)
    return when >= datetime.now(timezone.utc) - timedelta(days=window_days)


def _verdict(stats: StrategyStats) -> tuple[str, str]:
    """Returns (verdict, reason)."""
    if stats.close_count < 5:
        return ("INSUFFICIENT_DATA", f"only {stats.close_count} closes; need ≥5")
    if stats.realized_pnl_usd < 0 and stats.win_count / max(1, stats.close_count) < 0.4:
        return ("BROKEN", f"P&L ${stats.realized_pnl_usd:.2f} and WR "
                          f"{stats.win_count}/{stats.close_count} below threshold")
    wr = stats.win_count / max(1, stats.close_count)
    if wr < 0.5 or stats.realized_pnl_usd < 0:
        return ("UNDERPERFORMING", f"WR {wr:.0%} or P&L ${stats.realized_pnl_usd:.2f} below target")
    return ("HEALTHY", f"WR {wr:.0%} and P&L ${stats.realized_pnl_usd:.2f} are healthy")


def compute_strategy_stats(
    entries: Iterable[dict],
    strategy: str,
    *,
    window_days: int | None = 30,
) -> StrategyStats:
    """Compute stats for one strategy.

    Window is inclusive: an entry's `ts` must fall within the last `window_days`
    days. Pass window_days=0 (or None) to disable the window.
    """
    stats = StrategyStats(strategy=strategy)

    closes_in_order: list[dict] = []

    for e in entries:
        if e.get("strategy") != strategy:
            continue
        if not _in_window(e.get("ts", ""), window_days):
            continue

        stats.trade_count += 1
        stats.last_seen = e.get("ts") or stats.last_seen
        if not stats.first_seen:
            stats.first_seen = e.get("ts", "")

        if e.get("action") == "CLOSE":
            stats.close_count += 1
            try:
                pnl = float(e.get("pnl_usd", 0.0) or 0.0)
            except (TypeError, ValueError):
                pnl = 0.0
            stats.realized_pnl_usd += pnl
            if pnl > 0:
                stats.win_count += 1
            closes_in_order.append(e)

        v = e.get("verify", {}) or {}
        if v.get("status") == "ok":
            stats.verified_count += 1
            try:
                stats.total_gas += int(v.get("gas_used", 0) or 0)
            except (TypeError, ValueError):
                pass

        # capture most recent params if present
        if e.get("params"):
            stats.last_params = dict(e["params"])

    # avg_pnl
    if stats.close_count:
        stats.avg_pnl_usd = stats.realized_pnl_usd / stats.close_count

    # max drawdown (peak-to-trough on chronological closes)
    if closes_in_order:
        closes_in_order.sort(key=lambda x: x.get("ts", ""))
        peak = 0.0
        cum = 0.0
        max_dd = 0.0
        for c in closes_in_order:
            try:
                pnl = float(c.get("pnl_usd", 0.0) or 0.0)
            except (TypeError, ValueError):
                pnl = 0.0
            cum += pnl
            if cum > peak:
                peak = cum
            dd = peak - cum
            if dd > max_dd:
                max_dd = dd
        stats.max_drawdown_usd = max_dd

    # avg gas / verified
    if stats.verified_count:
        stats.avg_gas_per_tx = stats.total_gas / stats.verified_count

    stats.verdict, stats.verdict_reason = _verdict(stats)
    return stats


def compute_all(
    entries: Iterable[dict],
    *,
    strategy: str | None = None,
    window_days: int | None = 30,
) -> list[StrategyStats]:
    """Compute stats for every strategy, or one if `strategy` is given."""
    entries = list(entries)
    if strategy:
        return [compute_strategy_stats(entries, strategy, window_days=window_days)]

    names: list[str] = []
    seen: set[str] = set()
    for e in entries:
        s = e.get("strategy")
        if s and s not in seen:
            seen.add(s)
            names.append(s)

    return [
        compute_strategy_stats(entries, name, window_days=window_days) for name in names
    ]
