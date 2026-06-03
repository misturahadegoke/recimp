"""
report.py - Format a reflection or advisor report.

Input: a JSON object with these top-level keys:
  - generated_at: ISO 8601 ts
  - window_days:  int
  - strategies:   [StrategyStats dicts]
  - recommendations: {strategy_name: [TuningRecommendation dicts]}
                    (only present for advisor reports)
"""
from __future__ import annotations
import argparse
import json
import sys
from typing import Any, Dict


def _fmt_pct(x: float) -> str:
    return f"{x * 100:.1f}%"


def _fmt_usd(x: float) -> str:
    if abs(x) < 0.01 and x != 0:
        return f"${x:.4f}"
    return f"${x:,.2f}"


def _fmt_gas(x: float) -> str:
    if x <= 0:
        return "0"
    if x < 1_000:
        return f"{x:,.0f}"
    if x < 1_000_000:
        return f"{x/1_000:,.1f}K"
    return f"{x/1_000_000:,.2f}M"


VERDICT_COLOR = {
    "HEALTHY":            "\033[32m",  # green
    "UNDERPERFORMING":    "\033[33m",  # yellow
    "BROKEN":             "\033[31m",  # red
    "INSUFFICIENT_DATA":  "\033[90m",  # gray
}
RESET = "\033[0m"


def render_text(r: Dict[str, Any], use_color: bool = True) -> str:
    strategies = r.get("strategies", [])
    recs = r.get("recommendations", {})
    lines = []
    lines.append("=" * 64)
    lines.append(f"  AGENT REFLECTION REPORT — generated {r.get('generated_at','?')}")
    lines.append(f"  Window: last {r.get('window_days', '?')} day(s)  |  Strategies: {len(strategies)}")
    lines.append("=" * 64)
    lines.append("")

    if not strategies:
        lines.append("  No strategies in the journal yet. Run `recimp record` to start.")
        return "\n".join(lines) + "\n"

    for s in strategies:
        color = VERDICT_COLOR.get(s["verdict"], "") if use_color else ""
        reset = RESET if use_color else ""
        lines.append(f"  Strategy: {s['strategy']}    [{color}{s['verdict']}{reset}]")
        lines.append(f"    Trades:       {s['trade_count']}  "
                     f"(verified {s['verified_count']}, closed {s['close_count']})")
        lines.append(f"    Win rate:     {_fmt_pct(s['win_rate'])}  ({s['win_count']} winners)")
        lines.append(f"    Realized P&L: {_fmt_usd(s['realized_pnl_usd'])}  "
                     f"(avg {_fmt_usd(s['avg_pnl_usd'])}/trade)")
        lines.append(f"    Max drawdown: {_fmt_usd(s['max_drawdown_usd'])}")
        lines.append(f"    Gas:          total {_fmt_gas(s['total_gas'])}  "
                     f"avg {_fmt_gas(s['avg_gas_per_tx'])}/tx")
        lines.append(f"    First seen:   {s.get('first_seen','?')}")
        lines.append(f"    Last seen:    {s.get('last_seen','?')}")
        lines.append(f"    Verdict:      {s.get('verdict_reason','')}")
        if s.get("current_params"):
            lines.append(f"    Params:       {json.dumps(s['current_params'], sort_keys=True)}")
        if s["strategy"] in recs:
            lines.append(f"    Tuning:")
            for rec in recs[s["strategy"]]:
                lines.append(f"      - {rec['param']}: {rec['old']!r} -> {rec['new']!r}  "
                             f"(conf {rec['confidence']:.2f})")
                lines.append(f"          {rec['rationale']}")
        lines.append("")
    return "\n".join(lines) + "\n"


def render_markdown(r: Dict[str, Any]) -> str:
    strategies = r.get("strategies", [])
    recs = r.get("recommendations", {})
    lines = []
    lines.append(f"# Agent Reflection Report")
    lines.append("")
    lines.append(f"- **Generated:** {r.get('generated_at','?')}")
    lines.append(f"- **Window:** last {r.get('window_days','?')} day(s)")
    lines.append(f"- **Strategies:** {len(strategies)}")
    lines.append("")

    if not strategies:
        lines.append("No strategies in the journal yet. Run `recimp record` to start.")
        return "\n".join(lines) + "\n"

    for s in strategies:
        lines.append(f"## {s['strategy']} — **{s['verdict']}**")
        lines.append("")
        lines.append("| Metric | Value |")
        lines.append("|--------|-------|")
        lines.append(f"| Trades | {s['trade_count']} (verified {s['verified_count']}, closed {s['close_count']}) |")
        lines.append(f"| Win rate | {_fmt_pct(s['win_rate'])} ({s['win_count']} winners) |")
        lines.append(f"| Realized P&L | {_fmt_usd(s['realized_pnl_usd'])} (avg {_fmt_usd(s['avg_pnl_usd'])}/trade) |")
        lines.append(f"| Max drawdown | {_fmt_usd(s['max_drawdown_usd'])} |")
        lines.append(f"| Total gas | {_fmt_gas(s['total_gas'])} (avg {_fmt_gas(s['avg_gas_per_tx'])}/tx) |")
        lines.append(f"| First seen | {s.get('first_seen','?')} |")
        lines.append(f"| Last seen | {s.get('last_seen','?')} |")
        lines.append("")
        lines.append(f"> {s.get('verdict_reason','')}")
        lines.append("")
        if s.get("current_params"):
            lines.append("**Current params:** `" + json.dumps(s["current_params"], sort_keys=True) + "`")
            lines.append("")
        if s["strategy"] in recs:
            lines.append("**Tuning recommendations:**")
            lines.append("")
            lines.append("| Param | Old | New | Confidence | Rationale |")
            lines.append("|-------|-----|-----|------------|-----------|")
            for rec in recs[s["strategy"]]:
                lines.append(f"| `{rec['param']}` | `{rec['old']!r}` | `{rec['new']!r}` | {rec['confidence']:.2f} | {rec['rationale']} |")
            lines.append("")
    return "\n".join(lines) + "\n"


