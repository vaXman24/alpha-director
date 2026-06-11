"""
Social Trends module for Alpha Director.
Sources: Reddit (r/wallstreetbets, r/stocks, r/options, r/investing, r/StockMarket),
         StockTwits trending, Yahoo Finance trending.
Uses Claude Haiku to identify macro themes and map them to actionable stock/ETF picks.
Runs every 2 hours — writes trends.json to /opt/sentinel/.
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import anthropic
import requests

log = logging.getLogger("sentinel.trends")

TRENDS_FILE = Path(__file__).parent / "trends.json"
CACHE_TTL   = 7200   # 2 hours

SUBREDDITS  = ["wallstreetbets", "stocks", "options", "investing", "StockMarket"]
_REDDIT_UA  = "AlphaDirectorBot/1.0"

# Common words / abbreviations that are NOT stock tickers
_STOPWORDS = {
    "THE","FOR","ARE","YOU","AND","CAN","BUT","NOT","ALL","ANY","NEW","NOW",
    "HAS","HOW","ITS","USE","GET","ONE","TWO","WAY","THIS","THAT","WITH",
    "FROM","THEY","WHAT","WILL","BEEN","HAVE","WHEN","WERE","SAID","EACH",
    "TIME","SOME","JUST","LIKE","INTO","THAN","OVER","ALSO","BACK","AFTER",
    "SELL","HOLD","LONG","SHORT","CALL","PUTS","WEEK","YEAR","BULL","BEAR",
    "PLAY","GAIN","LOSS","COST","RATE","GOOD","BEST","NEXT","LAST","HIGH",
    "DOWN","MOVE","NEED","MAKE","TAKE","LOOK","KNOW","WANT","COME","NEWS",
    "DATA","BANK","FUND","CASH","DEBT","RISK","USA","GDP","FED","CPI","IMO",
    "TBH","EPS","QE","EU","AI","ML","EV","AR","VR","IV","ITM","OTM","ATM",
    "DD","DCA","SEC","CEO","IPO","ETF","ATH","ATL","YTD","LOL","WSB","USD",
    "BTC","ETH","SOL","BNB","XRP","ADA","FOMO","FUD","HODL","MOON","PUMP",
    "DUMP","SHIT","FUCK","EVEN","MOST","VERY","VERY","WELL","TRUE","REAL",
    "HUGE","ONLY","OPEN","FREE","DONE","STOP","ROTH","IRA","SPX","SPY",
    "QQQ","VIX","OCC","FDIC","FOMC","YOLO","BANG","BETS","MEME","LOCK",
}

_TICKER_RE = re.compile(r"(?<!\w)\$?([A-Z]{2,5})(?!\w)")


# ── Reddit ─────────────────────────────────────────────────────────────────

def _reddit_hot(subreddit: str) -> list[dict]:
    url = f"https://www.reddit.com/r/{subreddit}/hot.json?limit=25"
    try:
        r = requests.get(url, headers={"User-Agent": _REDDIT_UA}, timeout=12)
        r.raise_for_status()
        posts = r.json()["data"]["children"]
        return [
            {
                "title":    p["data"]["title"],
                "score":    p["data"]["score"],
                "comments": p["data"]["num_comments"],
            }
            for p in posts
        ]
    except Exception as e:
        log.warning("Reddit /%s error: %s", subreddit, e)
        return []


# ── StockTwits ─────────────────────────────────────────────────────────────

def _stocktwits_trending() -> list[str]:
    try:
        r = requests.get(
            "https://api.stocktwits.com/api/2/trending/symbols.json", timeout=10
        )
        r.raise_for_status()
        return [s["symbol"] for s in r.json().get("symbols", [])[:25]]
    except Exception as e:
        log.warning("StockTwits error: %s", e)
        return []


# ── Yahoo Finance trending ─────────────────────────────────────────────────

def _yahoo_trending() -> list[str]:
    try:
        r = requests.get(
            "https://query1.finance.yahoo.com/v1/finance/trending/US?count=20",
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=10,
        )
        r.raise_for_status()
        quotes = r.json()["finance"]["result"][0]["quotes"]
        return [q["symbol"] for q in quotes if "." not in q.get("symbol", "")]
    except Exception as e:
        log.warning("Yahoo trending error: %s", e)
        return []


# ── Ticker mention counter ─────────────────────────────────────────────────

def _extract_tickers(texts: list[str]) -> list[str]:
    counts: Counter = Counter()
    for text in texts:
        for m in _TICKER_RE.finditer(text.upper()):
            t = m.group(1).lstrip("$")
            if t not in _STOPWORDS and 2 <= len(t) <= 5:
                counts[t] += 1
    return [t for t, _ in counts.most_common(25)]


# ── Gather all sources ─────────────────────────────────────────────────────

def gather_social_data() -> dict:
    log.info("Gathering social trends…")
    reddit_raw: dict[str, list[dict]] = {}
    all_titles: list[str] = []

    for sub in SUBREDDITS:
        posts = _reddit_hot(sub)
        reddit_raw[sub] = posts
        all_titles.extend(p["title"] for p in posts)
        time.sleep(0.8)

    reddit_tickers  = _extract_tickers(all_titles)
    stocktwits      = _stocktwits_trending()
    yahoo           = _yahoo_trending()

    # Compact summary for Claude — top 5 posts per sub (score-weighted)
    reddit_summary = {
        sub: sorted(posts, key=lambda p: p["score"], reverse=True)[:5]
        for sub, posts in reddit_raw.items()
    }

    return {
        "reddit_top_titles":    all_titles[:50],
        "reddit_summary":       reddit_summary,
        "reddit_top_tickers":   reddit_tickers[:20],
        "stocktwits_trending":  stocktwits[:20],
        "yahoo_trending":       yahoo[:20],
        "scraped_at":           datetime.now(timezone.utc).isoformat(),
    }


# ── Claude synthesis ───────────────────────────────────────────────────────

_SYSTEM = """You are a quantitative analyst extracting actionable investment themes from retail social media.
Your task: identify 4-7 distinct trending themes, then for each produce specific stock and ETF picks with full analysis parameters.
Be specific and realistic. Every pick must have a concrete reason tied to the theme.
Output ONLY valid JSON matching the schema. No text before or after the JSON."""

_PROMPT_TMPL = """Social media data — Reddit (r/wallstreetbets, r/stocks, r/options, r/investing, r/StockMarket), StockTwits, Yahoo Finance trending:

