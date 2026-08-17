"""Track A mini-backtest: compare 3 ranking strategies on the live snapshot window.

Strategies scored on each daily snapshot:
  DCA          - sort allocation_usd desc, top 5 (>0)
  ActionCenter - sort by action tier, then composite score (port of index.html JS)
  UpsideOnly   - sort upside_pct desc among STRONG BUY/BUY rows, top 5

Forward returns at +5d via yfinance, excess vs SPY.
"""
from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import math

import pandas as pd
import yfinance as yf


def wilson_ci(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    margin = z * math.sqrt((p * (1 - p) + z * z / (4 * n)) / n) / denom
    return (max(0.0, center - margin), min(1.0, center + margin))

REPO = Path(r"c:\Users\kaiha\Desktop\Repos\alpha-director")
DATA_PATH = "docs/data.json"
SIDECAR_PATH = "docs/charts/analysis.json"
TIER_ORDER = ["STRONG BUY", "BUY", "WATCH", "TRIM", "EXIT"]
TOP_N = 5
HORIZONS = [3, 5, 10]


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=REPO, capture_output=True, text=True, check=True
    ).stdout


def list_snapshots() -> list[tuple[str, str, datetime]]:
    """Return [(sha, path, commit_dt_utc)] for one snapshot per trading day per file.

    Strategy: for each calendar day (Israel time), pick the LATEST commit of that day.
    """
    out = []
    for path in (DATA_PATH, SIDECAR_PATH):
        log = _git("log", "--format=%H|%aI", "--", path).strip().splitlines()
        per_day: dict[str, tuple[str, datetime]] = {}
        for line in log:
            sha, iso = line.split("|", 1)
            dt = datetime.fromisoformat(iso).astimezone(timezone.utc)
            day = dt.date().isoformat()
            cur = per_day.get(day)
            if cur is None or dt > cur[1]:
                per_day[day] = (sha, dt)
        for day, (sha, dt) in sorted(per_day.items()):
            out.append((sha, path, dt))
    return out


def read_at(sha: str, path: str) -> dict | None:
    try:
        raw = _git("show", f"{sha}:{path}")
        return json.loads(raw)
    except subprocess.CalledProcessError:
        return None


@dataclass
class Pick:
    snapshot_date: str
    ticker: str
    strategy: str
    rank: int
    action: str
    upside_pct: float | None
    allocation_usd: float | None
    score: float


def score_action_center(row: dict, conf_pct: float | None) -> float:
    """Port of index.html:2138-2148 composite score.

    Note: portfolio positions never carry brain.confidence -> defaults to 5.
    """
    c = (conf_pct / 100) if conf_pct is not None else 0.7
    brain = (row.get("confidence") or 5) / 10
    upside = min(row.get("upside_pct") or 0, 100) / 100
    return c * 0.60 + brain * 0.15 + upside * 0.25


def collect_universe(data: dict, sidecar: dict | None) -> list[dict]:
    """Flatten portfolio.positions + outside_opps + dca_new_picks.

    Apply effective_action from sidecar (mirrors _applyEffectiveActions in JS).
    Returns one row per unique ticker (portfolio wins on conflict).
    """
    rows: dict[str, dict] = {}

    def patch(p: dict, bucket: str) -> dict:
        t = (p.get("ticker") or "").upper()
        if not t:
            return {}
        rec = (sidecar or {}).get(t, {}).get("analysis") or {}
        eff_action = rec.get("effective_action") or p.get("action") or ""
        conf_pct = rec.get("confidence_pct")
        return {
            "ticker": t,
            "bucket": bucket,
            "action": eff_action.upper(),
            "_orig_action": (p.get("action") or "").upper(),
            "upside_pct": p.get("upside_pct"),
            "allocation_usd": p.get("allocation_usd") or 0,
            # New sanitized snapshots carry allocation_pct instead of _usd; both
            # are monotonic within a snapshot so DCA ranking is unchanged.
            "allocation_pct": p.get("allocation_pct"),
            "rsi": p.get("rsi"),
            "above_200": p.get("above_200"),
            "confidence_pct": conf_pct,
            "brain_confidence": p.get("confidence"),
            "price": p.get("price"),
        }

    for p in (data.get("portfolio", {}) or {}).get("positions", []) or []:
        r = patch(p, "portfolio")
        if r:
            rows[r["ticker"]] = r
    for p in data.get("outside_opps", []) or []:
        r = patch(p, "outside")
        if r and r["ticker"] not in rows:
            rows[r["ticker"]] = r
    for p in data.get("dca_new_picks", []) or []:
        r = patch(p, "dca_pick")
        if r and r["ticker"] not in rows:
            rows[r["ticker"]] = r
    return list(rows.values())


