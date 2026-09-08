"""Phase C — source empirical-weight calibrator (SHADOW ONLY).

Runs weekly on the VPS (invoked from calibration_report.run()). For each calibration
source it scores matured signals by forward excess-return vs SPY, maps to an empirical
weight (CI-gated + shrunk toward the YAML prior), and appends a snapshot row to
`source_empirical_weights`. Pure measurement:

    * DOES NOT modify claim_engine_weights, source_weights.yaml, or any decision path.
    * weight_for() keeps returning priors. These weights are DISPLAY/LOG only.

options_flow_unusual is scored CONTRARIAN @20d per PRE-REGISTRATION-options-flow.md
(validated 2026-07-10: +3.69% beta-adjusted alpha, full skepticism battery passed).
Other sources: openinsider 20d follow, capitol 5d follow, finra 5d follow.

Deployed to /opt/sentinel/source_calibrator.py. Zero LLM cost. Self-contained; if
prices can't be fetched it logs and writes nothing (never breaks the caller).
"""
from __future__ import annotations
import json, math, logging, sqlite3
from datetime import datetime, timezone, timedelta
from pathlib import Path

log = logging.getLogger("source_calibrator")
DB_PATH = Path(__file__).parent / "sentinel.db"

# source -> (horizon_days, convention, prior, src_type)
SPEC = {
    "options_flow_unusual":  (20, "contrarian", 0.50, "discrete"),
    "openinsider_cluster":   (20, "follow",     0.60, "discrete"),
    "capitol_trades_house":  (5,  "follow",     0.35, "discrete"),
    "finra_short_zscore":    (5,  "follow",     0.40, "trend"),
}
K_SHRINK = 30

# A source with no new sentiment_signals rows in this many days is stale —
# flag it rather than silently blend months-old events into today's weight
# as if they were fresh. Added 2026-08-17: finra_short_zscore (dead since
# 2026-05-25) and capitol_trades_house (dead since 2026-07-02) were both
# still producing weekly weight_blended snapshots off frozen historical n.
_STALE_DAYS = 45

_DDL = """
CREATE TABLE IF NOT EXISTS source_empirical_weights (
    source_id      TEXT NOT NULL,
    computed_at    TEXT NOT NULL,
    horizon_days   INTEGER,
    convention     TEXT,
    n              INTEGER,
    hit_pct        REAL,
    mean_excess    REAL,
    ci_lo          REAL,
    ci_hi          REAL,
    weight_prior   REAL,
    weight_emp     REAL,
    weight_blended REAL,
    stale          INTEGER DEFAULT 0,
    PRIMARY KEY (source_id, computed_at)
);
"""


def _last_event_date(source: str) -> str | None:
    with _conn() as con:
        row = con.execute(
            "SELECT MAX(ts) FROM sentiment_signals WHERE source=?", (source,)
        ).fetchone()
    return row[0] if row else None


def _is_stale(last_ts: str | None) -> bool:
    if not last_ts:
        return True
    try:
        last = datetime.fromisoformat(last_ts.replace("Z", "+00:00").split("#")[0])
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
    except ValueError:
        return False
    return (datetime.now(timezone.utc) - last) > timedelta(days=_STALE_DAYS)


def _conn():
    con = sqlite3.connect(DB_PATH); con.row_factory = sqlite3.Row
    return con


def _direction(source: str, md: dict) -> int:
    if source == "openinsider_cluster":
        return 1 if md.get("direction") == "bullish" else 0
    if source == "capitol_trades_house":
        return {"P": 1, "S": -1}.get(md.get("trade_type"), 0)
    if source == "finra_short_zscore":
        dv = md.get("direction", "")
        return 1 if "bull" in dv else (-1 if "bear" in dv else 0)
    if source == "options_flow_unusual":
        return {"C": 1, "P": -1}.get(md.get("side"), 0)
    return 0


def _net_events(source: str):
    """Aggregate to one net directional event per (ticker, date). Returns
    {(ticker,date): net_int}. Excludes non-ticker symbols."""
    from collections import defaultdict
    acc = defaultdict(float)
    with _conn() as con:
        for r in con.execute("SELECT ticker, ts, metadata FROM sentiment_signals WHERE source=?", (source,)):
            tk = (r["ticker"] or "").upper()
            if not tk or tk in ("NONE", "N/A") or ":" in tk:
                continue
            try:
                md = json.loads(r["metadata"] or "{}")
            except Exception:
                md = {}
            d = _direction(source, md)
            if d:
                acc[(tk, str(r["ts"])[:10])] += d
    return {k: (1 if v > 0 else -1) for k, v in acc.items() if v != 0}


def _weight_from_stats(mean_ex, lo, hi, src_type):
    if hi < 0:
        w = 0.30
    elif lo > 0 and mean_ex >= 2.0:
        w = 0.60
    elif lo > 0:
        w = 0.50
    elif mean_ex > 0:
        w = 0.45
    else:
        w = 0.38
    return min(w, 0.40) if src_type == "trend" else w


