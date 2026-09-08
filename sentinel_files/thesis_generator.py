"""
Machine-thesis generator — auto-writes pre-registered theses from live events so
the Brier/Kelly calibration engine stops starving (warming_up gate: needs 30
closed-with-Brier theses, currently 18). Zero LLM. Pure Python + yfinance/db.

Deploy target: /opt/sentinel/thesis_generator.py, invoked daily by sentinel.py
right after thesis_scorer. Idempotent: thesis_id is deterministic per (ticker,
event, date); re-runs upsert the same row, never duplicate.

MEASUREMENT theses, not capital actions:
  - Recorded UNCONDITIONALLY (we bypass the validator's capital regime-BLOCK gate;
    we are measuring whether the signal predicts, not deciding to trade).
  - Enriched exactly like hand-authored theses (sentiment_at_entry snapshot +
    regime_at_entry) so the existing calibration_report divergence/regime/bucket
    breakdowns keep working.
  - Long-biased to match thesis_scorer (WIN = price up vs entry). Only events that
    map to a *bullish* expectation are emitted in v1.

Event → thesis (v1):
  1. options_flow_contrarian  [VALIDATED CANDIDATE, pre-registered]
     Net unusual flow per ticker/day (side C=+1, P=-1, netted). CONTRARIAN:
     net PUT-heavy (net<0, |net|>=MIN_NET) => expect OUTPERFORM => BULLISH thesis
     ("fade the unusual puts"). Net CALL-heavy maps to a bearish expectation which
     the long-only scorer can't grade, so it is NOT emitted (logged as skipped).
     P(win)=0.60 (study hit ~64% @20d; kept conservative for honest Brier).
     Horizon 20 trading days. This forward-tracks the options-flow pre-registration
     across the current (post-study) regime — exactly what that doc asked for.

  2. discovery_confirmed   [scaffolded] — CONFIRMED-tier names => bullish thesis.
     Emits only if a confirmed list is available; degrades to empty otherwise.

  3. regime_flip           [scaffolded] — SPY macro thesis on a regime transition.
     Compares regime.json to a persisted last-regime; fires only on an actual flip.

Run:  python thesis_generator.py --dry-run   # print candidates, upsert NOTHING
      python thesis_generator.py             # upsert OPEN theses (live)
"""
from __future__ import annotations

import json
import logging
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

log = logging.getLogger("thesis_generator")

# ── Tunables (pre-registered; change = new pre-registration) ──────────────────
MIN_NET_CONTRACTS = 3      # dose-response: require a clear net put lean
OPTIONS_HORIZON_TD = 20    # trading days (the validated horizon)
OPTIONS_PWIN = 0.60        # conservative vs study's ~64% hit → honest Brier
OPTIONS_STOP_FRAC = 0.12   # hard stop 12% below entry (spec-class bounce)
CONVICTION = 7             # machine floor (validator requires >=7)

