# Alpha Director — Enhancement Ideas: Analysis, Precision, Prediction, Sentiment
**Date:** 2026-07-11 · **Status:** ideas only — nothing designed-final, nothing deployed.
**Companion to:** `ARCHITECTURE_REVIEW_2026-07-10.md` (the roadmap) and
`PHASE_C_WEIGHT_ENGINE_DESIGN.md` + `research/phase_c/` (the prototype that changes the picture).

---

## 0. The frame (what the review + prototype established)

1. The only **validated** lever is regime-aware sizing; ranking formulas have no
   demonstrated edge. (Architecture review §1.)
2. The Phase C prototype just produced the **first signal to pass the entire
   skepticism battery**: 20-day *contrarian* inversion of unusual-options-flow —
   +3.69% beta-adjusted alpha, CI [+2.48, +4.91], OOS-stable, cost-robust,
   breadth 19/28 tickers. One gate remains: it has only been observed in one
   regime window (Apr–Jul '26). (`research/phase_c/inversion_results.md`.)
   **Status update: pre-registered + shadow engine deployed 2026-07-11**
   (`source_calibrator.py` weekly, display-only, `weight_for()` untouched).
3. The measurement machine is the edge — so every idea below enters as
   **measured-shadow first** (into `sentiment_signals` → Phase C scoring), and
   nothing touches capital without CI-gated evidence + wife approval.

Every idea is tagged **[FREE]**, **[PAID-ALREADY]** (rides existing spend), or
**[PAID-IF-VALIDATED]** (spend only after a shadow-validated edge, per the
$48/mo rule in the YAML).

---

## 1. Finish what's already proven (highest leverage, mostly built)

| # | Idea | Status / why it's first |
|---|---|---|
| 1.1 | ~~Ship Phase C shadow-deploy~~ | ✅ **DONE 2026-07-11** — `source_calibrator.py` weekly, `weight_empirical` live on dashboard, display-only |
| 1.2 | ~~Flip options_flow to contrarian-20d + pre-register~~ | ✅ **DONE 2026-07-11** — `PRE-REGISTRATION-options-flow.md`; capital rule = regime-2 confirm + n≥150 fwd + cost-survive |
| 1.3 | **Regime-scaled DCA** (P2-1: `monthly_dca_eff = monthly_dca × sizing_mult`), 4-week shadow "would-have-deployed" log → approval | The single evidence-backed capital change available today |
| 1.4 | **Machine-thesis generator** (B3): regime flips, divergence-HIGH (post-fix), bear-regime insider clusters, discovery-CONFIRMED names, and now **options-flow-contrarian events** auto-write pre-registered theses. **[DEPLOYED 2026-07-11]** `research/thesis_gen/thesis_generator.py` live; seeded IBIT+MU (measurement-only). Also fixed Part B: `thesis_scorer._current_price` was stale 9-13d/missing → now yfinance-primary. | Unfreezes the 18/30 `warming_up` gate; makes calibration self-sustaining; auto-arms both surviving hypotheses for their confirmation windows |
| 1.5 | **Pick ledger** (P1-5): every DCA/AC pick logged with +5/+20/+60d excess vs SPY at next-open entry | Turns the 13-day backtest into a permanent, growing evidence base |

---

## 2. Calibration solutions (measurement upgrades)

**2.1 Score the LLM as a source. [FREE — existing spend]**
Claude already writes analyses (`claude_analyses` table) and trends themes with
`sentiment_score`/`action`/`confidence` — all display-only, never graded. Add a
structured claim to every analysis ("direction, horizon, confidence") and write
it into `sentiment_signals` as source `claude_analyst`. Phase C then computes an
empirical weight for Claude exactly like any other source. Either the LLM earns
trust with a CI, or you learn it's decoration. (Fix the `claude_analyses` schema
drift + $0 cost ledger while in there — P0-5.)