REDDIT HOT TITLES:
{titles}

REDDIT TOP MENTIONED TICKERS: {reddit_t}
STOCKTWITS TRENDING: {st_t}
YAHOO FINANCE TRENDING: {yf_t}

Identify 4-7 distinct investment themes. Also independently consider current macro/tech themes such as:
photonics/optical computing, AI infrastructure buildout, energy grid modernization, defense/geopolitics,
GLP-1 obesity drugs, reshoring/manufacturing, crypto/ETF approvals — include any that are genuinely relevant.

Output this exact JSON schema:
{{
  "updated": "{ts}",
  "trends": [
    {{
      "id": "snake_case_slug",
      "name": "Short Trend Name (3-5 words)",
      "emoji": "single relevant emoji",
      "description": "2-3 sentence description of the macro driver and why it is trending NOW",
      "sentiment": "bullish or bearish or neutral",
      "sentiment_score": float 0.0-1.0,
      "momentum": "rising or stable or fading",
      "sources": ["reddit", "stocktwits", "yahoo"],
      "mention_count": estimated total mentions integer,
      "stocks": [
        {{
          "ticker": "TICKER",
          "name": "Full Company Name",
          "why": "One specific sentence: why this company benefits from this exact theme",
          "action": "STRONG BUY or BUY or WATCH or AVOID",
          "confidence": integer 1-10,
          "upside_pct": realistic 12-month upside integer,
          "risk": "LOW or MEDIUM or HIGH or VERY HIGH",
          "target": realistic 12-month price target float or null
        }}
      ],
      "etfs": [
        {{
          "ticker": "TICKER",
          "name": "Full ETF Name",
          "why": "One sentence: how this ETF captures the theme",
          "action": "BUY or WATCH"
        }}
      ]
    }}
  ]
}}

Each theme: 2-4 stocks, 1-2 ETFs. Be specific with price targets."""


def _synthesize(social: dict) -> dict:
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    titles_str = "\n".join(f"- {t[:110]}" for t in social["reddit_top_titles"][:40])
    prompt = _PROMPT_TMPL.format(
        titles   = titles_str,
        reddit_t = ", ".join(social["reddit_top_tickers"][:15]),
        st_t     = ", ".join(social["stocktwits_trending"][:15]),
        yf_t     = ", ".join(social["yahoo_trending"][:15]),
        ts       = social["scraped_at"],
    )

    msg = client.messages.create(
        model      = "claude-haiku-4-5-20251001",
        max_tokens = 5000,
        system     = _SYSTEM,
        messages   = [{"role": "user", "content": prompt}],
    )

    raw = msg.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("```", 2)[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.rsplit("```", 1)[0].strip()

    try:
        data = json.loads(raw)
        log.info("Claude trends: %d themes, in=%d out=%d",
                 len(data.get("trends", [])),
                 msg.usage.input_tokens,
                 msg.usage.output_tokens)
        return data
    except json.JSONDecodeError as e:
        log.error("Trends JSON parse error: %s | raw: %s", e, raw[:400])
        return {"updated": social["scraped_at"], "trends": [], "error": str(e)}


# ── Public entry point ─────────────────────────────────────────────────────

def refresh_trends(force: bool = False) -> dict | None:
    """Refresh trends if cache is older than CACHE_TTL. Returns trends dict or None if skipped."""
    if not force and TRENDS_FILE.exists():
        try:
            cached      = json.loads(TRENDS_FILE.read_text())
            updated_str = cached.get("updated", "")
            if updated_str:
                updated_dt  = datetime.fromisoformat(updated_str.replace("Z", "+00:00"))
                age         = (datetime.now(timezone.utc) - updated_dt).total_seconds()
                if age < CACHE_TTL:
                    log.info("Trends cache fresh (%.0f min) — skip", age / 60)
                    return None
        except Exception:
            pass

    try:
        social = gather_social_data()
        data   = _synthesize(social)
        data["_sources"] = {
            "reddit_tickers":  social["reddit_top_tickers"][:10],
            "stocktwits":      social["stocktwits_trending"][:10],
            "yahoo":           social["yahoo_trending"][:10],
        }
        TRENDS_FILE.write_text(json.dumps(data, indent=2, default=str))
        log.info("trends.json written — %d themes", len(data.get("trends", [])))
        return data
    except Exception as e:
        log.error("refresh_trends failed: %s", e, exc_info=True)
        return None
