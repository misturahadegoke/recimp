# RecImp — Recursive Self-Improvement for Onchain Agents

> A meta-skill that lets an AI agent log its onchain actions,
> review its own performance per strategy, and propose
> parameter tuning based on the review.

[![python](https://img.shields.io/badge/python-3.9%2B-blue)]()
[![license](https://img.shields.io/badge/license-MIT--0-green)]()
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
- **Append-only journal** — JSONL, atomic writes, no external
  DB.
- **On-chain verification** — every recorded tx is re-read via
  the chain's RPC to confirm inclusion and capture gas used.
- **Per-strategy stats** — win rate, realized P&L, max
  drawdown, gas, current params, first/last seen.
- **Four-tier verdict** — `HEALTHY` / `UNDERPERFORMING` /
  `BROKEN` / `INSUFFICIENT_DATA`.
- **Rule-based tuning** — five auditable rules, each with a
  trigger, output, confidence, and rationale.
- **Multi-format output** — text (with ANSI colors), JSON,
  Markdown, or HTML via the `report.py` formatter.
- **Agent-ready** — ships a `SKILL.md` at the repo root with
  the invocation contract an agent runtime needs to drive the
  tool.

## Supported networks

The tool runs against any EVM-compatible JSON-RPC endpoint for
on-chain verification. The following networks are explicitly
supported out of the box and used in the examples below.

| Network                 | Chain ID | RPC URL                                | Native token | Explorer                          |
|-------------------------|----------|----------------------------------------|--------------|-----------------------------------|
| Pharos Pacific Mainnet  | `1672`   | `https://rpc.pharos.xyz`               | PROS         | https://www.pharosscan.xyz/       |
| Pharos Atlantic Testnet | `688689` | `https://atlantic.dplabs-internal.com` | PHRS         | https://atlantic.pharosscan.xyz/  |

You can target either by passing the matching `--rpc-url` flag
(see [Usage](#usage)).

## Framework

- **Language:** Python 3.9+
- **RPC protocol:** JSON-RPC (`eth_getTransactionReceipt`,
  `eth_getTransactionByHash`, `eth_blockNumber`, `eth_chainId`)
- **Storage:** append-only JSONL on local disk
  (`data/journal.jsonl` by default; override with
  `RECIMP_JOURNAL` env var or `--journal` flag).
- **External CLIs (optional):** `cast` from
  [Foundry](https://book.getfoundry.xyz/) for manual cross-checks
  of tx status; `jq` for ergonomic RPC URL extraction in shell
  pipelines.
- **No web3 framework required** — the engine speaks JSON-RPC
  directly over `requests` and the journal is plain Python.

## Dependencies

Runtime (Python):

- `requests>=2.31` — HTTP client used by `src/rpc.py`.

External (only if you want the optional CLIs):

- `cast` / `forge` — Foundry CLI (https://book.getfoundry.xyz/getting-started/installation).
- `jq` — command-line JSON processor, used in README shell snippets.

Everything is pinned in `requirements.txt` at the repo root.

## Install

### 1. Install Python 3.9+ and pip

```bash
# macOS
brew install python@3.11
# Debian/Ubuntu/Termux
apt install -y python3 python3-pip
```

Verify with `python3 --version`.

### 2. (Optional) Install Foundry if you want cast/forge fallback

```bash
curl -L https://foundry.paradigm.xyz | bash
foundryup
```

Verify with `cast --version`. Foundry is OPTIONAL for this skill — the bash CLI in `scripts/cli.sh` works without it.

### 3. Get the skill

```bash
git clone https://github.com/misturahadegoke/recimp
cd recimp
pip install -r requirements.txt
chmod +x scripts/*.sh
```

That's it. No build step, no native compilation. The skill is a Python 3.9+ module wrapped by a bash CLI for easy invocation.
## Quick test (try it in 30 seconds)

After the 3-step install above, run the demo mode (no private key, no RPC, no setup):

```bash
bash scripts/iterate.sh --demo
```

You should see a printed report. The demo uses synthetic data, so it works offline.

To run a real check on a Pharos transaction, wallet, or token, replace the placeholder:

```bash
bash scripts/iterate.sh --strategy ./strategy.json --iterations 50
```

## Use in an AI agent (Claude Code / Codex / OpenClaw / Pharos Agent Center)

The skill ships with a `SKILL.md` that AI agents auto-load. Once installed in your agent, just ask in natural language — the agent will read `SKILL.md` and run the bash script for you.

```text
"Review my last 10 trades and tell me what to tune."
```

The agent will run `bash scripts/iterate.sh --demo` (or the live command with the address you gave) and read the result back to you.

### Install in your agent

**Option A — Pharos Agent Center** (one-line install):

```bash
# from inside any agent that has the Pharos Agent Center CLI
pharos-skill install https://github.com/misturahadegoke/recimp
```

**Option B — OpenClaw / Claude Code / Codex** (one-line via npm):

```bash
npx skills add https://github.com/misturahadegoke/recimp
```

**Option C — Manual install** (drop into your agent's skills directory):

```bash
# Clone the skill
git clone https://github.com/misturahadegoke/recimp
cd recimp

# Claude Code: copy to ~/.claude/skills/
mkdir -p ~/.claude/skills/recimp
cp -r . ~/.claude/skills/recimp/

# Codex: copy to ~/.codex/skills/
mkdir -p ~/.codex/skills/recimp
cp -r . ~/.codex/skills/recimp/

# OpenClaw: copy to ~/.openclaw/skills/
mkdir -p ~/.openclaw/skills/recimp
cp -r . ~/.openclaw/skills/recimp/

# Then restart the agent — the skill will be auto-loaded.
```
## Usage

The CLI exposes four subcommands.

### 1. `record` — log a trade

```bash
python src/recimp.py record \
  --strategy stablecoin-farming \
  --action OPEN \
  --tx-hash 0xYourTxHash \
  --symbol USDC \
  --params '{"size_usd": 1000, "stop_loss_bps": 200, "max_slippage_bps": 30}' \
  --note "user-initiated"
```

### 2. `verify` — re-read tx hashes via RPC

```bash
python src/recimp.py verify \
  --rpc-url https://rpc.pharos.xyz
```

This walks the journal, calls `eth_getTransactionReceipt` for
each entry, and writes the verification metadata back to disk.

### 3. `reflect` — per-strategy stats

```bash
python src/recimp.py reflect \
  --rpc-url https://rpc.pharos.xyz \
  --window 30 \
  --format markdown
```

### 4. `advise` — tuning recommendations

```bash
python src/recimp.py advise \
  --rpc-url https://rpc.pharos.xyz \
  --window 30 \
  --format text
```

### Full example session

```bash
# 1. Open a position
python src/recimp.py record --strategy stablecoin-farming --action OPEN \
  --tx-hash 0xabc... --symbol USDC \
  --params '{"size_usd": 1000, "stop_loss_bps": 200}'

# 2. Close it
python src/recimp.py record --strategy stablecoin-farming --action CLOSE \
  --tx-hash 0xdef... --symbol USDC --pnl-usd 50.0 \
  --params '{"size_usd": 1000, "stop_loss_bps": 200}'

# 3. Verify on-chain
python src/recimp.py verify --rpc-url https://rpc.pharos.xyz

# 4. Review performance
python src/recimp.py reflect --rpc-url https://rpc.pharos.xyz --format text

# 5. Get tuning advice
python src/recimp.py advise --rpc-url https://rpc.pharos.xyz --format text
```

### Subcommand flag reference

#### `record`

| Flag           | Required | Description                                       |
|----------------|----------|---------------------------------------------------|
| `--strategy`   | yes      | Strategy name (e.g. `stablecoin-farming`)         |
| `--action`     | yes      | `OPEN`, `CLOSE`, `REBALANCE`, `CLAIM`            |
| `--tx-hash`    | no       | 0x tx hash (verify later)                         |
| `--symbol`     | no       | Asset symbol (e.g. `USDC`)                        |
| `--pnl-usd`    | no       | Realized P&L in USD (for CLOSE actions)           |
| `--params`     | no       | JSON-encoded parameter dict at the time of trade  |
| `--note`       | no       | Free-form note                                    |

#### `verify`

| Flag           | Required | Description                                       |
|----------------|----------|---------------------------------------------------|
| `--rpc-url`    | yes      | JSON-RPC endpoint                                 |
| `--strategy`   | no       | Only verify a specific strategy                   |
| `--since`      | no       | Only verify entries newer than this ISO 8601 ts   |

#### `reflect` / `advise`

| Flag           | Required | Description                                       |
|----------------|----------|---------------------------------------------------|
| `--rpc-url`    | yes      | JSON-RPC endpoint                                 |
| `--strategy`   | no       | Only reflect/advise on a specific strategy        |
| `--window`     | no       | Lookback window in days (default 30, 0 to disable) |
| `--format`     | no       | `text`, `json`, `markdown`, `html`                |
| `--out`        | no       | Output file (`-` for stdout)                      |

### Sample output

See `examples/sample-output.md` for what a real report looks like.

## AI Agent Integration

This repository ships a `SKILL.md` at the root that any agent
runtime can load to discover the skill. The flow is:

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
> +$360 realized. Tuning: raise `size_usd` 1000 → 1250 (conf
> 0.60).
>
> **perp-grid** — BROKEN, 8 trades, 25% win rate, -$230
> realized. Tuning: disable `enabled` (conf 0.85).
>
> See `reflection-report.md` for the full breakdown.

## Repository layout

```
recimp/
├── SKILL.md                       # Agent-facing skill spec
├── README.md                      # This file
├── LICENSE                        # MIT-0
├── requirements.txt
├── data/
│   └── journal.jsonl              # Per-agent trade log (gitignored)
├── src/
│   ├── recimp.py                  # CLI entry point
│   ├── journal.py                 # Append-only trade log
│   ├── verifier.py                # On-chain tx confirmation
│   ├── reflection.py              # Per-strategy stats
│   ├── advisor.py                 # Rule-based tuning
│   ├── rpc.py                     # JSON-RPC client
│   └── report.py                  # Text / JSON / Markdown / HTML formatter
├── references/
│   ├── pnl-math.md                # P&L / drawdown math
│   └── tuning-rules.md            # Rule-based tuning rules
└── examples/
    ├── sample-journal.jsonl       # Example trade log
    └── sample-output.md           # Example reflection report
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

## Contributing

PRs welcome — especially new advisor rules, journal-import
tools (for migrating from existing trade bots), and benchmarks
against real agent journals.


## Tests

```bash
pytest tests/ -v  # or: bash scripts/iterate.sh --demo
```

The test suite covers the engine's heuristics, the JSON output schema, and (when run with `cast` installed) a live RPC smoke test against Pharos Pacific Mainnet.

## Repository layout

```
.
├── README.md                  # this file
├── SKILL.md                   # Agent-side description (loaded by Claude/Codex/etc.)
├── scripts/
│   └── iterate.sh          # bash + cast engine — the entire skill
├── assets/
│   └── networks.json          # Pharos Skill Engine network config
└── tests/
    └── test_*.sh              # bash smoke test
```
## License

[MIT-0](https://opensource.org/licenses/MIT-0) — free to use, modify,
redistribute. No attribution required.

---

**Author:** misturahadegoke
**Built with:** Python 3.9+, plain JSON-RPC, and a healthy
distrust of agents that can't explain their own performance.
