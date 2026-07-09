#!/usr/bin/env python3
"""
recimp — Recursive Self-Improvement for Onchain Agents (CLI).

Subcommands:
  record    log a trade to the journal
  verify    re-read tx hashes via JSON-RPC; attach confirmations
  reflect   per-strategy stats + verdict
  advise    rule-based tuning recommendations

Read-only. No private key is accepted.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

# Make `import rpc` etc. work whether invoked as a script or as `python -m`
_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from journal import Journal, new_entry, default_journal_path  # noqa: E402
from rpc import RpcClient, RpcError  # noqa: E402
from verifier import run as verify_run  # noqa: E402
from reflection import compute_all  # noqa: E402
from advisor import advise_all  # noqa: E402
import report  # noqa: E402


# --- Helpers ---------------------------------------------------------------

def _load_networks() -> dict:
    p = _HERE.parent / "assets" / "networks.json"
    if not p.exists():
        return {"networks": [], "defaultNetwork": "mainnet"}
    try:
        with open(p) as f:
            return json.load(f)
    except json.JSONDecodeError:
        return {"networks": [], "defaultNetwork": "mainnet"}


def _resolve_rpc(arg_rpc: str | None, chain: str | None) -> str:
    if arg_rpc:
        return arg_rpc
    nets = _load_networks().get("networks", [])
    if not nets:
        raise SystemExit("Error: no --rpc-url given and assets/networks.json is missing")
    wanted = (chain or "").lower()
    if wanted in ("", "mainnet"):
        wanted = "mainnet"
    for n in nets:
        if n.get("name") == wanted:
            return n["rpcUrl"]
    # fall back to first
    return nets[0]["rpcUrl"]


def _print(s: str) -> None:
    print(s)


def _emit_payload(payload: str, out: str | None) -> None:
    if out and out != "-":
        Path(out).parent.mkdir(parents=True, exist_ok=True)
        with open(out, "w", encoding="utf-8") as f:
            f.write(payload)
            if not payload.endswith("\n"):
                f.write("\n")
        _print(f"  wrote {out}")
    else:
        _print(payload)


# --- Subcommands -----------------------------------------------------------

def cmd_record(args: argparse.Namespace) -> int:
    journal = Journal(args.journal)
    try:
        params = json.loads(args.params) if args.params else {}
    except json.JSONDecodeError as e:
        _print(f"Error: --params must be JSON: {e}")
        return 2

    entry = new_entry(
        strategy=args.strategy,
        action=args.action,
        tx_hash=args.tx_hash,
        symbol=args.symbol,
        pnl_usd=float(args.pnl_usd or 0.0),
        params=params,
        note=args.note or "",
    )
    journal.append(entry)
    _print(json.dumps({"ok": True, "id": entry["id"]}, indent=2))
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    rpc_url = _resolve_rpc(args.rpc_url, getattr(args, "chain", None))
    rpc = RpcClient(rpc_url)

    journal = Journal(args.journal)
    if not journal.exists():
        _print(json.dumps({"checked": 0, "updated": 0, "note": "journal not found"}))
        return 0

    summary = verify_run(
        journal,
        rpc,
        strategy=args.strategy,
        since=args.since,
        progress=not args.quiet,
    )
    _print(json.dumps(summary, indent=2))
    return 0


def _emit_reflect(
    entries_path: Path,
    *,
    rpc: RpcClient | None,
    strategy: str | None,
    window: int | None,
    fmt: str,
    out: str | None,
    advise: bool,
) -> int:
    journal = Journal(entries_path)
    entries = journal.read_all()
    if not entries:
        _print("No journal entries.")
        return 0

    stats_list = compute_all(entries, strategy=strategy, window_days=window)

    advisories: dict[str, list] = {}
    if advise:
        # filter to only the requested strategy (or all if none)
        from advisor import advise_for_strategy
        for s in stats_list:
            if strategy and s.strategy != strategy:
                continue
            recs = advise_for_strategy(s)
            advisories[s.strategy] = recs

    payload = report.render(
        stats_list, fmt=fmt, advisories=advisories, window=window
    )
    _emit_payload(payload, out)
    return 0


def cmd_reflect(args: argparse.Namespace) -> int:
    rpc: RpcClient | None = None
    if args.rpc_url:
        rpc = RpcClient(_resolve_rpc(args.rpc_url, getattr(args, "chain", None)))
    return _emit_reflect(
        Path(args.journal),
        rpc=rpc,
        strategy=args.strategy,
        window=args.window,
        fmt=args.format,
        out=args.out,
        advise=False,
    )


def cmd_advise(args: argparse.Namespace) -> int:
    return _emit_reflect(
        Path(args.journal),
        rpc=None,
        strategy=args.strategy,
        window=args.window,
        fmt=args.format,
        out=args.out,
        advise=True,
    )


# --- Argparse --------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="recimp",
        description="Recursive self-improvement CLI for on-chain AI agents (Pharos).",
    )
    p.add_argument(
        "--journal",
        default=str(default_journal_path()),
        help="path to journal JSONL (default: $RECIMP_JOURNAL or data/journal.jsonl)",
    )

    sub = p.add_subparsers(dest="cmd", required=True)

    pr = sub.add_parser("record", help="log a trade")
    pr.add_argument("--strategy", required=True)
    pr.add_argument(
        "--action", required=True, choices=["OPEN", "CLOSE", "REBALANCE", "CLAIM", "INIT"]
    )
    pr.add_argument("--tx-hash", default=None)
    pr.add_argument("--symbol", default=None)
    pr.add_argument("--pnl-usd", default=None)
    pr.add_argument("--params", default=None, help="JSON-encoded dict")
    pr.add_argument("--note", default=None)
    pr.set_defaults(func=cmd_record)

    pv = sub.add_parser("verify", help="re-read tx hashes via JSON-RPC")
    pv.add_argument("--rpc-url", required=True)
    pv.add_argument("--chain", choices=["mainnet", "testnet"], default=None)
    pv.add_argument("--strategy", default=None)
    pv.add_argument("--since", default=None, help="ISO 8601 lower bound")
    pv.add_argument("--quiet", action="store_true")
    pv.set_defaults(func=cmd_verify)

    pf = sub.add_parser("reflect", help="per-strategy stats + verdict")
    pf.add_argument("--rpc-url", default=None, help="optional, for native price context")
    pf.add_argument("--chain", choices=["mainnet", "testnet"], default=None)
    pf.add_argument("--strategy", default=None)
    pf.add_argument(
        "--window", type=int, default=30,
        help="lookback days (default 30, 0 disables)",
    )
    pf.add_argument("--format", choices=["text", "json", "markdown", "html"], default="text")
    pf.add_argument("--out", default=None)
    pf.set_defaults(func=cmd_reflect)

    pa = sub.add_parser("advise", help="rule-based tuning recommendations")
    pa.add_argument("--rpc-url", default=None, help="optional, ignored (advise is offline)")
    pa.add_argument("--chain", choices=["mainnet", "testnet"], default=None)
    pa.add_argument("--strategy", default=None)
    pa.add_argument("--window", type=int, default=30)
    pa.add_argument("--format", choices=["text", "json", "markdown", "html"], default="text")
    pa.add_argument("--out", default=None)
    pa.set_defaults(func=cmd_advise)

    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        return args.func(args)
    except RpcError as e:
        _print(f"Error: RPC failure — {e}")
        return 3
    except Exception as e:  # noqa: BLE001
        _print(f"Error: {e}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
