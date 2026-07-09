# RecImp — Recursive Self-Improvement for Onchain Agents

> A meta-skill that lets an AI agent log its onchain actions,
> review its own performance per strategy, and propose
> parameter tuning based on the review.

[![python](https://img.shields.io/badge/python-3.9%2B-blue)]()
[![license](https://img.shields.io/badge/license/MIT--0-green)]()
[![rpc](https://img.shields.io/badge/RPC-JSON--RPC%20%7C%20EVM-orange)]()

## Overview

RecImp is a "meta" skill for agents that trade onchain. It
ships four pieces:

1. **Journal** — an append-only `data/journal.jsonl` file where
   the agent records every trade (timestamp, strategy, action,
   tx hash, expected P&L, params used).
2. **Verifier** — re-reads each journal entry's tx hash via
   `eth_getTransactionReceipt` and attaches confirmation
   status, block, and actual gas used.
3. **Reflection engine** — for each strategy, computes realized
   P&L, win rate, max drawdown, gas efficiency, and a
   rule-based health verdict.
4. **Tuning advisor** — proposes concrete parameter changes
   with a confidence 0–1 and a human-readable rationale.

It works against any EVM-compatible JSON-RPC endpoint and ships
with first-class support for the Pharos networks (see
[Supported networks](#supported-networks)).

## Features

- **Four subcommands** — `record`, `verify`, `reflect`, `advise`
  cover the full self-improvement loop.
- **Append-only journal** — JSONL, atomic writes, no external DB.
- **On-chain verification** — every recorded tx is re-read via
  the chain's RPC to confirm inclusion and capture gas used.
- **Per-strategy stats** — win rate, realized P&L, max
  drawdown, gas, current params, first/last seen.
- **Four-tier verdict** — `HEALTHY` / `UNDERPERFORMING` /
  `BROKEN` / `INSUFFICIENT_DATA`.
- **Rule-based tuning** — five auditable rules, each with a
  trigger, output, confidence, and rationale.
- **Multi-format output** — text (with ANSI colors), JSON,
  Markdown, or HTML.
- **Read-only** — never accepts a private key.
- **Zero Python deps** — runs on the stdlib (`urllib.request`,
  `json`, `argparse`, `dataclasses`). No `pip install` step.

## Supported networks

The tool runs against any EVM-compatible JSON-RPC endpoint for
on-chain verification. The following networks are explicitly
supported out of the box and used in the examples below.

| Network                 | Chain ID | RPC URL                                | Native token | Explorer                          |
|-------------------------|----------|----------------------------------------|--------------|-----------------------------------|
| Pharos Pacific Mainnet  | `1672`   | `https://rpc.pharos.xyz`               | PROS         | https://www.pharosscan.xyz/       |
| Pharos Atlantic Testnet | `688689` | `https://atlantic.dplabs-internal.com` | PHRS         | https://atlantic.pharosscan.xyz/  |

You can target either by passing `--rpc-url <URL>` or `--chain mainnet|testnet`
(see [Usage](#usage)).

## Framework

- **Language:** Python 3.9+ (stdlib only — `urllib`, `json`, `argparse`, `dataclasses`).
- **RPC protocol:** JSON-RPC (`eth_getTransactionReceipt`,
  `eth_getTransactionByHash`, `eth_blockNumber`, `eth_chainId`).
- **Storage:** append-only JSONL on local disk
  (`data/journal.jsonl` by default; override with
  `RECIMP_JOURNAL` env var or `--journal` flag).
- **External CLIs (optional):** `cast` from
  [Foundry](https://book.getfoundry.xyz/) for manual cross-checks
  of tx status.
- **No web3 framework required** — the engine speaks JSON-RPC
  directly over `urllib.request`.

## Dependencies

Runtime: nothing beyond Python 3.9+ stdlib. `requirements.txt` is
kept for tooling compatibility but contains only `requests>=2.31`
(no one actually needs it — the engine uses `urllib.request`).

Optional:

- `cast` / `forge` — Foundry CLI (https://book.getfoundry.xyz/getting-started/installation)
  for manual cross-checks of tx status.

## Install

```bash
git clone https://github.com/misturahadegoke/recimp
cd recimp

# Verified Python version
python3 --version   # 3.9+
```

That's it — no `pip install`, no native compilation, no
Foundry requirement. The skill is a Python module wrapped by a
bash demo shim for callers without a populated journal.

## Quick test (try it in 30 seconds)

After the install above, you can run either:

```bash
# Synthetic demo — no journal, no network.
bash scripts/iterate.sh

# Or, against the bundled sample journal:
cp examples/sample-journal.jsonl data/journal.jsonl
python3 src/recimp.py advise --format text
```

You should see a per-strategy report with verdicts
(`HEALTHY` / `UNDERPERFORMING` / `BROKEN` / `INSUFFICIENT_DATA`)
and rule-based tuning recommendations where applicable.
See `examples/sample-output.md` for the expected output.

To run a live on-chain check, point `--rpc-url` at a Pharos RPC:

```bash
python3 src/recimp.py verify \
  --rpc-url https://atlantic.dplabs-internal.com \
  --chain testnet
```

## Use in an AI agent (Claude Code / Codex / OpenClaw / Pharos Agent Center / Anvita Flow)

The skill ships a `SKILL.md` at the repo root that AI agents
auto-load. Once installed in your agent, just ask in natural
language — the agent will read `SKILL.md` and run the Python
CLI for you.

```text
"Review my last 10 trades and tell me what to tune."
```

The agent will run `python3 src/recimp.py advise --format text`
(or the live command with the address you gave) and read the
result back to you.

### Install in your agent

**Option A — Anvita Flow / Pharos Agent Center** (one-line install):

```bash
# Upload the .zip to https://flow.anvita.xyz/service-agents
bash scripts/build-package.sh
# → produces recimp.zip
```

**Option B — OpenClaw / Claude Code / Codex** (one-line via npm):

```bash
npx skills add https://github.com/misturahadegoke/recimp
```

**Option C — Manual install**:

```bash
# Clone the skill
git clone https://github.com/misturahadegoke/recimp
cd recimp

# Claude Code: copy to ~/.claude/skills/recimp
mkdir -p ~/.claude/skills/recimp
cp -r . ~/.claude/skills/recimp/

# Codex: copy to ~/.codex/skills/recimp
mkdir -p ~/.codex/skills/recimp
cp -r . ~/.codex/skills/recimp/

# OpenClaw: copy to ~/.openclaw/skills/recimp
mkdir -p ~/.openclaw/skills/recimp
cp -r . ~/.openclaw/skills/recimp/
```

Then restart the agent — the skill will be auto-loaded via `SKILL.md`.

## Usage

The CLI exposes four subcommands.

### 1. `record` — log a trade

```bash
python3 src/recimp.py record \
  --strategy stablecoin-farming \
  --action OPEN \
  --tx-hash 0xYourTxHash \
  --symbol USDC \
  --params '{"size_usd": 1000, "stop_loss_bps": 200, "max_slippage_bps": 30}' \
  --note "user-initiated"
```

### 2. `verify` — re-read tx hashes via RPC

```bash
python3 src/recimp.py verify \
  --rpc-url https://rpc.pharos.xyz \
  --chain mainnet
```

This walks the journal, calls `eth_getTransactionReceipt` for
each entry, and writes the verification metadata back to disk.

### 3. `reflect` — per-strategy stats

```bash
python3 src/recimp.py reflect \
  --chain mainnet \
  --window 30 \
  --format markdown
```

### 4. `advise` — tuning recommendations

```bash
python3 src/recimp.py advise \
  --window 30 \
  --format text
```

### Full example session

```bash
# 1. Open a position
python3 src/recimp.py record --strategy stablecoin-farming --action OPEN \
  --tx-hash 0xabc... --symbol USDC \
  --params '{"size_usd": 1000, "stop_loss_bps": 200}'

# 2. Close it
python3 src/recimp.py record --strategy stablecoin-farming --action CLOSE \
  --tx-hash 0xdef... --symbol USDC --pnl-usd 50.0 \
  --params '{"size_usd": 1000, "stop_loss_bps": 200}'

# 3. Verify on-chain
python3 src/recimp.py verify --rpc-url https://rpc.pharos.xyz --chain mainnet

# 4. Review performance
python3 src/recimp.py reflect --chain mainnet --format text

# 5. Get tuning advice
python3 src/recimp.py advise --format text
```

### Subcommand flag reference

#### `record`

| Flag | Required | Description |
|------|----------|-------------|
| `--strategy` | yes | Strategy name (e.g. `stablecoin-farming`) |
| `--action` | yes | `OPEN` / `CLOSE` / `REBALANCE` / `CLAIM` / `INIT` |
| `--tx-hash` | no | 0x tx hash (verified later) |
| `--symbol` | no | Asset symbol (e.g. `USDC`) |
| `--pnl-usd` | no | Realized P&L in USD (for `CLOSE`) |
| `--params` | no | JSON-encoded parameter dict at the time of trade |
| `--note` | no | Free-form note |
| `--journal PATH` | no | Override journal location |

#### `verify`

| Flag | Required | Description |
|------|----------|-------------|
| `--rpc-url` | yes | JSON-RPC endpoint (overrides `--chain`) |
| `--chain` | no | `mainnet` or `testnet` |
| `--strategy` | no | Only verify a specific strategy |
| `--since` | no | Only entries newer than this ISO 8601 timestamp |
| `--quiet` | no | Suppress per-N progress |

#### `reflect` / `advise`

| Flag | Required | Description |
|------|----------|-------------|
| `--rpc-url` | no | JSON-RPC (only `reflect` uses it for context; `advise` is offline) |
| `--chain` | no | `mainnet` or `testnet` |
| `--strategy` | no | Only reflect on / advise for one strategy |
| `--window` | no | Lookback in days (default `30`, `0` disables) |
| `--format` | no | `text` / `json` / `markdown` / `html` |
| `--out PATH` | no | Write to file (`-` for stdout, default) |

### Sample output

See `examples/sample-output.md` for what a real report looks like.

## AI Agent Integration

This repository ships a `SKILL.md` at the root that any agent
runtime can load to discover the skill. The flow:

1. The agent reads `SKILL.md` to learn the four subcommands
   and their arguments.
2. After every onchain action, the agent calls
   `recimp record` to log it.
3. Periodically (or on user request), the agent calls
   `recimp verify && recimp reflect && recimp advise` to
   review and tune.
4. The agent surfaces the verdict, stats, and recommendations
   as the top of its reply.
5. Tuning recommendations are *advisory only*; the agent
   should ask the user before applying them.

A typical prompt that triggers the skill:

> "Review your trading performance on Pharos."

A typical reply:

> **stablecoin-farming** — HEALTHY, 12 trades, 75% win rate,
> +$360 realized. Tuning: raise `size_usd` 1000 → 1250 (conf 0.60).
>
> **perp-grid** — BROKEN, 8 trades, 25% win rate, -$230
> realized. Tuning: disable `enabled` (conf 0.85).
>
> See `advise-report.md` for the full breakdown.

## Repository layout

```
recimp/
├── SKILL.md                       # Agent-facing skill spec (Anvita Flow / Claude / etc.)
├── README.md                      # This file
├── LICENSE                        # MIT-0
├── requirements.txt               # Empty-effect — engine is pure stdlib
├── data/                          # Working directory for the journal (gitignored)
├── src/
│   ├── recimp.py                  # CLI entry point (`python src/recimp.py …`)
│   ├── journal.py                 # Append-only trade log + atomic writes
│   ├── verifier.py                # On-chain tx confirmation
│   ├── reflection.py              # Per-strategy stats + verdict
│   ├── advisor.py                 # Rule-based tuning (5 rules)
│   ├── rpc.py                     # JSON-RPC client (urllib, with backoff)
│   └── report.py                  # Text / JSON / Markdown / HTML formatter
├── scripts/
│   ├── iterate.sh                 # Synthetic demo shim (no journal, no network)
│   └── build-package.sh           # Build recimp.zip for Anvita Flow upload
├── references/
│   ├── pnl-math.md                # P&L / drawdown / verdict math
│   └── tuning-rules.md            # Rule-based advisor reference
├── assets/
│   └── networks.json              # Pharos Skill Engine network config
├── examples/
│   ├── sample-journal.jsonl       # Example trade log
│   └── sample-output.md           # Example reflection report
└── tests/
    └── test_iterate_smoke.sh      # Bash smoke test (with live-RPC attempt)
```

## How it works

See `references/pnl-math.md` for the realized-P&L, drawdown, and
verdict formulas. See `references/tuning-rules.md` for the five
advisor rules.

## Roadmap

- [ ] Re-derive P&L from on-chain Transfer events (currently
      trusts the agent's reported `pnl_usd`).
- [ ] Bayesian posterior over parameter values (replace rule-
      based advisor as a *second* opinion).
- [ ] Per-strategy config file (`strategies/<name>.json`) so
      `params` is the source of truth.
- [ ] Webhook / push-notification when a strategy crosses into
      `BROKEN`.
- [ ] Roundtrip with Pharos Skill Engine for actual
      `cast`-based write paths (currently no writes are issued).

## Contributing

PRs welcome — especially new advisor rules, journal-import
tools (for migrating from existing trade bots), and benchmarks
against real agent journals.

## Tests

```bash
bash tests/test_iterate_smoke.sh
```

The test suite covers the engine's heuristics, the JSON output
schema, journal record/append roundtrip, demo shim, and (when
Atlantic testnet RPC is reachable) a live RPC smoke test
that actually calls `eth_getTransactionReceipt` against Pharos.

## License

[MIT-0](https://opensource.org/licenses/MIT-0) — free to use, modify,
redistribute. No attribution required.

---

**Author:** misturahadegoke
**Built with:** Python 3.9+ stdlib, plain JSON-RPC, and a healthy
distrust of agents that can't explain their own performance.
