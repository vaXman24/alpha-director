"""
Thesis scorer — daily pass over open theses.

Exit detection (in priority order):
  1. Trailing stop: if pnl ≥ 30%, trail at entry+15%; ≥ 50% → entry+30%; ≥ 100% → entry+60%
     Price drops below trail_stop → WIN (protected profit)
  2. Hard stop: price ≤ hard_stop → STOP
  3. Time stop: today ≥ time_stop → WIN / DRAW / MISS based on pnl at expiry

Trim alerts (non-closing, Telegram only):
  +25% → "Consider trimming 25%"
  +50% → "Consider trimming 50%"
  +100% → "Trim 75% — double — let rest ride"

Each trim level fires only once (stored in theses.trim_alerted_level).

Run daily from sentinel.py or standalone. Zero LLM calls.
"""

from __future__ import annotations

import json
import logging
import math
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import db

log = logging.getLogger("thesis_scorer")

# Brier outcome values
_OUTCOME_VAL = {"WIN": 1.0, "LOSS": 0.0, "STOP": 0.0, "MISS": 0.0, "DRAW": 0.5}

# Trailing stop: pnl_pct threshold → lock-in floor as fraction of entry
_TRAIL_LEVELS = [
    (100.0, 1.60),   # up 100% → protect 60% gain (trail at entry×1.60)
    ( 50.0, 1.30),   # up  50% → protect 30% gain
    ( 30.0, 1.15),   # up  30% → protect 15% gain
]

# Trim alert thresholds and messages
_TRIM_LEVELS = [
    (100, "🎯 DOUBLE: Trim 75% — thesis delivered 100%+. Let remainder ride or take full exit."),
    ( 50, "✂️ TRIM: Up 50%+ — consider trimming 50%. Stop moved to entry+30%."),
    ( 25, "✂️ TRIM: Up 25%+ — consider trimming 25%. Protect partial gain."),
]


def _brier(probability: float, outcome_val: float) -> float:
    return round((float(probability) - outcome_val) ** 2, 4)


# ── Outcome write-back to thesis Markdown ─────────────────────────────────────
# Mirrors thesis_validator._patch_sentiment_block. Pure I/O; isolated try/except
# in _writeback_outcome_md so failure cannot abort scoring or mask the DB close.

_OUTCOME_ICON = {"WIN": "✅", "DRAW": "🟡", "MISS": "❌", "STOP": "🛑"}


def _patch_outcome_frontmatter(
    text: str, outcome: str, exit_price: float | None,
    brier: float, now: datetime,
) -> str:
    """Replace top-level frontmatter fields filled at close time."""
    iso = now.isoformat(timespec="seconds")
    price_s = f"{float(exit_price):.4f}" if exit_price is not None else "null"

    replacements = {
        "status":             "CLOSED",
        "outcome":            outcome,
        "outcome_date":       iso,
        "outcome_price":      price_s,
        "brier_contribution": f"{brier:.4f}",
    }
    for key, val in replacements.items():
        # Top-level YAML key at start of line; preserve any trailing comment.
        pattern = rf"(^{key}:\s*)([^\n#]*)(\s*#.*)?$"
        text = re.sub(
            pattern,
            lambda m, v=val: f"{m.group(1)}{v}{m.group(3) or ''}",
            text, count=1, flags=re.MULTILINE,
        )
    return text


