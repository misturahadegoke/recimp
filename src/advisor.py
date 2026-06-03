"""
advisor.py - Rule-based tuning recommendations.

Given per-strategy stats, produce a list of proposed parameter
changes. Each change has:
  - param:     name of the param
  - old:       current value
  - new:       proposed value
  - confidence: 0..1
  - rationale: human-readable explanation

The rules are deliberately simple. A future version could swap
in a Bayesian posterior or an LLM-based proposal, but the
auditable rule-based version is the right starting point.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from reflection import (
    StrategyStats,
    VERDICT_HEALTHY,
    VERDICT_UNDERPERFORMING,
    VERDICT_BROKEN,
    VERDICT_INSUFFICIENT_DATA,
)


@dataclass
class TuningRecommendation:
    param: str
    old: Any
    new: Any
    confidence: float
    rationale: str


# A few rules. The advisor is intentionally conservative —
# each rule has a clear trigger and a clear output.
def advise_for_strategy(s: StrategyStats) -> List[TuningRecommendation]:
    recs: List[TuningRecommendation] = []
    if s.verdict == VERDICT_INSUFFICIENT_DATA:
        return recs
    if s.verdict == VERDICT_BROKEN:
        recs.append(TuningRecommendation(
            param="enabled",
            old=True,
            new=False,
            confidence=0.85,
            rationale=f"Strategy is BROKEN (win_rate={s.win_rate:.0%}, "
                     f"pnl=${s.realized_pnl_usd:.2f}). Disable until the "
                     f"agent investigates the cause.",
        ))
        return recs

    # Rule: tighten stop_loss when win rate is low
    if "stop_loss_bps" in s.current_params and s.win_rate < 0.55 and s.close_count >= 5:
        old = s.current_params["stop_loss_bps"]
        new = max(10, int(old * 0.7))
        recs.append(TuningRecommendation(
            param="stop_loss_bps",
            old=old,
            new=new,
            confidence=0.65,
            rationale=f"Win rate is {s.win_rate:.0%}, below the 55% target. "
                     f"Tighten stop_loss_bps from {old} to {new} (≈30% smaller) "
                     f"to cut losers earlier.",
        ))

    # Rule: scale up position size when win rate is high
    if "size_usd" in s.current_params and s.win_rate > 0.7 and s.realized_pnl_usd > 0 and s.max_drawdown_usd < s.realized_pnl_usd:
        old = s.current_params["size_usd"]
        new = int(old * 1.25)
        recs.append(TuningRecommendation(
            param="size_usd",
            old=old,
            new=new,
            confidence=0.6,
            rationale=f"Win rate {s.win_rate:.0%} and positive P&L with "
                     f"drawdown smaller than P&L. Scale up size_usd from "
                     f"{old} to {new} (≈25% larger).",
        ))

    # Rule: cap drawdown exposure
    if "max_drawdown_bps" in s.current_params and s.max_drawdown_usd > 0 and s.avg_gas_per_tx > 0:
        # If realized drawdown is more than 30% of cumulative P&L,
        # tighten the cap.
        if s.max_drawdown_usd > 0.3 * max(1.0, s.realized_pnl_usd):
            old = s.current_params["max_drawdown_bps"]
            new = max(50, int(old * 0.8))
            recs.append(TuningRecommendation(
                param="max_drawdown_bps",
                old=old,
                new=new,
                confidence=0.7,
                rationale=f"Max drawdown ${s.max_drawdown_usd:.2f} is >30% of "
                         f"cumulative P&L. Tighten max_drawdown_bps from "
                         f"{old} to {new} (≈20% smaller).",
            ))

    # Rule: gas efficiency — if avg_gas is high relative to avg_pnl,
    # reduce trade frequency.
    if s.avg_pnl_usd > 0 and s.avg_gas_per_tx > 0:
        # Assume a rough $1 = 1e9 wei = 1 gwei at $1/PROS, which is
        # good enough for a heuristic.
        gas_native = s.avg_gas_per_tx / 1e18
        if gas_native > 0.10 * s.avg_pnl_usd:
            recs.append(TuningRecommendation(
                param="min_profit_usd",
                old=0,
                new=int(s.avg_pnl_usd * 0.5),
                confidence=0.55,
                rationale=f"Average gas ({gas_native:.4f} native) is >10% of "
                         f"average P&L per trade (${s.avg_pnl_usd:.2f}). Add a "
                         f"`min_profit_usd` floor to skip marginal trades.",
            ))

    return recs


def advise_all(stats: List[StrategyStats]) -> Dict[str, List[TuningRecommendation]]:
    out: Dict[str, List[TuningRecommendation]] = {}
    for s in stats:
        recs = advise_for_strategy(s)
        if recs:
            out[s.strategy] = recs
    return out
