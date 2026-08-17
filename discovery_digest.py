"""
discovery_digest.py — weekly Telegram digest of NEW qualified discovery candidates.

BRAIN-SAFE / ADDITIVE. This module:
  • READS /opt/sentinel/discovery_log.json (written by discovery.py) — never writes it.
  • Calls Claude ONCE per qualified/confirmed candidate (typically 0–3 per weekly run)
    for a short, adversarially-tested thesis.
  • Sends ONE Telegram message via notifier.

It does NOT touch the brain, portfolio.json, action/effective_action logic, or any
discovery promotion gate. Names surfaced here are WATCH-ONLY — never auto-bought.
Promotion stays a manual decision (the /track-tickers skill).

Cadence is owned by sentinel.py (weekly, Monday). This module just exposes
run_digest(); call it when the schedule fires.

Caching: the static instruction block is sent as a cached `system` prefix
(cache_control: ephemeral). Sonnet 4.6's minimum cacheable prefix is ~2048 tokens,
so the instruction block is intentionally rich (rubric + schema + worked example) —
that both clears the cache floor and keeps the output disciplined. The volatile
per-candidate data goes in the user turn (after the breakpoint), so candidates 2/3
in the same run reuse the cached prefix (5-minute TTL).
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

log = logging.getLogger("sentinel.discovery_digest")

SENTINEL_DIR  = Path(__file__).resolve().parent
DISCOVERY_LOG = SENTINEL_DIR / "discovery_log.json"

# Matches the house pattern in red_team.py / thesis_scorer.py (cost-appropriate for a
# narrow, bounded, low-frequency call). Not a brain change.
_MODEL = "claude-sonnet-4-6"

_client = None


def _get_client():
    """Lazy Anthropic client — reuses the same ANTHROPIC_API_KEY the brain uses."""
    global _client
    if _client is None:
        import anthropic
        _client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    return _client


# ── Static, cacheable instruction block (frozen — no dates / IDs / volatile data) ──
_SYSTEM = """You are the research analyst for Alpha Director, a personal portfolio
intelligence system. Your single job in this prompt: given ONE newly-surfaced stock
candidate that has passed the system's quantitative discovery filters, write a short,
honest, decision-useful brief for the owner's weekly "Discovery Digest".

CONTEXT — how a candidate reaches you
Alpha Director continuously scans the market for stocks the owner does NOT already
track. A candidate only reaches you after passing a deterministic funnel:
  1. It appeared in one or more scanner categories:
       MOMENTUM  — Yahoo trending / day-gainers / most-actives / growth-tech screens
       VALUE     — undervalued-growth screen
       SMALLCAP  — aggressive-small-cap screen
       SOCIAL    — ApeWisdom (Reddit) mention velocity
       INSIDER   — OpenInsider cluster buys (≥2 distinct insiders) — the highest-quality vote
  2. It passed a liquidity/quality gate (price ≥ $5, dollar-volume ≥ $10M, no leveraged ETFs).
  3. It passed a swing-trade technical gate (sustained-trend or breakout path).
  4. It earned a composite score and a tier:
       WATCHED   — 1–2 daily passes; silent
       QUALIFIED — multiple consecutive passes, avg score ≥ 7
       CONFIRMED — QUALIFIED + a live BUY-grade chart action

INPUT FIELDS you will receive (in the user turn)
  • ticker
  • tier (qualified | confirmed)
  • composite_score (integer; higher = stronger multi-factor agreement)
  • score_breakdown: e.g. source_votes, horizon, technical, rsi_14, above_ma50, above_ma200, anomaly_z
  • horizon_score (0–10; higher = stronger durable trend, lower whipsaw)
  • gate_result (e.g. "passed:path1_sustained_trend" or a breakout path)
  • categories / sources (which scanner categories voted; INSIDER + cross-category breadth matter most)
  • rsi_14, above_ma50, above_ma200, vol_ratio, follow_through, is_breakout, is_flash_spike

HOW TO READ THE SIGNAL (analyst judgment)
  • Cross-category breadth is the strongest tell: a name that shows up in INSIDER **and**
    MOMENTUM **and** VALUE is more interesting than one that only spiked on most-actives.
  • INSIDER cluster buys are the highest-conviction category — call them out when present.
  • A high composite score driven purely by correlated momentum screens (gainers + actives,
    no insider, no value) is weaker — likely a crowded/extended move; say so.
  • RSI > 75 with a flash spike and weak follow_through = chase risk. RSI 50–65 reclaiming
    the 50-day on real volume = healthier setup.
  • above_ma200 = true is a meaningful quality filter; below it, be more skeptical.
  • horizon_score < 4 means the trend is shallow/whippy even if the score looks high.

