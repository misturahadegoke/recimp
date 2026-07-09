"""
Formatters for reflection + advisor output.

Supports text (with ANSI colors), JSON, Markdown, and HTML.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Iterable

from reflection import StrategyStats
from advisor import TuningRecommendation


# --- ANSI helpers ----------------------------------------------------------

_USE_COLOR = True


def _c(code: str, s: str) -> str:
    if not _USE_COLOR:
        return s
    return f"\033[{code}m{s}\033[0m"


def _green(s: str) -> str:
    return _c("32", s)


def _yellow(s: str) -> str:
    return _c("33", s)


def _red(s: str) -> str:
    return _c("31", s)


def _bold(s: str) -> str:
    return _c("1", s)


def _dim(s: str) -> str:
    return _c("2", s)


# --- Verdict color ---------------------------------------------------------

def _verdict_color(v: str) -> str:
    if v == "HEALTHY":
        return _green(v)
    if v == "UNDERPERFORMING":
        return _yellow(v)
    if v == "BROKEN":
        return _red(v)
    return _dim(v)


# --- Strats → summary dict (used by all formatters) ------------------------

def _stats_dict(s: StrategyStats) -> dict:
    return s.to_dict()


def _rec_dict(r: TuningRecommendation) -> dict:
    return r.to_dict()


# --- Text format -----------------------------------------------------------

def render_text(
    stats_list: list[StrategyStats],
    *,
    window: int | None = None,
    advisories: dict[str, list[TuningRecommendation]] | None = None,
) -> str:
    advisories = advisories or {}
    lines: list[str] = []
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    window_str = f"last {window} day(s)" if window else "all time"
    lines.append("=" * 72)
    lines.append(
        f"  AGENT REFLECTION REPORT — generated {now}\n"
        f"  Window: {window_str}  |  Strategies: {len(stats_list)}"
    )
    lines.append("=" * 72)

    for s in stats_list:
        lines.append("")
        lines.append(f"  Strategy: {s.strategy}    [{_verdict_color(s.verdict)}]")
        lines.append(
            f"    Trades:       {s.trade_count}  "
            f"(verified {s.verified_count}, closed {s.close_count})"
        )
        wr = (s.win_count / max(1, s.close_count)) if s.close_count else 0.0
        lines.append(
            f"    Win rate:     {wr:.1%}  ({s.win_count} winners)"
        )
        lines.append(
            f"    Realized P&L: ${s.realized_pnl_usd:.2f}  "
            f"(avg ${s.avg_pnl_usd:.2f}/trade)"
        )
        lines.append(f"    Max drawdown: ${s.max_drawdown_usd:.2f}")
        lines.append(
            f"    Gas:          total {s.total_gas:,}  "
            f"avg {s.avg_gas_per_tx:,.1f}/tx"
        )
        lines.append(f"    First seen:   {s.first_seen}")
        lines.append(f"    Last seen:    {s.last_seen}")
        lines.append(f"    Verdict:      {s.verdict_reason}")
        if s.last_params:
            lines.append(f"    Params:       {json.dumps(s.last_params)}")
        recs = advisories.get(s.strategy, [])
        if recs:
            lines.append("    Tuning:")
            for r in recs:
                lines.append(f"      - {r.param}: {r.old!r} -> {r.new!r}  (conf {r.confidence:.2f})")
                lines.append(f"          {r.rationale}")

    lines.append("")
    lines.append("=" * 72)
    return "\n".join(lines)


# --- Markdown format -------------------------------------------------------

def render_markdown(
    stats_list: list[StrategyStats],
    *,
    advisories: dict[str, list[TuningRecommendation]] | None = None,
) -> str:
    advisories = advisories or {}
    lines: list[str] = []
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    lines.append(f"# RecImp Reflection Report")
    lines.append(f"\n_Generated {now}_  ")
    lines.append(f"_Strategies: {len(stats_list)}_\n")

    for s in stats_list:
        lines.append(f"## {s.strategy}  — {s.verdict}\n")
        lines.append(f"> {s.verdict_reason}\n")
        wr = (s.win_count / max(1, s.close_count)) if s.close_count else 0.0
        lines.append(f"- **Trades**: {s.trade_count} (verified {s.verified_count}, closed {s.close_count})")
        lines.append(f"- **Win rate**: {wr:.1%} ({s.win_count} winners)")
        lines.append(f"- **Realized P&L**: ${s.realized_pnl_usd:.2f}  (avg ${s.avg_pnl_usd:.2f}/trade)")
        lines.append(f"- **Max drawdown**: ${s.max_drawdown_usd:.2f}")
        lines.append(f"- **Gas**: total {s.total_gas:,}  avg {s.avg_gas_per_tx:,.1f}/tx")
        lines.append(f"- **First seen**: {s.first_seen}")
        lines.append(f"- **Last seen**: {s.last_seen}")
        if s.last_params:
            lines.append(f"- **Params**: `{json.dumps(s.last_params)}`")
        recs = advisories.get(s.strategy, [])
        if recs:
            lines.append(f"\n### Recommended tuning\n")
            for r in recs:
                lines.append(
                    f"- **{r.param}**: `{r.old!r}` → `{r.new!r}` _(conf {r.confidence:.2f})_ — {r.rationale}"
                )
        lines.append("")

    return "\n".join(lines)


# --- HTML format -----------------------------------------------------------

_HTML_CSS = """
body { font: 14px/1.5 -apple-system, system-ui, sans-serif; max-width: 920px; margin: 24px auto; padding: 0 16px; color: #111; }
h1 { font-size: 22px; }
.strategy { border: 1px solid #ddd; border-radius: 8px; padding: 14px 18px; margin: 14px 0; }
.verdict { font-weight: 600; padding: 2px 8px; border-radius: 999px; font-size: 12px; }
.v-HEALTHY { background: #d4f4dd; color: #14532d; }
.v-UNDERPERFORMING { background: #fff1c2; color: #78350f; }
.v-BROKEN { background: #ffd5d5; color: #7f1d1d; }
.v-INSUFFICIENT_DATA { background: #eee; color: #555; }
table { border-collapse: collapse; margin: 8px 0 4px; }
td, th { padding: 4px 10px; border-bottom: 1px solid #eee; text-align: left; }
.rec { background: #f6f8ff; border-left: 3px solid #6c7cff; padding: 8px 10px; margin: 6px 0; }
.conf { font-weight: 600; }
"""


def _escape(s: str) -> str:
    return (
        s.replace("&", "&amp;")
         .replace("<", "&lt;")
         .replace(">", "&gt;")
    )


def render_html(
    stats_list: list[StrategyStats],
    *,
    advisories: dict[str, list[TuningRecommendation]] | None = None,
) -> str:
    advisories = advisories or {}
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    out: list[str] = [
        "<!doctype html>",
        "<html><head><meta charset='utf-8'>",
        f"<title>RecImp Report — {now}</title>",
        f"<style>{_HTML_CSS}</style></head><body>",
        f"<h1>RecImp Reflection Report</h1>",
        f"<p><em>Generated {_escape(now)} — {len(stats_list)} strateg{'y' if len(stats_list)==1 else 'ies'}</em></p>",
    ]
    for s in stats_list:
        wr = (s.win_count / max(1, s.close_count)) if s.close_count else 0.0
        out.append("<div class='strategy'>")
        out.append(
            f"<h2>{_escape(s.strategy)} "
            f"<span class='verdict v-{s.verdict}'>{_escape(s.verdict)}</span></h2>"
        )
        out.append(f"<p><em>{_escape(s.verdict_reason)}</em></p>")
        out.append("<table>")
        out.append(f"<tr><th>Trades</th><td>{s.trade_count} "
                   f"(verified {s.verified_count}, closed {s.close_count})</td></tr>")
        out.append(f"<tr><th>Win rate</th><td>{wr:.1%} ({s.win_count} winners)</td></tr>")
        out.append(f"<tr><th>Realized P&amp;L</th>"
                   f"<td>${s.realized_pnl_usd:.2f} (avg ${s.avg_pnl_usd:.2f}/trade)</td></tr>")
        out.append(f"<tr><th>Max drawdown</th><td>${s.max_drawdown_usd:.2f}</td></tr>")
        out.append(f"<tr><th>Gas</th>"
                   f"<td>total {s.total_gas:,} / avg {s.avg_gas_per_tx:,.1f} per tx</td></tr>")
        out.append(f"<tr><th>Window</th>"
                   f"<td>{_escape(s.first_seen)} → {_escape(s.last_seen)}</td></tr>")
        out.append("</table>")
        if s.last_params:
            out.append(f"<p><strong>Params:</strong> "
                       f"<code>{_escape(json.dumps(s.last_params))}</code></p>")

        recs = advisories.get(s.strategy, [])
        if recs:
            out.append("<h3>Recommended tuning</h3>")
            for r in recs:
                out.append(
                    "<div class='rec'>"
                    f"<div><code>{_escape(r.param)}: {r.old!r} → {r.new!r}</code> "
                    f"<span class='conf'>(conf {r.confidence:.2f})</span></div>"
                    f"<div><small>{_escape(r.rationale)}</small></div>"
                    "</div>"
                )

        out.append("</div>")
    out.append("</body></html>")
    return "\n".join(out)


# --- JSON format -----------------------------------------------------------

def render_json(
    stats_list: list[StrategyStats],
    *,
    advisories: dict[str, list[TuningRecommendation]] | None = None,
) -> str:
    advisories = advisories or {}
    payload = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "strategies": [],
    }
    for s in stats_list:
        item = _stats_dict(s)
        recs = advisories.get(s.strategy, [])
        item["recommendations"] = [_rec_dict(r) for r in recs]
        payload["strategies"].append(item)
    return json.dumps(payload, indent=2)


# --- Dispatcher ------------------------------------------------------------

def render(
    stats_list: list[StrategyStats],
    *,
    fmt: str = "text",
    advisories: dict[str, list[TuningRecommendation]] | None = None,
    window: int | None = None,
) -> str:
    fmt = (fmt or "text").lower()
    if fmt == "json":
        return render_json(stats_list, advisories=advisories)
    if fmt in ("md", "markdown"):
        return render_markdown(stats_list, advisories=advisories)
    if fmt == "html":
        return render_html(stats_list, advisories=advisories)
    return render_text(stats_list, window=window, advisories=advisories)
