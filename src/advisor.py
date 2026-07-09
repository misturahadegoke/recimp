"""
Rule-based tuning advisor.

Five rules from references/tuning-rules.md. Each returns zero or more
TuningRecommendation with a (param, old, new, confidence, rationale).
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Optional

from reflection import StrategyStats


@dataclass
class TuningRecommendation:
    param: str
    old: object
    new: object
    confidence: float
    rationale: str

    def to_dict(self) -> dict:
        return asdict(self)


# --- R0: BROKEN short-circuit ----------------------------------------------

def _r0_broken(stats: StrategyStats) -> list[TuningRecommendation]:
    if stats.verdict != "BROKEN":
        return []
    return [
        TuningRecommendation(
            param="enabled",
            old=True,
            new=False,
            confidence=0.85,
            rationale=(
                f"Strategy is BROKEN (P&L ${stats.realized_pnl_usd:.2f}, "
                f"WR {stats.win_count}/{stats.close_count}). "
                "Disable until you investigate."
            ),
        )
    ]


# --- R1: Tighten stop-loss on low win rate ---------------------------------

def _r1_stop_loss(stats: StrategyStats) -> list[TuningRecommendation]:
    if stats.close_count < 5:
        return []
    if not stats.last_params or "stop_loss_bps" not in stats.last_params:
        return []
    wr = stats.win_count / max(1, stats.close_count)
    if wr >= 0.55:
        return []

    old = stats.last_params["stop_loss_bps"]
    try:
        old_v = float(old)
    except (TypeError, ValueError):
        return []
    new_v = max(10, int(old_v * 0.7))  # floor at 10 bps
    if new_v >= old_v:
        return []
    return [
        TuningRecommendation(
            param="stop_loss_bps",
            old=old,
            new=new_v,
            confidence=0.65,
            rationale=(
                f"WR is {wr:.0%}, below the 55% target. Tighten stop_loss_bps "
                f"from {old} to {new_v} (~30% smaller) to cut losers earlier."
            ),
        )
    ]


# --- R2: Scale up on high WR + low drawdown ---------------------------------

def _r2_scale_up(stats: StrategyStats) -> list[TuningRecommendation]:
    if "size_usd" not in (stats.last_params or {}):
        return []
    if stats.close_count < 5:
        return []
    wr = stats.win_count / max(1, stats.close_count)
    if wr <= 0.7:
        return []
    if stats.realized_pnl_usd <= 0:
        return []
    if stats.max_drawdown_usd >= max(stats.realized_pnl_usd, 1):
        return []

    old = stats.last_params["size_usd"]
    try:
        old_v = float(old)
    except (TypeError, ValueError):
        return []
    new_v = int(old_v * 1.25)
    return [
        TuningRecommendation(
            param="size_usd",
            old=old,
            new=new_v,
            confidence=0.60,
            rationale=(
                f"WR {wr:.0%} and positive P&L with drawdown smaller than P&L. "
                f"Scale up size_usd from {old} to {new_v} (~25% larger)."
            ),
        )
    ]


# --- R3: Tighten max-drawdown cap -----------------------------------------

def _r3_drawdown_cap(stats: StrategyStats) -> list[TuningRecommendation]:
    if "max_drawdown_bps" not in (stats.last_params or {}):
        return []
    if stats.max_drawdown_usd <= 0:
        return []
    realized = max(stats.realized_pnl_usd, 1.0)
    if stats.max_drawdown_usd <= 0.3 * realized:
        return []

    old = stats.last_params["max_drawdown_bps"]
    try:
        old_v = float(old)
    except (TypeError, ValueError):
        return []
    new_v = max(50, int(old_v * 0.8))  # floor at 50 bps
    if new_v >= old_v:
        return []
    return [
        TuningRecommendation(
            param="max_drawdown_bps",
            old=old,
            new=new_v,
            confidence=0.70,
            rationale=(
                f"Realized drawdown (${stats.max_drawdown_usd:.2f}) is large "
                f"relative to cumulative P&L (${stats.realized_pnl_usd:.2f}). "
                f"Tighten max_drawdown_bps from {old} to {new_v}."
            ),
        )
    ]


# --- R4: Add a min-profit floor when gas eats P&L --------------------------

def _r4_gas_floor(stats: StrategyStats) -> list[TuningRecommendation]:
    if stats.avg_pnl_usd <= 0:
        return []
    if stats.avg_gas_per_tx <= 0:
        return []
    # rough gas → native token (18 decimal)
    gas_native = stats.avg_gas_per_tx / 1e18
    if gas_native <= 0.10 * stats.avg_pnl_usd:
        return []
    new_v = int(stats.avg_pnl_usd * 0.5)
    if new_v <= 0:
        return []
    return [
        TuningRecommendation(
            param="min_profit_usd",
            old=None,
            new=new_v,
            confidence=0.55,
            rationale=(
                f"Gas ({stats.avg_gas_per_tx:.0f} ~= {gas_native:.6f} native) "
                f"is >10% of avg P&L (${stats.avg_pnl_usd:.2f}). "
                f"Set min_profit_usd={new_v} so marginal trades get skipped."
            ),
        )
    ]


_RULES = [_r0_broken, _r1_stop_loss, _r2_scale_up, _r3_drawdown_cap, _r4_gas_floor]


def advise_for_strategy(stats: StrategyStats) -> list[TuningRecommendation]:
    """Run all rules in order. Early BROKEN short-circuits the rest (per docs)."""
    if stats.verdict == "BROKEN":
        return _r0_broken(stats)

    out: list[TuningRecommendation] = []
    for rule in _RULES:
        out.extend(rule(stats))
    return out


def advise_all(
    stats_list: list[StrategyStats],
    *,
    strategy: str | None = None,
) -> list[dict]:
    """Return advices as a flat list of {strategy, recommendations:[…]} dicts."""
    out: list[dict] = []
    for s in stats_list:
        if strategy and s.strategy != strategy:
            continue
        recs = advise_for_strategy(s)
        out.append(
            {
                "strategy": s.strategy,
                "verdict": s.verdict,
                "recommendations": [r.to_dict() for r in recs],
            }
        )
    return out
