---
name: recimp
description: >
  REQUIRED for any task where an AI agent needs to record its
  onchain actions, review its own performance per strategy, and
  propose parameter tuning based on the review. Invoke when the
  user asks the agent to "log this trade", "review your
  performance", "reflect on what worked", "tune the strategy",
  "show me your trade history", "compute my win rate", "what's
  my drawdown", or wants a structured per-strategy report
  including realized P&L, win rate, gas efficiency, and a
  rule-based tuning recommendation. Uses Python 3.9+ with the
  JSON-RPC client bundled in `src/rpc.py` (no Foundry, no
  third-party Python deps required). Writes to a JSONL journal
  on disk and reads back via `eth_getTransactionByHash` /
  `eth_getTransactionReceipt` against any EVM-compatible RPC
  URL (including Pharos Pacific mainnet and Atlantic testnet).
  Read-only — never accepts a private key.
version: 3.0.0
requires: read
bins: [python3, curl]
author: misturahadegoke
network: pharos
tags: [pharos, blockchain, agent-skill, memory, self-improvement, json-rpc]
agents: [claude, codex, gemini, openclaw, anvita-flow]
---


# RecImp — Recursive Self-Improvement Skill

A meta-skill for AI agents that trade onchain: log every action,
review the journal, and propose parameter tuning based on the review.

The skill ships four subcommands:

1. **`record`** — write one trade to `data/journal.jsonl` (timestamp, strategy, action, tx hash, expected P&L, params used).
2. **`verify`** — re-read each entry's tx hash via `eth_getTransactionReceipt` against any EVM-compatible JSON-RPC endpoint and attach confirmation status, block, and gas used.
3. **`reflect`** — per-strategy stats: realized P&L, win rate, max drawdown, average gas, plus a rule-based verdict (`HEALTHY` / `UNDERPERFORMING` / `BROKEN` / `INSUFFICIENT_DATA`).
4. **`advise`** — propose concrete parameter changes with a confidence 0–1 and a human-readable rationale.

## When to use

- The agent has just executed a trade and wants to log it.
- The user asks the agent to "review your performance".
- The user wants a per-strategy P&L report.
- The user wants a tuning recommendation.

## When NOT to use

- Strategy backtesting (this skill reads live journal entries, not historical simulation data).
- Cross-strategy portfolio optimization (use a dedicated portfolio optimizer).
- Off-chain-only strategies (the verifier is on-chain-aware).
- Sending transactions (this skill is read-only — use the Pharos Skill Engine for writes).

## Prerequisites

```bash
python3 --version   # 3.9+
```

The skill uses only the Python standard library (`urllib.request`, `json`, `argparse`, `dataclasses`). **No `pip install`, no Foundry, no third-party packages.** The runtime only needs `python3`.

For optional manual cross-checks via Foundry's `cast`, install Foundry separately:

```bash
curl -L https://foundry.paradigm.xyz | bash && foundryup
cast --version
```

The skill is **read-only** — no private key is required or accepted.

## Network configuration

Network RPC URLs and chain IDs are sourced from `assets/networks.json` (canonical Pharos Skill Engine schema). To add a new network, append a new object to the `networks` array and update `defaultNetwork` if needed.

| Network | Chain ID | RPC URL | Native |
|---|---|---|---|
| Pharos Atlantic Testnet | `688689` | `https://atlantic.dplabs-internal.com` | PHRS |
| Pharos Pacific Mainnet | `1672` | `https://rpc.pharos.xyz` | PROS |

CLI flag conventions:

- `--chain mainnet` → Pacific (1672)
- `--chain testnet` → Atlantic (688689)
- `--rpc-url <URL>` → override per call

## Inputs (CLI)

### `python src/recimp.py record`

