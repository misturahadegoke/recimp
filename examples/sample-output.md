# Example: Reflection + Advise Report

> Generated against a sample journal containing two strategies
> (12 trades each). See `SKILL.md` for the full command line.

```
================================================================
  AGENT REFLECTION REPORT — generated 2026-06-03T17:00:00Z
  Window: last 30 day(s)  |  Strategies: 2
================================================================

  Strategy: stablecoin-farming    [HEALTHY]
    Trades:       6  (verified 6, closed 3)
    Win rate:     66.7%  (2 winners)
    Realized P&L: $60.00  (avg $20.00/trade)
    Max drawdown: $30.00
    Gas:          total 390K  avg 65.0K/tx
    First seen:   2026-06-01T10:00:00Z
    Last seen:    2026-06-03T11:30:00Z
    Verdict:      Win rate 67% and P&L $60.00 are healthy.
    Params:       {"max_slippage_bps": 30, "size_usd": 1000, "stop_loss_bps": 200}
    Tuning:
      - size_usd: 1000 -> 1250  (conf 0.60)
          Win rate 67% and positive P&L with drawdown smaller than P&L. Scale up size_usd from 1000 to 1250 (≈25% larger).

  Strategy: perp-grid    [UNDERPERFORMING]
    Trades:       6  (verified 6, closed 3)
    Win rate:     33.3%  (1 winners)
    Realized P&L: $-75.00  (avg $-25.00/trade)
    Max drawdown: $75.00
    Gas:          total 720K  avg 120.0K/tx
    First seen:   2026-06-01T10:00:00Z
    Last seen:    2026-06-03T16:00:00Z
    Verdict:      Win rate 33% or P&L $-75.00 is below target. Tighten entry rules.
    Params:       {"max_drawdown_bps": 1000, "size_usd": 500, "stop_loss_bps": 500}
    Tuning:
      - stop_loss_bps: 500 -> 350  (conf 0.65)
          Win rate is 33%, below the 55% target. Tighten stop_loss_bps from 500 to 350 (≈30% smaller) to cut losers earlier.
```

## Reading the report

- **Strategy verdict** is the headline:
  - `HEALTHY` — win rate ≥ 50% and P&L positive.
  - `UNDERPERFORMING` — win rate below 50% or P&L negative.
  - `BROKEN` — both below threshold; advisor recommends disabling.
  - `INSUFFICIENT_DATA` — fewer than 5 closes; no verdict.
- **Realized P&L** is the sum of `pnl_usd` across all `CLOSE`
  entries in the window.
- **Max drawdown** is the worst peak-to-trough drop in
  cumulative P&L.
- **Tuning** lists the rule-based recommendations. Each
  includes the parameter, the proposed change, a confidence
  0–1, and a human-readable rationale.

## How to use this

1. Run `recimp record` after every trade to log it.
2. Run `recimp verify` periodically to confirm on-chain
   settlement.
3. Run `recimp reflect` (or `recimp advise`) to review.
4. Apply tuning recommendations manually — the advisor is a
   sanity check, not an autopilot.