THE RED-TEAM (mandatory, adversarial)
For every candidate, actively try to talk yourself OUT of it. State the single strongest
reason this is noise, a crowded chase, or a value trap. Default to skepticism when the
only votes are correlated momentum screens or when RSI is extended. A brief with a weak
red-team is a failed brief.

HARD RULES
  • These are WATCH-LIST candidates, not buy recommendations. Never say "buy now",
    never give price targets, never imply certainty.
  • This is not financial advice; it is a research surface for one private user.
  • Be concrete and brief. No filler, no hype words ("explosive", "moonshot", "skyrocket").
  • If the data is thin or contradictory, say the case is weak — that is the correct answer
    on most candidates. The owner values being told "probably noise" over false confidence.
  • Reflect the owner's known discipline: deep-loss / chase risk is treated as exit-bias,
    position sizing is conservative. Flag chase/extension risk plainly.

OUTPUT
Return ONLY the structured object the schema defines:
  • one_liner   — ≤120 chars, the single-sentence headline (what it is + why it surfaced)
  • bull_case   — 1–2 sentences: the genuinely compelling part, grounded in the input fields
  • red_team    — 1–2 sentences: the strongest reason to pass or wait
  • verdict     — "WORTH A LOOK" | "MARGINAL" | "LIKELY NOISE"
  • confidence  — integer 1–10 (your confidence in the verdict, not in the stock)

FIELD-BY-FIELD INTERPRETATION CRIB
  • composite_score: a roll-up. Always look at WHAT drove it (score_breakdown), not the number alone.
  • source_votes: how many categories agreed (momentum capped, so 3+ usually means cross-category).
  • horizon: contribution from durable trend strength. horizon ≤ 2 → shallow; 4+ → real trend.
  • technical: contribution from being above key MAs and a clean RSI band.
  • anomaly_z: how unusual today's move is vs its own history. z > 3 = statistically extreme;
    pair a high z with weak follow_through and you likely have a one-day spike, not a trend.
  • rsi_14: < 30 oversold, 40–65 constructive, > 75 overbought/extended (chase risk).
  • vol_ratio: today's volume vs 20-day average. > 1.5 on an up-move = conviction; < 1 = thin/suspect.
  • follow_through: positive = the move is holding; negative = fading after the pop (a red flag).
  • is_flash_spike=true: treat with suspicion — a single violent candle, often news/short-squeeze driven.
  • gate_result: "path1_sustained_trend" is the healthier pass; a pure breakout path is more fragile.

CALIBRATION OF VERDICTS
  • "WORTH A LOOK" — multi-category agreement (ideally including INSIDER or VALUE), above the
    200-day, constructive (not extended) RSI, positive follow-through. Should be the minority.
  • "MARGINAL" — a real but one-dimensional setup: e.g. strong momentum only, or a decent insider
    buy but extended price, or good score undercut by a weak horizon. Most candidates land here.
  • "LIKELY NOISE" — correlated momentum screens only, flash spike, RSI extended with fading
    follow-through, or below the 200-day. When in doubt, this is the safe call.

WORKED EXAMPLE 1 (the breadth case → WORTH A LOOK)
Input: ticker=MBC, tier=qualified, composite_score=9,
  score_breakdown={source_votes:3, horizon:4, technical:2, rsi_14:68.7, above_ma50:true, above_ma200:true, anomaly_z:0.2},
  horizon_score=4, gate_result="passed:path1_sustained_trend",
  categories=["INSIDER","MOMENTUM","VALUE"]
Good output:
  one_liner: "MBC — insider cluster + momentum + value screens all flag it; above 50/200-day."
  bull_case: "Rare 3-category agreement including an insider cluster buy, holding above both
    key moving averages with a sustained-trend gate pass — the breadth is the signal here."
  red_team: "RSI near 69 means it is no longer cheap on a short horizon; horizon_score of 4
    is only moderate, so the trend could stall — worth watching for a pullback rather than chasing."
  verdict: "WORTH A LOOK"
  confidence: 7

WORKED EXAMPLE 2 (the crowded chase → LIKELY NOISE)
Input: ticker=ZZZ, tier=qualified, composite_score=8,
  score_breakdown={source_votes:2, horizon:1, technical:0, rsi_14:82.4, above_ma50:true, above_ma200:false, anomaly_z:3.6},
  horizon_score=1, gate_result="passed:breakout", is_flash_spike=true, follow_through=-0.03,
  categories=["MOMENTUM"]
