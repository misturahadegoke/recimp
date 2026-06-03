"""
recimp.py - CLI entry point with four subcommands:
  record   - log a new trade
  verify   - re-read tx hashes via RPC and attach confirmation
  reflect  - per-strategy stats
  advise   - rule-based tuning recommendations

Usage:
  python recimp.py record --strategy X --action OPEN --tx-hash 0x...
  python recimp.py verify --rpc-url https://...
  python recimp.py reflect --rpc-url https://...
  python recimp.py advise --rpc-url https://...
"""
from __future__ import annotations
import argparse
import json
import sys
import time
from typing import Any, Dict, List, Optional

from journal import (
    JournalEntry,
    VALID_ACTIONS,
    append as journal_append,
)
from verifier import verify_all
from reflection import compute as compute_reflection
from advisor import advise_for_strategy, advise_all
from rpc import RpcClient


def _stats_to_dict(s) -> Dict[str, Any]:
    return {
        "strategy":         s.strategy,
        "trade_count":      s.trade_count,
        "verified_count":   s.verified_count,
        "close_count":      s.close_count,
        "win_count":        s.win_count,
        "win_rate":         s.win_rate,
        "realized_pnl_usd": s.realized_pnl_usd,
        "avg_pnl_usd":      s.avg_pnl_usd,
        "total_gas":        s.total_gas,
        "avg_gas_per_tx":   s.avg_gas_per_tx,
        "max_drawdown_usd": s.max_drawdown_usd,
        "current_params":   s.current_params,
        "verdict":          s.verdict,
        "verdict_reason":   s.verdict_reason,
        "first_seen":       s.first_seen,
        "last_seen":        s.last_seen,
    }


def _rec_to_dict(r) -> Dict[str, Any]:
    return {
        "param":      r.param,
        "old":        r.old,
        "new":        r.new,
        "confidence": r.confidence,
        "rationale":  r.rationale,
    }


def cmd_record(args: argparse.Namespace) -> int:
    if args.action not in VALID_ACTIONS:
        print(f"error: --action must be one of {sorted(VALID_ACTIONS)}", file=sys.stderr)
        return 1
    if not args.strategy:
        print("error: --strategy is required", file=sys.stderr)
        return 1
    params: Dict[str, Any] = {}
    if args.params:
        try:
            params = json.loads(args.params)
        except json.JSONDecodeError as e:
            print(f"error: --params is not valid JSON: {e}", file=sys.stderr)
            return 1
    entry = JournalEntry(
        strategy=args.strategy,
        action=args.action,
        symbol=args.symbol or "",
        tx_hash=args.tx_hash or "",
        pnl_usd=args.pnl_usd or 0.0,
        params=params,
        note=args.note or "",
    )
    journal_append(entry)
    print(f"recorded {entry.id}  strategy={args.strategy}  action={args.action}  symbol={entry.symbol}  tx={entry.tx_hash}")
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    rpc = RpcClient(args.rpc_url)
    summary = verify_all(rpc, path=args.journal, strategy=args.strategy, since=args.since)
    print(json.dumps(summary, indent=2))
    return 0


def cmd_reflect(args: argparse.Namespace) -> int:
    stats = compute_reflection(
        path=args.journal,
        strategy=args.strategy,
        window_days=args.window,
    )
    payload = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "window_days":  args.window,
        "journal_path": args.journal,
        "strategies":   [_stats_to_dict(s) for s in stats],
    }
    _emit(args, payload)
    return 0


def cmd_advise(args: argparse.Namespace) -> int:
    stats = compute_reflection(
        path=args.journal,
        strategy=args.strategy,
        window_days=args.window,
    )
    recs_map = advise_all(stats)
    payload = {
        "generated_at":     time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "window_days":      args.window,
        "journal_path":     args.journal,
        "strategies":       [_stats_to_dict(s) for s in stats],
        "recommendations":  {k: [_rec_to_dict(r) for r in v] for k, v in recs_map.items()},
    }
    _emit(args, payload)
    return 0


def _emit(args: argparse.Namespace, payload: Dict[str, Any]) -> None:
    if args.format == "json":
        out = json.dumps(payload, indent=2)
    elif args.format == "markdown":
        from report import render_markdown
        out = render_markdown(payload)
    elif args.format == "html":
        from report import render_html
        out = render_html(payload)
    else:
        from report import render_text
        out = render_text(payload, use_color=sys.stdout.isatty())
    if args.out == "-":
        sys.stdout.write(out)
    else:
        with open(args.out, "w") as f:
            f.write(out)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Recursive self-improvement for onchain agents.")
    p.add_argument("--journal", default="data/journal.jsonl",
                   help="Path to the JSONL journal (default: data/journal.jsonl)")
    sub = p.add_subparsers(dest="cmd", required=True)

    # record
    pr = sub.add_parser("record", help="Log a new trade")
    pr.add_argument("--strategy", required=True)
    pr.add_argument("--action", required=True, choices=sorted(VALID_ACTIONS))
    pr.add_argument("--symbol", default="")
    pr.add_argument("--tx-hash", default="")
    pr.add_argument("--pnl-usd", type=float, default=0.0)
    pr.add_argument("--params", default="", help="JSON-encoded params dict")
    pr.add_argument("--note", default="")

    # verify
    pv = sub.add_parser("verify", help="Re-read tx hashes via RPC")
    pv.add_argument("--rpc-url", required=True)
    pv.add_argument("--strategy", default=None)
    pv.add_argument("--since", default=None,
                    help="ISO 8601 timestamp; only verify entries newer than this")

    # reflect
    prf = sub.add_parser("reflect", help="Per-strategy stats")
    prf.add_argument("--rpc-url", required=True)
    prf.add_argument("--strategy", default=None)
    prf.add_argument("--window", type=int, default=30, help="Lookback window in days")
    prf.add_argument("--format", choices=["text", "json", "markdown", "html"], default="text")
    prf.add_argument("--out", default="-")

    # advise
    pa = sub.add_parser("advise", help="Tuning recommendations")
    pa.add_argument("--rpc-url", required=True)
    pa.add_argument("--strategy", default=None)
    pa.add_argument("--window", type=int, default=30)
    pa.add_argument("--format", choices=["text", "json", "markdown", "html"], default="text")
    pa.add_argument("--out", default="-")

    return p


def main():
    p = build_parser()
    args = p.parse_args()
    if args.cmd == "record":
        sys.exit(cmd_record(args))
    elif args.cmd == "verify":
        sys.exit(cmd_verify(args))
    elif args.cmd == "reflect":
        sys.exit(cmd_reflect(args))
    elif args.cmd == "advise":
        sys.exit(cmd_advise(args))
    else:
        p.print_help()
        sys.exit(2)


if __name__ == "__main__":
    main()
