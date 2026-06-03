# Tuning rules

This file documents the rule-based tuning advisor in
`src/advisor.py`. Every rule is a small, auditable function
that takes a `StrategyStats` and returns zero or more
`TuningRecommendation`s.

## Why rule-based, not ML?

Three reasons:

1. **Auditable.** A human can read a rule in 30 seconds. A
   model trained on a few dozen strategies is opaque.
2. **Cheap.** No GPU, no data pipeline, no training loop.
3. **Reversible.** Each recommendation is a discrete
   (old → new, confidence, rationale) tuple that the agent (or
   the user) can accept, reject, or modify.

A future version could swap in a Bayesian posterior over
parameter values — but it should run *alongside* the rules,
not replace them.

## Rules

The advisor has five rules. They run in order, and an early
`BROKEN` verdict short-circuits the rest (we don't propose
parameter tweaks for a strategy we just told you to disable).

### R0: BROKEN short-circuit

Trigger: `verdict == "BROKEN"`.
Recommendation: `enabled: True → False` (confidence 0.85).
Rationale: strategy is losing money with low win rate. Disable
until the agent investigates.

### R1: Tighten stop-loss on low win rate

Trigger: `stop_loss_bps` in `current_params`, `win_rate < 0.55`,
`close_count >= 5`.
Recommendation: `stop_loss_bps *= 0.7` (i.e. 30% smaller),
floor at 10 bps. Confidence 0.65.
Rationale: a low win rate is often paired with wide stops.
Tightening them cuts losers without changing the entry signal.

### R2: Scale up on high win rate + low drawdown

Trigger: `size_usd` in `current_params`, `win_rate > 0.7`,
`realized_pnl_usd > 0`, `max_drawdown_usd < realized_pnl_usd`.
Recommendation: `size_usd *= 1.25`. Confidence 0.6.
Rationale: a strategy that's winning and not drawing down hard
is probably under-sized.

### R3: Tighten max drawdown cap

Trigger: `max_drawdown_bps` in `current_params`,
`max_drawdown_usd > 0.3 * max(1, realized_pnl_usd)`.
Recommendation: `max_drawdown_bps *= 0.8`, floor at 50 bps.
Confidence 0.7.
Rationale: if the realized drawdown is large relative to the
cumulative P&L, the strategy is closer to a wipeout than the
agent realizes.

### R4: Add a min-profit floor when gas eats P&L

Trigger: `avg_pnl_usd > 0`, `avg_gas_per_tx > 0`, and
`gas_native > 0.10 * avg_pnl_usd` (where `gas_native =
avg_gas_per_tx / 1e18`, a rough conversion to native-token
units assuming 18-decimals).
Recommendation: `min_profit_usd = int(avg_pnl_usd * 0.5)`.
Confidence 0.55.
Rationale: if gas is more than 10% of the average trade's
profit, the strategy is over-trading. Add a profit floor so
marginal trades get skipped.

## Adding a new rule

1. Add a function to `src/advisor.py` that takes a
   `StrategyStats` and returns a `list[TuningRecommendation]`.
2. Wire it into `advise_for_strategy`.
3. Add the rule's logic to this file.

A good rule has:
- a **clear trigger** (verifiable from the stats alone),
- a **clear output** (specific param + specific new value),
- a **human-readable rationale** (so the agent can explain it
  to the user),
- a **bounded confidence** (0.5–0.85; below 0.5 isn't worth
  surfacing).

## Limitations

- The rules are *additive* — they don't compete. A strategy
  can get a "tighten stop_loss" and a "scale up size" at the
  same time, which would conflict. The advisor does not
  attempt to resolve such conflicts; the user (or a higher
  layer) should pick one.
- The rules are static. They do not adapt to regime changes
  (a strategy that loses in a bull market might do great in
  a bear market). The advisor is a quick sanity check, not
  a portfolio manager.
- The advisor assumes the `params` dict is the source of truth
  for "current settings". If the agent's live config has
  drifted from the last recorded `params`, the recommendations
  may be stale.