_HIGH_BETA_HINT = {  # study showed the edge concentrates here; used only to tag bucket
    "COIN","CLSK","BMNR","IBIT","IONQ","ETHA","MSTR","MARA","RIOT","HOOD","HIMS","SOFI",
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _latest_trading_date(con) -> str:
    row = con.execute(
        "SELECT MAX(substr(ts,1,10)) FROM sentiment_signals WHERE source='options_flow_unusual'"
    ).fetchone()
    return row[0] if row and row[0] else _now().date().isoformat()


def _price(db, ticker: str) -> float | None:
    """Share the scorer's dated-quote validation for measurement entries."""
    from thesis_scorer import _current_price
    price = _current_price(ticker)
    return round(price, 4) if price is not None else None


def _bucket_for(ticker: str) -> str:
    return "spec" if ticker in _HIGH_BETA_HINT else "swing"


# ── Event gatherers (return list of candidate dicts, pre-enrichment) ──────────

def gather_options_flow(con, today: str) -> list[dict]:
    """Net unusual flow per ticker for `today`; emit BULLISH contrarian candidates
    for net-PUT-heavy tickers. Returns candidates + a skipped-summary via log."""
    net = defaultdict(lambda: {"sum": 0, "n": 0})
    for r in con.execute(
        "SELECT ticker, metadata FROM sentiment_signals "
        "WHERE source='options_flow_unusual' AND substr(ts,1,10)=?", (today,)
    ):
        tk = (r["ticker"] or "").upper()
        if not tk or tk.startswith("PM:"):
            continue
        try:
            side = (json.loads(r["metadata"] or "{}")).get("side")
        except Exception:
            side = None
        d = 1 if side == "C" else (-1 if side == "P" else 0)
        if d == 0:
            continue
        net[tk]["sum"] += d
        net[tk]["n"] += 1

    cands, skipped_call = [], 0
    for tk, v in net.items():
        s = v["sum"]
        if s <= -MIN_NET_CONTRACTS:          # PUT-heavy → contrarian BULLISH
            cands.append({
                "event": "options_flow_contrarian",
                "code": "AF",
                "ticker": tk,
                "net": s, "n_contracts": v["n"],
                "p_win": OPTIONS_PWIN,
                "horizon_td": OPTIONS_HORIZON_TD,
                "stop_frac": OPTIONS_STOP_FRAC,
                "catalyst": f"Fade unusual PUT flow (net={s}, {v['n']} contracts)",
                "rationale": "Contrarian: unusual PUT flow → 20d outperformance (pre-reg options-flow)",
            })
        elif s >= MIN_NET_CONTRACTS:          # CALL-heavy → bearish, not gradable long-only
            skipped_call += 1
    log.info("options_flow: %d put-heavy(bullish) candidates, %d call-heavy skipped (bearish, long-only can't grade)",
             len(cands), skipped_call)
    return cands


def gather_discovery_confirmed(con) -> list[dict]:
    """CONFIRMED-tier discovery names → bullish thesis. Scaffold: reads an optional
    discovery output; degrades to empty when unavailable."""
    cands = []
    for path in ("/opt/sentinel/discovery_state.json", "/opt/sentinel/discovery.json"):
        p = Path(path)
        if not p.exists():
            continue
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        items = data.get("confirmed") or data.get("CONFIRMED") or []
        for it in items:
            tk = (it.get("ticker") if isinstance(it, dict) else str(it) or "").upper()
            if not tk:
                continue
            cands.append({
                "event": "discovery_confirmed", "code": "DC", "ticker": tk,
                "net": None, "n_contracts": None, "p_win": 0.55, "horizon_td": 20,
                "stop_frac": 0.12,
                "catalyst": "Discovery CONFIRMED tier (QUALIFIED + BUY-grade action)",
                "rationale": "Discovery funnel promoted this name to CONFIRMED",
            })
        break
    log.info("discovery_confirmed: %d candidates", len(cands))
    return cands


def gather_regime_flip(con) -> list[dict]:
    """SPY macro thesis on a regime transition. Compares regime.json to a persisted
    last-regime state; fires only on an actual flip. Scaffold."""
    reg_p = Path("/opt/sentinel/regime.json")
    state_p = Path("/opt/sentinel/.thesis_gen_last_regime")
    if not reg_p.exists():
        return []
    try:
        cur_regime = json.loads(reg_p.read_text(encoding="utf-8")).get("regime")
    except Exception:
        return []
    last = state_p.read_text().strip() if state_p.exists() else None
    cands = []
    if last and cur_regime and cur_regime != last:
        # bullish only on flip TO a risk-on-ish regime (long-only gradable)
        if cur_regime in ("RISK_ON", "NEUTRAL") and last in ("RISK_OFF", "CRISIS"):
            cands.append({
                "event": "regime_flip", "code": "RG", "ticker": "SPY",
                "net": None, "n_contracts": None, "p_win": 0.55, "horizon_td": 20,
                "stop_frac": 0.08,
                "catalyst": f"Regime flip {last}→{cur_regime}",
                "rationale": "Regime recovered from risk-off; SPY mean-reversion",
            })
    log.info("regime_flip: last=%s cur=%s → %d candidates", last, cur_regime, len(cands))
    return cands


# ── Thesis assembly + enrichment ──────────────────────────────────────────────

def build_thesis(db, cand: dict, today: str, reg: dict, sentiment_fn) -> dict | None:
    tk = cand["ticker"]
    entry = _price(db, tk)
    if entry is None:
        log.warning("no price for %s — skipping", tk)
        return None
    thesis_id = f"{tk}_{today}_{cand['code']}"
    time_stop = (datetime.fromisoformat(today) + timedelta(days=round(cand["horizon_td"] * 1.4))).date().isoformat()
    hard_stop = round(entry * (1 - cand["stop_frac"]), 4)
    sent = sentiment_fn(tk) if sentiment_fn else {}
    return {
        "thesis_id": thesis_id,
        "ticker": tk,
        "thesis_date": today,
        "bucket": _bucket_for(tk),
        "conviction": CONVICTION,
        "probability": float(cand["p_win"]),
        "time_horizon": f"{cand['horizon_td']}d",
        "entry_price": entry,
        "hard_stop": hard_stop,
        "time_stop": time_stop,
        "catalyst": cand["catalyst"],
        "catalyst_date": today,
        "sizing_rec": 0.0,                      # measurement thesis → no capital
        "lifecycle": "entry",
        "red_team_verdict": "AUTO",
        "red_team_date": today,
        "outcome": "null",
        "outcome_date": None,
        "outcome_price": None,
        "brier_contribution": None,
        "sentiment_composite": sent.get("composite_score"),
        "divergence_flag": sent.get("divergence_flag"),
        "smart_side_aligned": (1 if sent.get("smart_side_aligned") is True
                               else 0 if sent.get("smart_side_aligned") is False else None),
        "correlation_flag": "AUTO",
        "correlation_detail": cand["rationale"],
        "regime_at_entry": reg.get("regime"),
        "status": "OPEN",
        "md_path": None,
        "_event": cand["event"],
        "_net": cand.get("net"),
    }


def run(dry_run: bool = True) -> list[dict]:
    import sqlite3
    sys.path.insert(0, "/opt/sentinel")
    import db
    try:
        db.init()
    except Exception:
        pass
    try:
        import regime_detector
        reg = regime_detector.current()
    except Exception as exc:
        log.warning("regime_detector.current() failed: %s", exc)
        reg = {}
    try:
        from thesis_validator import _sentiment_at_entry as sentiment_fn
    except Exception:
        sentiment_fn = None

    con = sqlite3.connect("/opt/sentinel/sentinel.db")
    con.row_factory = sqlite3.Row
    today = _latest_trading_date(con)

    cands = (gather_options_flow(con, today)
             + gather_discovery_confirmed(con)
             + gather_regime_flip(con))

    # existing thesis_ids for dedup (same ticker+day+code re-run)
    existing = {r[0] for r in con.execute("SELECT thesis_id FROM theses")}

    # tickers with an already-open thesis (any date) — added 2026-08-17.
    # thesis_id dedup above only catches an exact re-run on the same day; it
    # let the same ticker get a *new* thesis every day a candidate fired
    # while the prior one was still open (MU: 7 overlapping theses opened
    # 2026-07-11 through 2026-07-23, all before any of them closed, all
    # eventually STOP — 7 correlated samples counted as independent ones in
    # the calibration stats that Kelly sizing is based on).
    open_tickers = {r[0] for r in con.execute("SELECT ticker FROM theses WHERE status='OPEN'")}

    built, dup, dup_open = [], 0, 0
    for c in cands:
        tid = f"{c['ticker']}_{today}_{c['code']}"
        if tid in existing:
            dup += 1
            continue
        if c["ticker"] in open_tickers:
            dup_open += 1
            continue
        t = build_thesis(db, c, today, reg, sentiment_fn)
        if t:
            built.append(t)
            open_tickers.add(c["ticker"])
    con.close()

    log.info("built %d new theses (%d dedup-skipped, %d already-open-skipped), regime=%s, date=%s",
             len(built), dup, dup_open, reg.get("regime"), today)

    if not dry_run:
        for t in built:
            row = {k: v for k, v in t.items() if not k.startswith("_")}
            db.upsert_thesis(row)
            log.info("upserted %s (%s)", t["thesis_id"], t["_event"])

    return built


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    dry = "--dry-run" in sys.argv or "-n" in sys.argv
    built = run(dry_run=dry)
    print(f"\n{'DRY-RUN — nothing upserted' if dry else 'LIVE — upserted'}: {len(built)} theses\n")
    print(f"{'thesis_id':28s} {'evt':22s} {'buck':5s} {'entry':>9s} {'stop':>9s} "
          f"{'P':>4s} {'net':>5s} {'time_stop':>11s}  {'catalyst'}")
    for t in built:
        print(f"{t['thesis_id']:28s} {t['_event']:22s} {t['bucket']:5s} "
              f"{t['entry_price']:>9.2f} {t['hard_stop']:>9.2f} {t['probability']:>4.2f} "
              f"{str(t['_net'] if t['_net'] is not None else '—'):>5s} {t['time_stop']:>11s}  {t['catalyst']}")


if __name__ == "__main__":
    main()