**2.2 Quality-drift monitor (health_monitor v2).**
Today `health_monitor` only checks *volume* (and can't escalate — B2). Add a
*quality* dimension from Phase C outputs: when a source's rolling hit-rate CI
falls below its prior band, auto-tag it DEGRADED on the dashboard (display-only
demotion). Sources then self-deprecate instead of silently rotting the way
options_flow's 0.50 "follow" prior did.

**2.3 Per-regime conditional weights.**
Regime is the most consistently recurring split in every study (dip-buy ±15pp,
insider bear-only, options-flow contrarian regime-dependence). Store Phase C
stats per (source × bucket × **regime**) with the same min-N gates. This is the
amendment already noted in the review — treat it as required, not optional.

**2.4 Beta-adjusted excess as the default metric.**
The inversion test proved beta-adjustment is decisive (it *strengthened* the
result; it would have *killed* a beta mirage). Make `alpha vs trailing-1y-β`
the standard outcome measure in `source_calibrator.py`, the pick ledger, and
future thesis grading — not raw excess-vs-SPY.

**2.5 Reliability diagram in the Calibration Lab.**
Once machine-theses flow, plot predicted-confidence vs realized-hit-rate per
bucket (10 dots, pure JS). The honest version of "how calibrated are we" —
pairs with the evidence-tier badges (review §D1).

**2.6 "What would change our mind" tracker.**
A small dashboard card per armed hypothesis: *options-flow contrarian — needs:
different regime window, n so far in new regime: 0; bear-insider — needs: next
bear market.* Makes the confirmation gates visible instead of tribal knowledge.

---

## 3. Social sentiment (fix the dead leg, then measure it)

**3.1 Reddit: replace RSS with the official OAuth API, or retire. [FREE]**
Reddit's Data API is free for non-commercial use at ~100 queries/min per OAuth
client with a descriptive User-Agent — a different code path from the IP-blocked
RSS scrape (which still burns ~2.2k log lines/day). One-day spike test from the
VPS: register an app, pull r/wallstreetbets+r/stocks hot via OAuth. If the
datacenter IP is still blocked → **retire reddit_rss permanently** and let
ApeWisdom carry the retail cohort (it already does, ~2,250 signals/wk). Either
outcome ends the zombie state.

**3.2 Emit LLM news/trends sentiment into `sentiment_signals`. [FREE — existing spend]**
The 5-min news scan and 2-h Haiku trends synthesis already produce per-ticker
sentiment — it just evaporates into a display tab. Write per-ticker directional
rows as source `llm_news_sentiment` (and `trends_social` for the Reddit/StockTwits
themes). Zero new infrastructure; Phase C will tell you within weeks whether
news sentiment predicts *anything* at 5d/20d. This is the cheapest possible way
to turn "social sentiment" from vibes into a measured input.

**3.3 StockTwits: keep the scrape, don't pay.**
The official API is closed to new registrations (under review); third-party
wrappers are gray-area paid services. The existing trending scrape in
`trends.py` is adequate for the retail-attention cohort.

**3.4 Google Trends attention z-score. [FREE]**
`pytrends` (unofficial, mildly flaky) → weekly search-interest z-score per
portfolio ticker as shadow source `gtrends_attention`. Literature says attention
spikes lead *volume*, not returns — perfect Phase C test case, and a useful
divergence-cohort member either way.

**3.5 Divergence redesign is the consumer (B1).**
All of the above only matters once the divergence engine can actually fire:
retail cohort (apewisdom, reddit, gtrends, trends_social) z vs smart cohort
(options_flow-*contrarian*, openinsider, congress) z, score = spread × mean
quality from `claim_engine_weights`. Note the inversion finding *changes the
cohort semantics*: raw retail-follow and raw flow-follow may both be fade
signals — the redesigned divergence should use *calibrated directions*, not
naive ones.

**3.6 Skip X/Twitter.** API basic tier ≈ $200/mo; no evidence any AD source
needs it; fails the paid-if-validated rule before it starts.

---

## 4. Third-party tools & data (by cost tier)

### [FREE]
| Tool | Use in AD | Notes |
|---|---|---|
| **FRED API** | `BAMLH0A0HYM2` (HY OAS credit spread) + `T10Y2Y` (curve slope) as regime-detector v2 inputs. (NOT used for A1: FRED needs an API key and resets datacenter-IP requests → A1 was fixed 07-11 via `^TNX` on the existing yfinance batch instead. FRED remains the future-hardening option once a key is provisioned.) | Free key, rock-solid uptime, daily granularity |
| **SEC EDGAR direct** | Runtime Form-4 ingestion (you already used bulk EDGAR TSVs in insider-5y) → replaces the OpenInsider scrape with the official source; also full-text search API | Free, no ToS risk, no scrape fragility; OpenInsider becomes a cross-check |
| **Finnhub free tier** | 60 calls/min: insider transactions + MSPR insider-sentiment, social-sentiment endpoint, analyst targets **backup** (yfinance failover), earnings calendar backup | Verify which endpoints sit behind premium on the free key before wiring |
| **Kalshi API** | Macro event odds (Fed cuts, CPI, recession) → forward-looking **regime input** (shadow beside the detector) — the useful version of what Polymarket was supposed to be | CFTC-regulated, cleaner ticker mapping than `PM:bitcoin-…` pseudo-tickers; verify current API terms |
| **Polygon.io free tier** | Reference splits/dividends endpoint (one daily call sweeps recent splits market-wide) → **closes KLAC P1 split-detection** at the data layer | Alternative: yfinance `.splits` — but that's the same fragile path that caused the bug |
| **Reddit OAuth API** | §3.1 | 100 QPM non-commercial |
| **Google Trends (pytrends)** | §3.4 | Rate-limit flaky; weekly cadence is fine |

### [PAID-ALREADY] — ride the existing Unusual Whales key
- **UW congress endpoints** (`/api/congress/recent-trades` and siblings) — the
  dead `capitol_trades_house` source had the *strongest positive live signal*
  (+3.05%/5d, 80% hit, n=35) before its upstream 503'd. UW's API includes
  congressional trading — **revive the source at $0 new spend**. Verify the
  current key's scope covers the congress group; if yes, Quiver is unnecessary.
- **Fix the recurring `UnusualWhales 'NoneType'.run` error** — with flow now the
  top signal candidate, its pipeline reliability is no longer a nice-to-have.

### [PAID-IF-VALIDATED]
| Tool | Cost | Unlock condition |
|---|---|---|
| **Quiver Quantitative** (Hobbyist) | ~$25–30/mo | Only if UW congress coverage proves insufficient after a month of side-by-side |
| **Tiingo** | ~$10/mo | Only if yfinance transients (Invalid Crumb, "possibly delisted") persist after retry/backoff hardening — as price failover |
| **Earnings-transcript APIs** (Roic free tier 5 req/min/2y, API Ninjas, EarningsCalls.dev, FMP) | $0–~$30/mo | Only if the PEAD/earnings shadow source (§5.2) shows lift and you want transcript-NLP on top |

---

## 5. Precision & prediction — smart developments

**5.1 Regime detector v2 (one source of truth, richer inputs). [FREE]**
First A2 (single source of truth). Then shadow a v2 stress score adding: HY OAS
level+slope (FRED), yield-curve slope, realized-vol-of-VIX, Kalshi recession/Fed
odds. Log v1 vs v2 classifications side-by-side; adopt v2 only if it disagrees
*usefully* (earlier RISK_OFF in drawdowns on replay). Regime is the validated
lever — sharpening it compounds through every downstream decision.

**5.2 PEAD shadow source (post-earnings-announcement drift). [FREE]**
The earnings calendar is already ingested. After each portfolio/watchlist name
reports: compute surprise direction (Finnhub/yfinance estimates), emit
`earnings_surprise` into `sentiment_signals` (+20d horizon, next-open entry).
PEAD is the most-replicated anomaly in the literature — a perfect candidate for
the Phase C harness to confirm or kill *on your universe*. Plus a display-only
"earnings in N days" risk flag on DCA picks (deploying 2 days before a print is
a knowable risk the dashboard currently hides).

**5.3 Extend the backtest spine with the archived snapshots. [FREE]**
`backtest/run_backtest.py` covers 13 days because it walks published git
history — but the pre-scrub snapshot archive exists (dollar-exposure work,
06-11). Point the harness at the archive branch (local-only, never pushed) to
triple the evaluation window, and let the pick ledger (1.5) grow it daily
forever after.

**5.4 yfinance hardening + symbol sanity. [FREE]**
Retry-with-backoff on Invalid-Crumb/delisted transients; the `$NONE`/`N/A`/
`NASDAQ:SVC` parse guard in signal writers (Phase C hygiene byproduct); Stooq or
Finnhub as quote failover. Boring, but every study and every weight now depends
on this one fragile data path.

**5.5 Corporate-actions guard. [FREE]**
Daily Polygon splits sweep (§4) cross-checked against >20% overnight
price/target divergence → auto-quarantine (the KLAC lesson generalized from
symptom-catching to cause-catching).

**5.6 Weekly Decision Digest (review §D2) — endorse as the delivery surface.**
Monday digest + discovery digest + pick-ledger performance + calibration drift +
"what would change our mind" in one artifact (and optionally through the
existing Polly audio pipeline). The measurement machine only helps if its output
arrives as one readable decision brief.

---

## 6. What NOT to do (anti-roadmap)

1. **No new ranking-formula terms.** The backtest says `_allocScore` loses to a
   plain upside sort — measure (P2-2) before tuning anything.
2. **No X/Twitter API** ($200/mo, no hypothesis it serves).
3. **No paid data before a shadow-validated edge** (the YAML's own rule).
4. **No LLM in the money path.** LLM output becomes a *scored source* (2.1),
   never a direct action input.
5. **No new signal goes live un-pre-registered.** The inversion test earned its
   credibility from the discipline, not the p-value.

---

## 7. Suggested sequencing (slots into the existing P0–P3, doesn't replace it)

```
Now (with P0 batch)     : FRED DGS10 (A1 fix done right) · UW NoneType fix ·
                          symbol guard · reddit spike-test-or-retire
P1 window (+1–3 wk)     : machine-thesis gen (1.4) · pick ledger (1.5) ·
                          llm_news_sentiment emission (3.2)
                          [Phase C shadow + contrarian pre-reg: DONE 07-11]
P2 window (+4 wk)       : regime-scaled DCA shadow → approval (1.3) ·
                          UW congress revival (source was +3.05%/5d) ·
                          divergence redesign with calibrated directions (3.5)
Opportunistic / ongoing : PEAD source (5.2) · regime v2 shadow (5.1) ·
                          Kalshi + gtrends shadow sources · snapshot-archive
                          backtest (5.3) · reliability diagram + badges
Gated on regime change  : options-flow contrarian capital decision ·
                          bear-insider hypothesis test
```

Everything above respects the Wife Approval Gate: shadow/display first, one
plain-English summary per batch, capital changes as separate approvals.