def _build_outcome_section(
    thesis: dict, outcome: str, exit_price: float | None,
    brier: float, reason: str, now: datetime,
) -> str:
    icon = _OUTCOME_ICON.get(outcome, "•")

    entry = thesis.get("entry_price")
    if entry and exit_price is not None:
        try:
            pnl_pct = (float(exit_price) - float(entry)) / float(entry) * 100.0
            pnl_str = f"  (entry: ${float(entry):.2f} → {pnl_pct:+.1f}%)"
        except (TypeError, ValueError, ZeroDivisionError):
            pnl_str = ""
    else:
        pnl_str = ""

    held_str = ""
    d0 = _parse_date(thesis.get("thesis_date"))
    if d0:
        held_str = f"  (held {(now - d0).days} days)"

    if exit_price is not None:
        try:
            exit_line = f"- **Exit price:** ${float(exit_price):.2f}{pnl_str}"
        except (TypeError, ValueError):
            exit_line = "- **Exit price:** —"
    else:
        exit_line = "- **Exit price:** —"

    div_flag = thesis.get("divergence_flag") or "—"
    aligned  = thesis.get("smart_side_aligned")
    aligned_s = "✓" if aligned == 1 else ("✗" if aligned == 0 else "—")
    regime   = thesis.get("regime_at_entry") or "—"

    try:
        prob = float(thesis["probability"] if thesis.get("probability") is not None else 0.5)
    except (TypeError, ValueError):
        prob = 0.5

    return (
        "\n\n---\n\n"
        "## Outcome\n"
        "*Closed by thesis_scorer.py — do not edit*\n\n"
        f"- **Result:** {icon} {outcome}\n"
        f"- **Closed:** {now.strftime('%Y-%m-%d %H:%M UTC')}{held_str}\n"
        f"{exit_line}\n"
        f"- **P(win) at entry:** {prob:.2f}  →  **Brier:** {brier:.3f}  *(lower = better calibrated)*\n"
        f"- **Reason:** {reason}\n"
        f"- **Regime at entry:** {regime}  |  **Divergence:** {div_flag}  |  **Smart-side aligned:** {aligned_s}\n"
        f"- **Conviction:** {thesis.get('conviction') or '—'}  |  **Bucket:** {thesis.get('bucket') or '—'}\n"
    )


def _writeback_outcome_md(
    thesis: dict, outcome: str, exit_price: float | None,
    brier: float, reason: str, now: datetime,
) -> None:
    """Patch thesis MD with closure metadata. Never raises."""
    try:
        md_path = thesis.get("md_path")
        if not md_path:
            return
        p = Path(md_path)
        if not p.exists():
            log.info("Thesis MD not at %s; skipping writeback", md_path)
            return

        text = p.read_text(encoding="utf-8")
        original = text
        text = _patch_outcome_frontmatter(text, outcome, exit_price, brier, now)
        if "## Outcome" not in text:
            text = text.rstrip() + _build_outcome_section(
                thesis, outcome, exit_price, brier, reason, now,
            )

        if text != original:
            p.write_text(text, encoding="utf-8")
            log.info("Patched outcome into %s (%s)", p.name, outcome)
    except Exception as exc:
        log.warning(
            "MD writeback failed for %s: %s",
            thesis.get("thesis_id"), exc,
        )