def _dca_rank(r: dict) -> float:
    """Allocation weight for DCA ranking — prefer allocation_pct (sanitized
    snapshots), fall back to allocation_usd (legacy snapshots)."""
    pct = r.get("allocation_pct")
    return pct if pct is not None else (r.get("allocation_usd") or 0)


def pick_dca(universe: list[dict], snap_date: str) -> list[Pick]:
    cands = [r for r in universe if _dca_rank(r) > 0]
    cands.sort(key=_dca_rank, reverse=True)
    return [
        Pick(snap_date, r["ticker"], "DCA", i + 1, r["action"],
             r["upside_pct"], r["allocation_usd"], _dca_rank(r))
        for i, r in enumerate(cands[:TOP_N])
    ]


def pick_action_center(universe: list[dict], snap_date: str) -> list[Pick]:
    actionable = [r for r in universe if r["action"] in TIER_ORDER]

    def key(r: dict):
        tier_idx = TIER_ORDER.index(r["action"])
        score = score_action_center(
            {"confidence": r["brain_confidence"], "upside_pct": r["upside_pct"]},
            r["confidence_pct"],
        )
        return (tier_idx, -score)

    actionable.sort(key=key)
    return [
        Pick(snap_date, r["ticker"], "ActionCenter", i + 1, r["action"],
             r["upside_pct"], r["allocation_usd"],
             score_action_center(
                 {"confidence": r["brain_confidence"], "upside_pct": r["upside_pct"]},
                 r["confidence_pct"]))
        for i, r in enumerate(actionable[:TOP_N])
    ]


def pick_high_conviction(universe: list[dict], snap_date: str) -> list[Pick]:
    """Trend-confirmed conviction: STRONG BUY only, above_50 & above_200,
    30 < RSI < 75, sort by upside_pct desc, top 3."""
    cands = []
    for r in universe:
        if r["action"] != "STRONG BUY":
            continue
        if not (r.get("above_200") and r.get("above_50") if "above_50" in r else r.get("above_200")):
            continue
        rsi = r.get("rsi")
        if rsi is None or not (30 < rsi < 75):
            continue
        if (r.get("upside_pct") or 0) <= 0:
            continue
        cands.append(r)
    cands.sort(key=lambda r: r["upside_pct"] or 0, reverse=True)
    return [
        Pick(snap_date, r["ticker"], "HighConviction", i + 1, r["action"],
             r["upside_pct"], r["allocation_usd"], r["upside_pct"] or 0)
        for i, r in enumerate(cands[:3])
    ]


def pick_upside_only(universe: list[dict], snap_date: str) -> list[Pick]:
    cands = [r for r in universe
             if r["action"] in ("STRONG BUY", "BUY") and (r["upside_pct"] or 0) > 0]
    cands.sort(key=lambda r: r["upside_pct"] or 0, reverse=True)
    return [
        Pick(snap_date, r["ticker"], "UpsideOnly", i + 1, r["action"],
             r["upside_pct"], r["allocation_usd"], r["upside_pct"] or 0)
        for i, r in enumerate(cands[:TOP_N])
    ]


def build_picks() -> tuple[pd.DataFrame, list[str]]:
    """Walk per-day snapshots; for each day, pair latest data.json with latest sidecar."""
    snaps = list_snapshots()
    data_by_day: dict[str, str] = {}
    side_by_day: dict[str, str] = {}
    for sha, path, dt in snaps:
        day = dt.date().isoformat()
        if path == DATA_PATH:
            data_by_day[day] = sha
        else:
            side_by_day[day] = sha

    all_picks: list[Pick] = []
    days_used: list[str] = []
    for day, data_sha in sorted(data_by_day.items()):
        data = read_at(data_sha, DATA_PATH)
        if not data:
            continue
        sidecar_sha = side_by_day.get(day)
        sidecar = read_at(sidecar_sha, SIDECAR_PATH) if sidecar_sha else None
        universe = collect_universe(data, sidecar)
        if not universe:
            continue
        days_used.append(day)
        all_picks.extend(pick_dca(universe, day))
        all_picks.extend(pick_action_center(universe, day))
        all_picks.extend(pick_upside_only(universe, day))
        all_picks.extend(pick_high_conviction(universe, day))

    df = pd.DataFrame([p.__dict__ for p in all_picks])
    return df, days_used