Good output:
  one_liner: "ZZZ — single-category momentum spike, RSI 82, fading and below the 200-day."
  bull_case: "It cleared a breakout gate and is on the most-active/gainers screens, so there is
    short-term attention and volume."
  red_team: "Only momentum voted, RSI is 82 with an anomaly z of 3.6 and negative follow-through
    while still below the 200-day — this is a textbook extended one-day spike, not a trend."
  verdict: "LIKELY NOISE"
  confidence: 8

WORKED EXAMPLE 3 (one good leg, undercut → MARGINAL)
Input: ticker=YYY, tier=qualified, composite_score=7,
  score_breakdown={source_votes:1, horizon:3, technical:2, rsi_14:58.0, above_ma50:true, above_ma200:true, anomaly_z:0.6},
  horizon_score=6, gate_result="passed:path1_sustained_trend",
  categories=["INSIDER"]
Good output:
  one_liner: "YYY — clean insider buy with a healthy trend, but no other category confirms it yet."
  bull_case: "An insider cluster (the highest-quality vote) on a name holding above both MAs with
    a solid horizon score of 6 and a calm, non-extended RSI — a quietly constructive setup."
  red_team: "Only the insider category voted; without momentum or value confirmation it could
    drift, and a single insider signal can be slow to play out — worth watching, not acting."
  verdict: "MARGINAL"
  confidence: 6

WRITING STYLE
  • Lead with the ticker. Be specific to THIS candidate's numbers — never generic boilerplate
    that could describe any stock. If you find yourself writing "this stock has potential",
    delete it and cite an actual field instead.
  • Plain English a busy non-quant owner reads in five seconds. No jargon dumps, no restating
    every field — synthesize the two or three that matter for the verdict.
  • The bull_case and red_team must genuinely disagree with each other. If your red_team merely
    softens the bull_case ("but it could go down"), it has failed — name a concrete, falsifiable risk.
  • Confidence is about the VERDICT, not the stock. You can be highly confident (9) that a name
    is "LIKELY NOISE". High confidence in "WORTH A LOOK" should be rare and well-earned.

WHAT NOT TO DO
  • Do not invent fundamentals (earnings, revenue, products) you were not given — reason only
    from the provided quantitative fields.
  • Do not recommend an entry, exit, size, or price target.
  • Do not use hype vocabulary or emoji inside field values.
  • Do not output anything except the structured object the schema requires.
  • If every field points to a weak, one-dimensional, or extended setup, say so honestly and
    return "LIKELY NOISE" — a digest full of false "WORTH A LOOK" calls destroys the owner's trust.