| Field | Required | Description |
|---|---|---|
| `--strategy` | yes | Strategy name (e.g. `stablecoin-farming`) |
| `--action` | yes | `OPEN` / `CLOSE` / `REBALANCE` / `CLAIM` / `INIT` |
| `--tx-hash` | no | 0x tx hash (verified later) |
| `--symbol` | no | Asset symbol (e.g. `USDC`) |
| `--pnl-usd` | no | Realized P&L in USD (for `CLOSE`) |
| `--params` | no | JSON-encoded parameter dict at the time of trade |
| `--note` | no | Free-form note |
| `--journal PATH` | no | Override journal location |

### `python src/recimp.py verify`

| Field | Required | Description |
|---|---|---|
| `--rpc-url URL` | yes | JSON-RPC endpoint |
| `--chain mainnet\|testnet` | no | Network short name |
| `--strategy NAME` | no | Only verify one strategy |
| `--since ISO` | no | Only entries newer than this ISO 8601 timestamp |

### `python src/recimp.py reflect` / `advise`

| Field | Required | Description |
|---|---|---|
| `--rpc-url URL` | no | JSON-RPC endpoint (only used by `reflect` for context; `advise` is offline) |
| `--chain mainnet\|testnet` | no | Network short name |
| `--strategy NAME` | no | Only reflect on / advise for one strategy |
| `--window N` | no | Lookback in days (default `30`, `0` disables) |
| `--format text\|json\|markdown\|html` | no | Output format |
| `--out PATH` | no | Write to file instead of stdout |

## Outputs

`reflect` and `advise` both emit the same shape (per-strategy) with optional
tuning recommendations appended under `recommendations[]` in JSON mode, or
inline under "Recommended tuning" in HTML/Markdown mode.

Per-strategy fields:

- `strategy`, `trade_count`, `verified_count`, `close_count`
- `win_count`, `realized_pnl_usd`, `avg_pnl_usd`, `max_drawdown_usd`
- `total_gas`, `avg_gas_per_tx`, `first_seen`, `last_seen`
- `last_params` — most recent recorded param dict
- `verdict` — `HEALTHY` / `UNDERPERFORMING` / `BROKEN` / `INSUFFICIENT_DATA`
- `verdict_reason` — human-readable explanation
- `recommendations[]` — `[{param, old, new, confidence, rationale}]` (advise mode only)

## Capability index

| User need | Capability | Detailed instructions |
|---|---|---|
| Log a trade | `python src/recimp.py record --strategy ... --action ...` | See `Usage → 1. record` below |
| Confirm on-chain settlement | `python src/recimp.py verify --rpc-url ...` | See `Usage → 2. verify` |
| Per-strategy P&L report | `python src/recimp.py reflect --rpc-url ...` | Output in `text` / `json` / `markdown` / `html` |
| Tuning recommendation | `python src/recimp.py advise` | Offline; same data sources as `reflect` plus rule-based advisor |
| Cross-check tx status with Foundry | `cast receipt 0xHASH --rpc-url ...` | Optional; not required by the skill |

## Quick start

```bash
# 1. No install — pure stdlib. (Optional) Foundry for manual checks:
#    curl -L https://foundry.paradigm.xyz | bash && foundryup

# 2. Record a trade
python3 src/recimp.py record \
  --strategy stablecoin-farming \
  --action OPEN \
  --tx-hash 0xYourTxHash \
  --symbol USDC \
  --params '{"size_usd": 1000, "max_slippage_bps": 30}'

# 3. Verify on-chain confirmations
python3 src/recimp.py verify \
  --rpc-url https://rpc.pharos.xyz \
  --chain mainnet

# 4. Reflect on performance
python3 src/recimp.py reflect \
  --chain mainnet \
  --format markdown

# 5. Get tuning advice
python3 src/recimp.py advise \
  --format text
```

## Usage — annotated session