def render_html(r: Dict[str, Any]) -> str:
    strategies = r.get("strategies", [])
    recs = r.get("recommendations", {})
    verdict_color = {
        "HEALTHY":            "#1e8e3e",
        "UNDERPERFORMING":    "#f9ab00",
        "BROKEN":             "#d93025",
        "INSUFFICIENT_DATA":  "#5f6368",
    }
    sections = ""
    for s in strategies:
        vc = verdict_color.get(s["verdict"], "#202124")
        rec_html = ""
        if s["strategy"] in recs:
            rec_html = "<h3>Tuning recommendations</h3><ul>"
            for rec in recs[s["strategy"]]:
                rec_html += (
                    f"<li><code>{rec['param']}</code>: "
                    f"<code>{rec['old']!r}</code> &rarr; <code>{rec['new']!r}</code> "
                    f"(conf {rec['confidence']:.2f})<br>"
                    f"<span style='color:#5f6368; font-size:13px;'>{rec['rationale']}</span></li>"
                )
            rec_html += "</ul>"
        sections += f"""
<h2 style='color:{vc};'>{s['strategy']} &mdash; {s['verdict']}</h2>
<table>
<tbody>
<tr><th>Trades</th><td>{s['trade_count']} (verified {s['verified_count']}, closed {s['close_count']})</td></tr>
<tr><th>Win rate</th><td>{_fmt_pct(s['win_rate'])} ({s['win_count']} winners)</td></tr>
<tr><th>Realized P&amp;L</th><td>{_fmt_usd(s['realized_pnl_usd'])} (avg {_fmt_usd(s['avg_pnl_usd'])}/trade)</td></tr>
<tr><th>Max drawdown</th><td>{_fmt_usd(s['max_drawdown_usd'])}</td></tr>
<tr><th>Total gas</th><td>{_fmt_gas(s['total_gas'])} (avg {_fmt_gas(s['avg_gas_per_tx'])}/tx)</td></tr>
<tr><th>First seen</th><td>{s.get('first_seen','?')}</td></tr>
<tr><th>Last seen</th><td>{s.get('last_seen','?')}</td></tr>
<tr><th>Verdict</th><td>{s.get('verdict_reason','')}</td></tr>
</tbody>
</table>
{rec_html}
"""
    return f"""<!doctype html>
<html><head><meta charset="utf-8">
<title>Agent Reflection Report</title>
<style>
  body {{ font: 14px/1.4 system-ui, sans-serif; max-width: 900px; margin: 32px auto; padding: 0 16px; color: #202124; }}
  h1 {{ border-bottom: 2px solid #202124; padding-bottom: 4px; }}
  h2 {{ margin-top: 32px; padding-bottom: 4px; border-bottom: 1px solid #dadce0; }}
  h3 {{ font-size: 14px; margin: 12px 0 6px; color: #5f6368; }}
  table {{ border-collapse: collapse; width: 100%; margin: 6px 0 12px; }}
  th, td {{ border: 1px solid #dadce0; padding: 4px 8px; text-align: left; font-size: 13px; }}
  th {{ background: #f8f9fa; width: 180px; }}
  code {{ background: #f1f3f4; padding: 1px 4px; border-radius: 3px; }}
  ul {{ padding-left: 18px; }}
  li {{ margin-bottom: 8px; }}
</style></head><body>
<h1>Agent Reflection Report</h1>
<p><strong>Generated:</strong> {r.get('generated_at','?')} &middot;
   <strong>Window:</strong> last {r.get('window_days','?')} day(s) &middot;
   <strong>Strategies:</strong> {len(strategies)}</p>
{sections or "<p>No strategies in the journal yet. Run <code>recimp record</code> to start.</p>"}
</body></html>
"""


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--in", dest="input", default="-")
    p.add_argument("--format", choices=["text", "markdown", "html", "json"], default="text")
    p.add_argument("--out", default="-")
    p.add_argument("--no-color", action="store_true")
    args = p.parse_args()

    raw = sys.stdin.read() if args.input == "-" else open(args.input).read()
    r = json.loads(raw)

    if args.format == "json":
        out = json.dumps(r, indent=2)
    elif args.format == "markdown":
        out = render_markdown(r)
    elif args.format == "html":
        out = render_html(r)
    else:
        out = render_text(r, use_color=not args.no_color)

    if args.out == "-":
        sys.stdout.write(out)
    else:
        with open(args.out, "w") as f:
            f.write(out)


if __name__ == "__main__":
    main()