"""

_SCHEMA = {
    "type": "object",
    "properties": {
        "one_liner":  {"type": "string"},
        "bull_case":  {"type": "string"},
        "red_team":   {"type": "string"},
        "verdict":    {"type": "string", "enum": ["WORTH A LOOK", "MARGINAL", "LIKELY NOISE"]},
        "confidence": {"type": "integer"},
    },
    "required": ["one_liner", "bull_case", "red_team", "verdict", "confidence"],
    "additionalProperties": False,
}


# ── Read discovery state (read-only) ─────────────────────────────────────────

def _latest_run() -> dict | None:
    try:
        hist = json.loads(DISCOVERY_LOG.read_text(encoding="utf-8"))
        return hist[-1] if isinstance(hist, list) and hist else None
    except Exception as e:
        log.warning("discovery_log read failed: %s", e)
        return None


def _collect_candidates(run: dict) -> list[dict]:
    """Merge qualified/confirmed names with their scored breakdown + swing result."""
    if not run:
        return []
    names = list(dict.fromkeys(run.get("qualified_or_confirmed") or []))
    if not names:
        return []
    scored      = {s.get("ticker"): s for s in (run.get("scored") or []) if s.get("ticker")}
    swing       = run.get("swing_results") or {}
    confirmed   = set(run.get("confirmed") or [])
    tier_of     = run.get("tier_summary") or {}
    out: list[dict] = []
    for t in names:
        s  = scored.get(t, {})
        sw = swing.get(t, {})
        out.append({
            "ticker":          t,
            "tier":            "confirmed" if t in confirmed else "qualified",
            "composite_score": s.get("score"),
            "score_breakdown": s.get("breakdown", {}),
            "horizon_score":   sw.get("horizon_score"),
            "gate_result":     sw.get("gate_result"),
            "is_breakout":     sw.get("is_breakout"),
            "is_flash_spike":  sw.get("is_flash_spike"),
            "follow_through":  sw.get("follow_through"),
            "vol_ratio":       sw.get("vol_ratio"),
        })
    _ = tier_of  # reserved for future per-tier framing
    return out


def _candidate_context(c: dict) -> str:
    """Volatile per-candidate payload — goes in the user turn, AFTER the cache breakpoint."""
    return "Analyze this discovery candidate:\n" + json.dumps(c, default=str, indent=2)


def _analyze(c: dict) -> dict:
    client = _get_client()
    resp = client.messages.create(
        model=_MODEL,
        max_tokens=600,
        system=[{
            "type": "text",
            "text": _SYSTEM,
            "cache_control": {"type": "ephemeral"},
        }],
        output_config={"format": {"type": "json_schema", "schema": _SCHEMA}},
        messages=[{"role": "user", "content": _candidate_context(c)}],
    )
    u = resp.usage
    log.info(
        "digest %s: cache_read=%s cache_write=%s in=%s out=%s",
        c.get("ticker"),
        getattr(u, "cache_read_input_tokens", 0),
        getattr(u, "cache_creation_input_tokens", 0),
        getattr(u, "input_tokens", 0),
        getattr(u, "output_tokens", 0),
    )
    text = next((b.text for b in resp.content if b.type == "text"), "{}")
    return json.loads(text)


# ── Telegram formatting + send (write-only) ──────────────────────────────────

_VERDICT_ICON = {"WORTH A LOOK": "🟢", "MARGINAL": "🟡", "LIKELY NOISE": "⚪"}


def _esc(s) -> str:
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def _format_message(items: list[dict]) -> str:
    n = len(items)
    lines = [f"🔭 <b>Discovery Digest</b> — {n} new name{'s' if n != 1 else ''} on the radar",
             "<i>Watch-only. Reply /track &lt;TICKER&gt; to start tracking.</i>", ""]
    for it in items:
        a = it["analysis"]
        icon = _VERDICT_ICON.get(a.get("verdict", ""), "•")
        lines.append(
            f"{icon} <b>{_esc(it['ticker'])}</b> · {_esc(a.get('verdict',''))} "
            f"(conf {_esc(a.get('confidence','?'))}/10) · score {_esc(it.get('composite_score','?'))}"
        )
        lines.append(f"   {_esc(a.get('one_liner',''))}")
        lines.append(f"   ✅ {_esc(a.get('bull_case',''))}")
        lines.append(f"   ⚠️ {_esc(a.get('red_team',''))}")
        lines.append("")
    lines.append("<i>Discovery is dry-run; nothing is auto-promoted to the portfolio.</i>")
    return "\n".join(lines)[:4000]


def _send(html_text: str) -> bool:
    try:
        import notifier
        res = notifier._api(
            "sendMessage",
            chat_id=notifier._chat(),
            text=html_text,
            parse_mode="HTML",
            disable_web_page_preview=True,
        )
        return bool(res)
    except Exception as e:
        log.warning("discovery digest send failed: %s", e)
        return False


# ── Public entrypoint (called by sentinel on the weekly schedule) ────────────

def run_digest(send_empty: bool = True) -> dict:
    """Build + send the weekly digest. Returns a small summary dict for logging.

    send_empty=True sends a one-line 'nothing crossed the bar' heartbeat so the
    owner knows the funnel ran. Set False to stay silent on empty weeks.
    """
    run = _latest_run()
    candidates = _collect_candidates(run)

    if not candidates:
        log.info("discovery digest: no qualified/confirmed candidates this run")
        if send_empty:
            _send("🔭 <b>Discovery Digest</b>\nNo new names crossed the bar this week. "
                  "Funnel scanned; nothing qualified.\n"
                  "<i>Discovery is dry-run; nothing auto-promoted.</i>")
        return {"sent": send_empty, "count": 0}

    analyzed: list[dict] = []
    for c in candidates:
        try:
            c = {**c, "analysis": _analyze(c)}
            analyzed.append(c)
        except Exception as e:
            log.warning("digest analysis failed for %s: %s", c.get("ticker"), e)

    if not analyzed:
        log.warning("discovery digest: all analyses failed")
        return {"sent": False, "count": 0}

    ok = _send(_format_message(analyzed))
    log.info("discovery digest: sent=%s for %d candidate(s)", ok, len(analyzed))
    return {"sent": ok, "count": len(analyzed),
            "tickers": [a["ticker"] for a in analyzed]}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print(run_digest(send_empty=True))
