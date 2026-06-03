---
name: recursive-self-improvement
description: >
  REQUIRED for any task where an AI agent needs to record its
  onchain actions, review its own performance per strategy, and
  propose parameter tuning based on the review. Invoke when the
  user asks the agent to "log this trade", "review your
  performance", "reflect on what worked", "tune the strategy",
  "show me your trade history", "compute my win rate", "what's
  my drawdown", or wants a structured per-strategy report
  including realized P&L, win rate, gas efficiency, and a
  rule-based tuning recommendation. Use the bundled
  `src/recimp.py` engine which writes to a JSONL journal
  on disk and reads back via `eth_getTransactionByHash` /
  `eth_getTransactionReceipt` against any EVM-compatible RPC
  URL (including Pharos Pacific mainnet and Atlantic testnet).
  Do not attempt agent self-review or tuning without reading
  this skill.
version: 0.1.0
requires:
  - python >= 3.9
  - requests
  - anyBins:
      - cast   # optional, used for manual cross-check of tx status
      - jq     # optional, used for ergonomic RPC URL extraction
---

# Recursive Self-Improvement Skill

A meta-skill for AI agents that trade onchain: log every action,
review the journal, and propose parameter tuning based on the
review.

The skill ships four pieces:

1. **Journal** — an append-only `data/journal.jsonl` file where
   the agent records every trade (entry: timestamp, strategy,
   action, tx hash, expected P&L, params used).
2. **Verifier** — re-reads each journal entry's tx hash via
   `eth_getTransactionReceipt` and attaches confirmation status,
   block, and actual gas used.
3. **Reflection engine** — for each strategy, computes realized
   P&L, win rate, average gas cost, max drawdown, and a
   rule-based health verdict.
4. **Tuning advisor** — based on the rolling stats, proposes
   concrete parameter changes (e.g. "raise max_position_size by
   25%" or "tighten stop_loss to 2.5%") with a confidence 0–1
   and a human-readable rationale.

## When to use

- The agent has just executed a trade and wants to log it.
- The user asks the agent to "review your performance".
- The user wants a per-strategy P&L report.
- The user wants a tuning recommendation.

## When NOT to use

- Strategy backtesting (this skill reads live journal entries,
  not historical simulation data).
- Cross-strategy portfolio optimization (use a dedicated
  portfolio optimizer).
- Off-chain-only strategies (the verifier is on-chain-aware).

## Inputs

The CLI exposes four subcommands:

### `recimp record`

| Field             | Required | Description                                       |
|-------------------|----------|---------------------------------------------------|
| `--strategy`      | yes      | Strategy name (e.g. `stablecoin-farming`)         |
| `--action`        | yes      | One of `OPEN`, `CLOSE`, `REBALANCE`, `CLAIM`      |
| `--tx-hash`       | no       | 0x tx hash (verify later)                         |
| `--symbol`        | no       | Asset symbol (e.g. `USDC-PROS LP`)                |
| `--pnl-usd`       | no       | Realized P&L in USD (for CLOSE actions)           |
| `--params`        | no       | JSON-encoded parameter dict at the time of trade  |
| `--note`          | no       | Free-form note                                    |

### `recimp verify`

| Field             | Required | Description                                       |
|-------------------|----------|---------------------------------------------------|
| `--rpc-url`       | yes      | JSON-RPC endpoint                                 |
| `--strategy`      | no       | Only verify a specific strategy                   |
| `--since`         | no       | Only verify entries newer than this ISO 8601 ts   |

### `recimp reflect`

| Field             | Required | Description                                       |
|-------------------|----------|---------------------------------------------------|
| `--rpc-url`       | yes      | JSON-RPC endpoint (for native price reference)     |
| `--strategy`      | no       | Only reflect on a specific strategy               |
| `--window`        | no       | Lookback window in days (default 30)              |
| `--format`        | no       | `text`, `json`, `markdown`, `html`                |

### `recimp advise`

| Field             | Required | Description                                       |
|-------------------|----------|---------------------------------------------------|
| `--rpc-url`       | yes      | JSON-RPC endpoint (for native price reference)    |
| `--strategy`      | no       | Only advise a specific strategy                   |
| `--format`        | no       | `text`, `json`, `markdown`, `html`                |

## Outputs

A structured report with:

- Per-strategy stats: trade count, win rate, realized P&L,
  average gas, max drawdown, current params.
- Per-strategy health verdict: `HEALTHY` / `UNDERPERFORMING` /
  `BROKEN` / `INSUFFICIENT_DATA`.
- Per-strategy tuning recommendation: list of param changes,
  each with `param`, `old`, `new`, `confidence`, `rationale`.

## Quick start

```bash
# 1. Install
pip install -r requirements.txt

# 2. Record a trade
python src/recimp.py record \
  --strategy stablecoin-farming \
  --action OPEN \
  --tx-hash 0xYourTxHash \
  --symbol USDC \
  --params '{"size_usd": 1000, "max_slippage_bps": 30}'

# 3. Verify on-chain confirmations
python src/recimp.py verify \
  --rpc-url https://rpc.pharos.xyz

# 4. Reflect on performance
python src/recimp.py reflect \
  --rpc-url https://rpc.pharos.xyz

# 5. Get tuning advice
python src/recimp.py advise \
  --rpc-url https://rpc.pharos.xyz
```

## Agent invocation pattern

When the agent executes a trade, it should immediately call
`recimp record` to log it. Periodically (or on user request),
it calls `recimp verify && recimp reflect && recimp advise`,
surfaces the result, and (with user approval) applies the
tuning.

A typical session:

> User: "Review your trading performance on Pharos."
>
> Agent:
> 1. Runs `recimp verify --rpc-url https://rpc.pharos.xyz`
> 2. Runs `recimp reflect --rpc-url https://rpc.pharos.xyz`
> 3. Runs `recimp advise --rpc-url https://rpc.pharos.xyz`
> 4. Surfaces the report: "Over 30 days, strategy X had 12
>    trades, 67% win rate, +$342 realized, 0.003 ETH gas.
>    Verdict: HEALTHY. Tuning recommendation: raise
>    max_position_size from $1000 to $1250 (conf 0.62)."

## Error handling

| Error                  | Cause                          | Action |
|------------------------|--------------------------------|--------|
| `journal not found`    | First run                      | Create an empty journal via `recimp record --strategy init` |
| `tx not found`         | Wrong hash or chain            | Tell the user; entry stays "pending" in the journal |
| `rpc unreachable`      | Bad / dead RPC URL             | Ask user for a working RPC |
| `insufficient data`    | < 5 trades in the strategy     | Verdict returns `INSUFFICIENT_DATA`; no tuning proposed |

## Limitations

- P&L is computed from agent-supplied `--pnl-usd` values, not
  re-derived from on-chain state. The verifier only checks
  *whether* a tx confirmed, not *what* the price was.
- The tuning advisor is rule-based. It will not catch regime
  changes (bull vs bear), sudden liquidity events, or
  protocol-specific exploits. Treat its output as one input,
  not a final answer.
- The journal is local. If the agent's host dies, the journal
  dies with it. Back up `data/journal.jsonl` to a durable
  store (S3, IPFS) in production.