def _fetch_prices(tickers):
    """Returns (prices dict {ticker: DataFrame[Open,Close]}, spy DataFrame) or (None,None)."""
    try:
        import yfinance as yf, pandas as pd
    except Exception as e:
        log.warning("source_calibrator: yfinance/pandas unavailable: %s", e); return None, None
    start = (datetime.now(timezone.utc) - timedelta(days=160)).strftime("%Y-%m-%d")

    def dl(sym):
        try:
            df = yf.download(sym, start=start, auto_adjust=False, progress=False, threads=False)
            if df is None or len(df) < 5:
                return None
            if hasattr(df.columns, "get_level_values") and df.columns.nlevels > 1:
                df.columns = df.columns.get_level_values(0)
            return df[["Open", "Close"]].dropna()
        except Exception:
            return None

    spy = dl("SPY")
    if spy is None or len(spy) < 40:
        log.warning("source_calibrator: SPY fetch failed — abort (no write)"); return None, None
    prices = {}
    for t in tickers:
        d = dl(t)
        if d is not None and not d.empty:
            prices[t] = d
    return prices, spy


def _next_open_idx(signal_date, trading_dates):
    """Reject signals outside the downloaded window instead of moving entry."""
    if not trading_dates:
        return None
    signal_day = datetime.fromisoformat(str(signal_date)[:10]).date()
    if signal_day < trading_dates[0].date():
        return None
    return next((i for i, day in enumerate(trading_dates) if day.date() > signal_day), None)


def run(write: bool = True) -> dict:
    """Compute a shadow snapshot for every source; persist unless write=False.
    Returns summary dict. Never raises — logs and returns {} on any hard failure."""
    try:
        import numpy as np, pandas as pd
    except Exception as e:
        log.warning("source_calibrator: numpy/pandas unavailable: %s", e); return {}

    per_source = {s: _net_events(s) for s in SPEC}
    tickers = sorted({tk for ev in per_source.values() for (tk, _d) in ev})
    if not tickers:
        log.info("source_calibrator: no events yet"); return {}

    prices, spy = _fetch_prices(tickers)
    if prices is None:
        return {}
    SD = list(spy.index); so = spy["Open"]; sc = spy["Close"]

    def next_open_idx(ds):
        return _next_open_idx(ds, SD)

    now = datetime.now(timezone.utc).isoformat()
    rows = []      # tuples for insert
    summary = {}
    stale_sources = []
    for source, (H, conv, prior, stype) in SPEC.items():
        stale = _is_stale(_last_event_date(source))
        if stale:
            stale_sources.append(source)
        signed = []
        for (tk, date), net in per_source[source].items():
            if tk not in prices:
                continue
            pdf = prices[tk]; ei = next_open_idx(date)
            if ei is None or ei + H >= len(SD):
                continue
            edt, xdt = SD[ei], SD[ei + H]
            if edt not in pdf.index or xdt not in pdf.index:
                continue
            ep = float(pdf.loc[edt, "Open"]); es = float(so.iloc[ei])
            if ep <= 0 or es <= 0:
                continue
            xp = float(pdf.loc[xdt, "Close"]); xs = float(sc.iloc[ei + H])
            excess = (xp / ep - 1 - (xs / es - 1)) * 100.0
            pred = net if conv == "follow" else -net     # contrarian flips it
            signed.append(excess * pred)
        n = len(signed)
        if n < 2:
            w_emp = prior; w_blend = prior; mean_ex = hit = lo = hi = None
        else:
            arr = np.array(signed, float)
            mean_ex = float(arr.mean()); hit = float((arr > 0).mean() * 100)
            se = arr.std(ddof=1) / math.sqrt(n)
            lo, hi = mean_ex - 1.96 * se, mean_ex + 1.96 * se
            w_emp = _weight_from_stats(mean_ex, lo, hi, stype)
            w_blend = (n * w_emp + K_SHRINK * prior) / (n + K_SHRINK)
        rows.append((source, now, H, conv, n,
                     round(hit, 1) if hit is not None else None,
                     round(mean_ex, 3) if mean_ex is not None else None,
                     round(lo, 3) if lo is not None else None,
                     round(hi, 3) if hi is not None else None,
                     prior, round(w_emp, 3), round(w_blend, 3), int(stale)))
        summary[source] = {"n": n, "conv": conv, "H": H,
                           "mean_excess": round(mean_ex, 2) if mean_ex is not None else None,
                           "w_blended": round(w_blend, 3), "stale": stale}

    if stale_sources:
        log.warning(
            "source_calibrator: %d source(s) have produced no new events in "
            "%d+ days (weight_blended below is based on stale historical data, "
            "not current signal): %s",
            len(stale_sources), _STALE_DAYS, ", ".join(stale_sources),
        )

    if write:
        with _conn() as con:
            con.executescript(_DDL)
            con.executemany(
                "INSERT OR REPLACE INTO source_empirical_weights "
                "(source_id,computed_at,horizon_days,convention,n,hit_pct,mean_excess,"
                "ci_lo,ci_hi,weight_prior,weight_emp,weight_blended,stale) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                rows)
        log.info("source_calibrator: wrote %d snapshots: %s", len(rows), json.dumps(summary, default=str))
    else:
        log.info("source_calibrator DRY: %s", json.dumps(summary, default=str))
    return summary


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    dry = "--dry" in sys.argv
    if dry:
        print("[DRY RUN] computing, no DB write")
    print(json.dumps(run(write=not dry), indent=2, default=str))