```bash
# Open a position
python3 src/recimp.py record --strategy stablecoin-farming --action OPEN \
  --tx-hash 0xabc... --symbol USDC \
  --params '{"size_usd": 1000, "stop_loss_bps": 200}'

# Close it (pnl_usd required to compute realized P&L)
python3 src/recimp.py record --strategy stablecoin-farming --action CLOSE \
  --tx-hash 0xdef... --symbol USDC --pnl-usd 50.0 \
  --params '{"size_usd": 1000, "stop_loss_bps": 200}'

# Re-read confirmations
python3 src/recimp.py verify --rpc-url https://rpc.pharos.xyz --chain mainnet

# Per-strategy report (text)
python3 src/recimp.py reflect --chain mainnet --format text

# Tuning recommendations (markdown, to a file)
python3 src/recimp.py advise --format markdown --out advise-report.md
```

## Agent invocation pattern

After every onchain action, call `record`. Periodically (or on user request),
call `verify` then `reflect` then `advise` — and surface the verdict, stats,
and tuning recommendations in your reply.

> **User:** "Review your trading performance on Pharos."
>
> **Agent:**
> 1. `python3 src/recimp.py verify --rpc-url https://rpc.pharos.xyz --chain mainnet`
> 2. `python3 src/recimp.py reflect --chain mainnet --format text`
> 3. `python3 src/recimp.py advise --format text`
> 4. Replies: "stablecoin-farming — HEALTHY, 12 trades, 67% win rate, +$342 realized, 0.003 PHRS gas. Verdict healthy. Tuning recommendation: raise `size_usd` 1000 → 1250 (conf 0.60)."

## General error handling

| Error scenario | CLI signature | Handling |
|---|---|---|
| Journal doesn't exist yet | `{'checked': 0, 'note': 'journal not found'}` | First-run case; call `record` first to bootstrap |
| RPC unreachable | Exit code 3 (`RpcError`) | Ask user for a working RPC URL |
| Bad RPC URL | HTTP error wrapped in `RpcError` | Same as above |
| RPC rate-limited (HTTP 429) | Auto-retry with exponential backoff (0.4s / 0.8s / 1.6s / 3.2s) | Built-in; surface result if it still fails after 4 retries |
| `<5` closes for a strategy | `verdict: INSUFFICIENT_DATA` | Normal — advisor returns no recommendations |
| `--format` typo | argparse usage error | Built-in |
| Missing required `--strategy` | argparse usage error | Built-in |

## Security reminders

- **Private key protection** — the skill is read-only and never accepts a private key. Do not paste keys into chat.
- **Network confirmation** — `verify` writes to disk but does not write onchain. If a future version adds a write path, confirm the network (`mainnet` vs `testnet`) with the user before running.
- **No external API** — the skill talks only to whatever JSON-RPC endpoint you give it via `--rpc-url`. No third-party services.
- **Journal is local** — the JSONL journal is local to the runtime. For production, back it up to durable storage (S3 / IPFS) before the agent's host dies.

## Write operation pre-checks

This skill is **read-only** and never submits a transaction, so the full 4-step write pre-check is **not applicable**. If a future version adds a write path, the pre-checks must include:

1. **Private Key Check** — `--private-key` / `$PRIVATE_KEY` must be set; warn if the key has zero balance.
2. **Derive Public Address** — `cast wallet address`; confirm the key is for the intended network.
3. **Network Confirmation** — prompt the user with "You are about to write to Pacific mainnet. Continue? (y/N)".
4. **Automatic Balance Check** — `cast balance`; if below the operation cost + gas, abort with a clear error.

## Limitations

- `pnl_usd` is whatever the agent (or upstream trading engine) reports at close time. The verifier only checks **whether** a tx confirmed, not **what** the price was. Re-deriving P&L from on-chain Transfer events is on the roadmap but not implemented.
- Verdict thresholds (5 closes, 40% / 50% WR) are opinionated and live in `src/reflection.py:_verdict`.
- Advisory rules are static, additive, and don't resolve conflicts (a strategy can get "tighten stop" and "scale up" simultaneously — pick one).
- The advisor does not adapt to regime changes (bull vs bear, sudden liquidity events, protocol-specific exploits).
- Window is inclusive — `--window 0` disables it; default is `30` days.