def _parse_date(s: Any) -> datetime | None:
    if not s:
        return None
    s = str(s).strip()[:10]   # take YYYY-MM-DD portion only
    try:
        return datetime.strptime(s, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


# Four calendar days accommodates ordinary weekends and long weekends.
# This is a freshness bound, not an exchange-session/expiry execution model.
_MAX_QUOTE_AGE_SECONDS = 4 * 86400


def _validated_price(value, observed_at, now: datetime) -> float | None:
    try:
        price = float(value)
        stamp = datetime.fromisoformat(str(observed_at).replace("Z", "+00:00"))
        if stamp.tzinfo is None:
            stamp = stamp.replace(tzinfo=timezone.utc)
        age = (now - stamp).total_seconds()
        if math.isfinite(price) and price > 0 and 0 <= age <= _MAX_QUOTE_AGE_SECONDS:
            return price
    except (TypeError, ValueError, OverflowError):
        pass
    return None


def _current_price(ticker: str) -> float | None:
    """Use a recent dated quote; signal-change prices are not a quote cache."""
    try:
        import yfinance as yf
        history = yf.Ticker(ticker).history(period="5d")["Close"].dropna()
        if len(history):
            return _validated_price(history.iloc[-1], history.index[-1],
                                    datetime.now(timezone.utc))
    except Exception as exc:
        log.warning("Quote unavailable for %s (%s); deferring scoring", ticker, type(exc).__name__)
    return None


def _pnl_pct(price: float, entry: float) -> float:
    return (price - entry) / entry * 100.0


def _notify(ticker: str, thesis_id: str, headline: str, priority: str) -> None:
    try:
        from notifier import send_signal_notification
        items = [{
            "ticker":   ticker,
            "headline": headline,
            "source":   "Thesis Scorer",
            "priority": priority,
            "id":       f"score_{thesis_id}_{int(datetime.now(timezone.utc).timestamp())}",
        }]
        send_signal_notification([], items, {}, "")
    except Exception as exc:
        log.warning("Notification failed for %s: %s", thesis_id, exc)


def _check_trim_alerts(thesis: dict, price: float) -> None:
    """Fire trim alerts at +25/50/100% if not already sent. Does not close the thesis."""
    entry = thesis.get("entry_price")
    if not entry or float(entry) == 0:
        return

    pnl = _pnl_pct(price, float(entry))
    current_level = int(thesis.get("trim_alerted_level") or 0)
    thesis_id     = thesis["thesis_id"]
    ticker        = thesis["ticker"]

    for threshold, msg in _TRIM_LEVELS:
        if pnl >= threshold and current_level < threshold:
            full_msg = f"{msg}  |  {ticker}  pnl={pnl:.1f}%  entry={entry}"
            _notify(ticker, thesis_id, full_msg, "HIGH" if threshold >= 100 else "MEDIUM")
            db.update_trim_alert_level(thesis_id, threshold)
            log.info("Trim alert fired: %s  +%.0f%%  (threshold=%d)", ticker, pnl, threshold)
            break   # only the highest applicable level per pass


def _update_trailing_stop(thesis: dict, price: float) -> float | None:
    """
    Ratchet trail_stop upward based on current pnl. Returns current trail_stop after update.
    Only raises, never lowers. No-op if entry_price missing.
    """
    entry = thesis.get("entry_price")
    if not entry or float(entry) == 0:
        return thesis.get("trail_stop")

    pnl    = _pnl_pct(price, float(entry))
    new_ts = None
    for threshold, multiplier in _TRAIL_LEVELS:
        if pnl >= threshold:
            new_ts = round(float(entry) * multiplier, 2)
            break

    if new_ts is not None:
        current_ts = thesis.get("trail_stop")
        if current_ts is None or new_ts > float(current_ts):
            db.update_trail_stop(thesis["thesis_id"], new_ts)
            log.debug("Trail stop raised: %s → %.2f (pnl=%.1f%%)", thesis["ticker"], new_ts, pnl)
            return new_ts

    return thesis.get("trail_stop")


def _check_exits(thesis: dict, now: datetime) -> tuple[str | None, str, float | None]:
    """
    Returns (outcome, reason, exit_price) or (None, "", None) if no exit.
    """
    ticker = thesis["ticker"]
    price  = _current_price(ticker)
    if price is None:
        log.warning("Deferring %s: no valid recent quote", thesis.get("thesis_id"))
        return None, "awaiting valid recent quote", None

    # ── Trim alerts (non-closing) ─────────────────────────────────────────────
    if price and thesis.get("entry_price"):
        _check_trim_alerts(thesis, price)

    # ── Update and check trailing stop ────────────────────────────────────────
    if price and thesis.get("entry_price"):
        trail_stop = _update_trailing_stop(thesis, price)
        if trail_stop and float(price) <= float(trail_stop):
            return (
                "WIN" if price > float(thesis["entry_price"]) else "STOP",
                f"trailing stop {trail_stop:.2f} hit at observed price "
                f"(price={price:.2f}, entry={thesis['entry_price']})",
                price,
            )

    # ── Hard stop ─────────────────────────────────────────────────────────────
    hard_stop = thesis.get("hard_stop")
    if hard_stop and price is not None:
        try:
            if float(price) <= float(hard_stop):
                return "STOP", f"hard_stop {hard_stop} breached (price={price:.2f})", price
        except (TypeError, ValueError):
            pass

    # ── Time stop — classify WIN/DRAW/MISS by pnl at expiry ──────────────────
    time_stop_dt = _parse_date(thesis.get("time_stop"))
    if time_stop_dt and now >= time_stop_dt:
        entry = thesis.get("entry_price")
        if price is not None and entry:
            try:
                pnl = _pnl_pct(float(price), float(entry))
                if pnl >= 10.0:
                    outcome = "WIN"
                elif pnl >= -5.0:
                    outcome = "DRAW"
                else:
                    outcome = "MISS"
                return outcome, f"time_stop {thesis['time_stop']} (pnl={pnl:+.1f}%)", price
            except (TypeError, ValueError):
                pass
        return None, "awaiting valid entry/exit data", None

    return None, "", None


def _build_outcome_record(thesis: dict, outcome: str, price: float | None, now: datetime) -> dict:
    outcome_val = _OUTCOME_VAL.get(outcome, 0.0)
    prob        = float(thesis["probability"] if thesis.get("probability") is not None else 0.5)
    brier       = _brier(prob, outcome_val)

    # Attribute outcomes to the information available at entry, not at exit.
    div_flag = thesis.get("divergence_flag")

    return {
        "ts_scored":            now.isoformat(),
        "thesis_id":            thesis["thesis_id"],
        "ticker":               thesis["ticker"],
        "conviction":           thesis.get("conviction"),
        "probability_assigned": prob,
        "time_horizon":         thesis.get("time_horizon"),
        "bucket":               thesis.get("bucket"),
        "outcome":              outcome,
        "outcome_price":        price,
        "brier_score":          brier,
        "sentiment_composite":  thesis.get("sentiment_composite"),
        "divergence_flag":      div_flag,
        "smart_side_aligned":   thesis.get("smart_side_aligned"),
        "full_json":            json.dumps(thesis, default=str),
    }


def run() -> list[dict]:
    """Score all open theses. Returns list of scored outcome records."""
    now    = datetime.now(timezone.utc)
    theses = db.open_theses()
    scored: list[dict] = []

    if not theses:
        log.info("No open theses to score")
        return []

    for thesis in theses:
        try:
            outcome, reason, exit_price = _check_exits(thesis, now)
            if outcome is None:
                continue

            record = _build_outcome_record(thesis, outcome, exit_price, now)
            db.log_thesis_outcome(record)
            db.close_thesis(
                thesis_id     = thesis["thesis_id"],
                outcome       = outcome,
                outcome_price = exit_price,
                outcome_date  = now.isoformat(),
                brier_score   = record["brier_score"],
            )

            priority = "HIGH" if outcome == "STOP" else ("MEDIUM" if outcome == "MISS" else "LOW")
            _notify(
                thesis["ticker"], thesis["thesis_id"],
                (f"THESIS {outcome}: {thesis['ticker']} — {reason}  "
                 f"conviction={thesis.get('conviction')}  P(win)={thesis.get('probability')}"),
                priority,
            )

            _writeback_outcome_md(
                thesis, outcome, exit_price,
                record["brier_score"], reason, now,
            )

            scored.append(record)

            log.info(
                "Scored %s → %s  Brier=%.3f  %s",
                thesis["thesis_id"], outcome, record["brier_score"], reason,
            )

        except Exception as exc:
            log.error("Scorer error for %s: %s", thesis.get("thesis_id"), exc)

    log.info("Thesis scorer: %d exits from %d open theses", len(scored), len(theses))
    return scored


if __name__ == "__main__":
    import logging as _logging
    _logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    db.init()
    results = run()
    for r in results:
        print(f"{r['thesis_id']:35s}  {r['outcome']:6s}  Brier={r['brier_score']:.3f}")
