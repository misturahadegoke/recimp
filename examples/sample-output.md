# Example: Reflection + Advise Report

> Generated against the sample journal in `examples/sample-journal.jsonl`
> (3 strategies, 18 closes, last 30 days). Run with:
>
> ```
> python3 src/recimp.py advise --format text
> ```

========================================================================
  AGENT REFLECTION REPORT — generated 2026-07-09T11:07:46Z
  Window: last 30 day(s)  |  Strategies: 3
========================================================================

  Strategy: stablecoin-farming    [[32mHEALTHY[0m]
    Trades:       12  (verified 12, closed 6)
    Win rate:     66.7%  (4 winners)
    Realized P&L: $150.00  (avg $25.00/trade)
    Max drawdown: $30.00
    Gas:          total 780,000  avg 65,000.0/tx
    First seen:   2026-06-14T10:00:00Z
    Last seen:    2026-07-07T15:00:00Z
    Verdict:      WR 67% and P&L $150.00 are healthy
    Params:       {"size_usd": 1000, "stop_loss_bps": 200, "max_slippage_bps": 30}

  Strategy: perp-grid    [[31mBROKEN[0m]
    Trades:       12  (verified 12, closed 6)
    Win rate:     33.3%  (2 winners)
    Realized P&L: $-160.00  (avg $-26.67/trade)
    Max drawdown: $160.00
    Gas:          total 780,000  avg 65,000.0/tx
    First seen:   2026-06-15T10:00:00Z
    Last seen:    2026-07-08T18:00:00Z
    Verdict:      P&L $-160.00 and WR 2/6 below threshold
    Params:       {"size_usd": 500, "stop_loss_bps": 500, "max_drawdown_bps": 1000}
    Tuning:
      - enabled: True -> False  (conf 0.85)
          Strategy is BROKEN (P&L $-160.00, WR 2/6). Disable until you investigate.

  Strategy: small-cap-momentum    [[33mUNDERPERFORMING[0m]
    Trades:       12  (verified 12, closed 6)
    Win rate:     33.3%  (2 winners)
    Realized P&L: $220.00  (avg $36.67/trade)
    Max drawdown: $80.00
    Gas:          total 780,000  avg 65,000.0/tx
    First seen:   2026-06-11T10:00:00Z
    Last seen:    2026-07-08T18:00:00Z
    Verdict:      WR 33% or P&L $220.00 below target
    Params:       {"size_usd": 2000, "stop_loss_bps": 400, "max_drawdown_bps": 800}
    Tuning:
      - stop_loss_bps: 400 -> 280  (conf 0.65)
          WR is 33%, below the 55% target. Tighten stop_loss_bps from 400 to 280 (~30% smaller) to cut losers earlier.
      - max_drawdown_bps: 800 -> 640  (conf 0.70)
          Realized drawdown ($80.00) is large relative to cumulative P&L ($220.00). Tighten max_drawdown_bps from 800 to 640.

========================================================================
