# P&L math

This file documents how `src/reflection.py` computes realized
P&L, win rate, max drawdown, and gas totals from the journal.

## Inputs

Each `CLOSE` journal entry carries a `pnl_usd` field that the
agent (or the upstream trading engine) sets at close time. The
reflection engine treats this as the realized P&L for that trade.
There is no on-chain re-derivation — see the SKILL.md
"Limitations" for the rationale.

## Per-trade metrics

- `pnl_usd` — net USD value gained (positive) or lost (negative)
  on the closed position.
- `gas_used` — total gas consumed by the on-chain transactions
  that opened and closed the position (only attached to
  verified entries; the verifier reads it from the tx receipt).
- `win` — `True` iff `pnl_usd > 0`.

## Per-strategy metrics

Aggregated across all entries in the strategy (within the
lookback window).

### Trade count

```
trade_count = number of journal entries with this strategy
```

Verified count is the number of entries whose `verify.status ==
"ok"`. Strategies with few verified entries are noisier.

### Win rate

```
win_count = number of CLOSE entries with pnl_usd > 0
close_count = number of CLOSE entries (regardless of sign)
win_rate  = win_count / close_count    (0 if close_count == 0)
```

### Realized P&L

```
realized_pnl_usd = sum of pnl_usd for all CLOSE entries
```

Includes winners and losers. Negative if the strategy lost
money over the window.

### Average P&L per trade

```
avg_pnl_usd = realized_pnl_usd / close_count
```

### Max drawdown

Walk the `CLOSE` entries in chronological order, accumulating
P&L into a running sum. Track the running peak. The largest
peak-to-trough drop is the max drawdown.

```
cum = 0
peak = 0
max_dd = 0
for each close in chronological order:
    cum += close.pnl_usd
    if cum > peak: peak = cum
    dd = peak - cum
    if dd > max_dd: max_dd = dd
```

Returns 0.0 if no closes or if cumulative P&L never went down.

### Gas

```
total_gas      = sum of verify.gas_used for verified entries
avg_gas_per_tx = total_gas / verified_count   (0 if no verified)
```

The reflection engine doesn't convert gas to USD — that's a
downstream concern (use a native-token-price feed). The advisor
uses a very rough heuristic: assumes 1 native = 1 USD for the
gas-vs-pnl check, which is good enough to flag strategies
where gas is eating a meaningful share of profit.

## Verdict

```
if close_count < 5:
    INSUFFICIENT_DATA
elif realized_pnl_usd < 0 AND win_rate < 0.4:
    BROKEN
elif win_rate < 0.5 OR realized_pnl_usd < 0:
    UNDERPERFORMING
else:
    HEALTHY
```

The thresholds (5 trades, 40% win rate, 50% win rate) are
opinionated. Tune them in `src/reflection.py:_verdict` for
your protocol.

## Worked example

Suppose a strategy has these CLOSE P&L values, in order:

```
+50, +30, -20, +40, -50, +60, -10, +25, -15, +35
```

That's 10 closes, 6 winners → win_rate = 0.60.

```
realized_pnl_usd = 50+30-20+40-50+60-10+25-15+35 = 145
avg_pnl_usd      = 14.5
```

Cumulative P&L: 50, 80, 60, 100, 50, 110, 100, 125, 110, 145.
Peak-to-trough drops: 0, 0, 20, 0, 50, 0, 10, 0, 15, 0.
max_dd = 50.

Verdict: HEALTHY (win rate 60%, P&L +$145).

## Limitations

- P&L is whatever the agent reports. If the agent double-counts
  a fee or misses a slippage event, the reflection will inherit
  the error. A future version could re-derive P&L from on-chain
  Transfer events, but that's a much heavier build.
- The 30-day default window may not match your strategy's
  seasonality. Pass `--window 0` to disable the window.
- Strategies with very few trades (< 5) are flagged
  `INSUFFICIENT_DATA`. The advisor returns no recommendations
  in that case, which is intentional.