def fetch_prices(tickers: Iterable[str], start: str, end: str) -> pd.DataFrame:
    tickers = sorted(set(tickers))
    print(f"  yfinance: {len(tickers)} tickers, {start} -> {end}")
    df = yf.download(tickers, start=start, end=end, progress=False, auto_adjust=True)
    if isinstance(df.columns, pd.MultiIndex):
        df = df["Close"]
    elif "Close" in df.columns:
        df = df[["Close"]]
        df.columns = tickers if len(tickers) == 1 else df.columns
    return df


def attach_forward_returns(picks: pd.DataFrame) -> pd.DataFrame:
    if picks.empty:
        return picks
    tickers = list(set(picks["ticker"].tolist()) | {"SPY"})
    start = (pd.Timestamp(picks["snapshot_date"].min()) - pd.Timedelta(days=3)).date().isoformat()
    end = (pd.Timestamp(picks["snapshot_date"].max()) + pd.Timedelta(days=max(HORIZONS) + 7)).date().isoformat()
    px = fetch_prices(tickers, start, end)
    px = px.sort_index()
    trading_days = px.index

    def fwd_return(ticker: str, snap: str, h: int) -> float | None:
        snap_ts = pd.Timestamp(snap)
        future = trading_days[trading_days >= snap_ts]
        if len(future) <= h:
            return None
        d0, d1 = future[0], future[h]
        try:
            p0 = px.loc[d0, ticker]
            p1 = px.loc[d1, ticker]
        except KeyError:
            return None
        if pd.isna(p0) or pd.isna(p1) or p0 == 0:
            return None
        return float(p1 / p0 - 1)

    for h in HORIZONS:
        picks[f"ret_{h}d"] = picks.apply(
            lambda r: fwd_return(r["ticker"], r["snapshot_date"], h), axis=1
        )
        picks[f"spy_{h}d"] = picks.apply(
            lambda r: fwd_return("SPY", r["snapshot_date"], h), axis=1
        )
        picks[f"excess_{h}d"] = picks[f"ret_{h}d"] - picks[f"spy_{h}d"]
    return picks


def report(picks: pd.DataFrame) -> str:
    lines = []
    lines.append("=" * 78)
    lines.append("Alpha Director — Formula Comparison Backtest (Track A)")
    lines.append("=" * 78)
    lines.append(f"Snapshot days: {picks['snapshot_date'].nunique()} | total picks: {len(picks)}")
    lines.append(f"Window: {picks['snapshot_date'].min()} -> {picks['snapshot_date'].max()}")
    lines.append("")

    for h in HORIZONS:
        col = f"excess_{h}d"
        usable = picks.dropna(subset=[col])
        lines.append(f"### Forward window: +{h}d (vs SPY) — {len(usable)} of {len(picks)} picks have forward data")
        if usable.empty:
            lines.append("  (no completed forward windows yet)")
            lines.append("")
            continue
        agg = usable.groupby("strategy")[col].agg(
            n="count",
            mean_excess="mean",
            median_excess="median",
            hit_rate=lambda s: (s > 0).mean(),
            best="max",
            worst="min",
        ).round(4)
        ci_rows = []
        for strat, g in usable.groupby("strategy"):
            n = int(g.shape[0])
            k = int((g[col] > 0).sum())
            lo, hi = wilson_ci(k, n)
            ci_rows.append({"strategy": strat, "ci95_low": round(lo, 3), "ci95_high": round(hi, 3)})
        ci = pd.DataFrame(ci_rows).set_index("strategy")
        agg = agg.join(ci)
        lines.append(agg.to_string())
        lines.append("")

    lines.append("### Pick overlap (any horizon)")
    pivot = picks.groupby(["snapshot_date", "strategy"])["ticker"].apply(
        lambda s: ",".join(sorted(s.unique()))
    ).unstack("strategy")
    lines.append(pivot.to_string())
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    print("[1/3] Walking git for snapshots ...")
    picks, days = build_picks()
    print(f"      {len(picks)} picks across {len(days)} days")
    if picks.empty:
        print("No picks found — aborting.")
        return
    print("[2/3] Fetching forward prices ...")
    picks = attach_forward_returns(picks)
    print("[3/3] Building report ...")
    out_csv = REPO / "backtest" / "picks.csv"
    out_md = REPO / "backtest" / "report.md"
    picks.to_csv(out_csv, index=False)
    txt = report(picks)
    out_md.write_text(txt, encoding="utf-8")
    print()
    print(txt)
    print(f"\nWrote: {out_csv}\nWrote: {out_md}")


if __name__ == "__main__":
    main()
