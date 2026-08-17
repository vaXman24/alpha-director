# Alpha Director — Full Architecture Review & Improvement Roadmap
**Date:** 2026-07-10 · **Status:** review + plan only, nothing deployed.
**Scope:** money path (`live_collector`, dashboard JS), calibration stack
(`divergence`, `health_monitor`, `calibration_report`, `claim_engine_weights`,
Phase C design), sources, thesis pipeline, research corpus (May study, brain
replay, insider-5y, formula backtest), publisher/ops.

---

## 0. Executive summary

The system's plumbing is in better shape than its *epistemics are being used*.
Guardrails hold (quarantine, 35% cap, deploy discipline), the research corpus is
unusually honest — but the architecture has drifted **out of alignment with its
own findings**:

> Your research says: **no ranking formula has demonstrated edge; the only
> validated lever is regime-based risk management; the skepticism machine
> itself is the edge.**
> Your code says: **most complexity lives in ranking (alloc score, tiers,
> effective_action); the validated regime lever is display-only and never
> touches a dollar; the measurement machine is stalled (frozen theses, zeroed
> divergence, unbuilt Phase C).**

The roadmap below rebalances: **fix real bugs (P0), industrialize measurement
(P1), wire the validated lever into capital behind approval gates (P2), revive
or retire sources (P3)** — plus a decision-support layer that labels every
dashboard number with its evidence tier so decisions lean on what's proven.

---

## 1. What the evidence actually says (research synthesis)

| Finding | Source | Status |
|---|---|---|
| Technical core (chart_rec) has **no predictive lift**; core dip-buy made 2022 *worse* (−27%) | Brain replay 06-11 | Robust (5y replay of exact live rules) |
| Insider clusters: April's +3.6%/5d was **day-0 drift, untradeable**; realistic entry (next-open) ≈ +0.5%/5d, coin-flip hit, gone by wk 4 | Insider-5y 06-12 (n=3,930) | Robust — **signal rejected standalone** |
| Surviving insider nuance: **bear-regime clusters +2.9%/60d** (n=340, CI +0.1…+5.8) | Insider-5y | One bear market — pre-register, re-test next bear |
| **Defensive/regime strategies cut 2022 drawdown 70–93%** vs −40% B&H | May study v2 | Structural (how they work), not luck |
| Dip-buy quality splits **±15pp by regime @60d** | Signal-quality study | Shipped as display-only Bear Warning |
| No strategy beats curated-universe B&H in bulls; best deflated-Sharpe confidence: 41% | May study v2 | Robust |
| `_allocScore` **underperformed a plain upside sort** (33% vs 55% hit @3d); its `confidence` term is a constant for portfolio rows | Formula backtest 05-04 | Directional (13 days) — don't tune yet, *measure* |

**Evidence hierarchy for capital decisions:**
1. ✅ Validated: regime-aware sizing/protection; sizing discipline (DEEP-LOSS caps).
2. 🟡 Hypothesis: bear-regime insider buys @60d; per-regime source weights.
3. ❌ No demonstrated edge: technical signals, insider clusters standalone,
   `_allocScore` vs simple ranks, analyst-upside precision.

---

## 2. Code findings (this review, verified against prod source read-only)

### A. Money-path bugs (affect real allocation NOW)

**A1 — Yield factor inverted by a dead feed (BUG, live).**
`live_collector.py:981` hardcodes `t10y_yld = 0` ("t10y is currently None") and
`market.t10y` publishes `{"t10y": None}`. With yld=0 the formula's else-branch
gives **HIGH/VERY-HIGH-risk names a 1.10× boost**. At real ~4.3% 10Y the intended
branch would give them **0.87×**. Net: a silent ~26% relative overweight of the
riskiest candidates in every DCA cycle. Fix: restore the feed (`^TNX`) or pin
`yf=1.0` until it works.

**A2 — Two regime engines disagree on one dashboard.**
`live_collector.py:786` computes crude top-level `regime` (SPY>200 & VIX<25 →
RISK-ON) while `regime_detector` (VIX+F&G+breadth, stress score, sizing_mult)
says NEUTRAL/75% in the same payload. Today: `regime: RISK-ON` vs
`regime_info: NEUTRAL`. One source of truth (the detector), crude calc as
fallback only.

**A3 — `allocation_pct` vs `allocation_usd` come from different math.**
Python writes `allocation_pct` = raw score share (NVDA 76.9→100%), while the
capped/redistributed logic governs `allocation_usd` and the dashboard's own JS
`_finalPct`. Same concept, three surfaces, two formulas. Publish the capped pct
from Python; JS displays only.

**A4 — Dead formula term.** `confidence` is never set on portfolio rows →
`conf_w` is a constant 0.65 (backtest confirmed structurally). Wire the chart
`confidence_pct` in, or drop the term.

### B. Calibration stack defects

**B1 — Divergence engine is mathematically zeroed (BUG).**
`div_score = Σ |z_a−z_b| × |q_a−q_b|` — pairs with **equal quality contribute
zero** regardless of disagreement. The two live sources (apewisdom, options_flow)
both resolve to q=0.5 → every run scores 0.0 → **DIVERGENCE_HIGH is currently
impossible** (log: 814 rows, recent all 0.0/CONSENSUS). Worse, `_load_weights()`
is a flat parser that can't read the nested `sources_g_a:` YAML — G-A sources
silently fall back to 0.5 and stray keys (`default:`, `core:`) pollute the dict.
Redesign: explicit smart-cohort vs retail-cohort z comparison, quality from
`claim_engine_weights.weight_for()`, and score = spread × *mean* quality.

**B2 — health_monitor can't escalate.** `red_days + 0  # placeholder — real
cron does +1/day` — no such cron exists → RED never becomes DEAD, the auto-drop
rule is dormant. And `vol_ratio` bounds (0.5–1.5) mislabel both quiet-but-healthy
low-freq sources (FINRA false alarm) and over-baseline ones (polymarket 32×
YELLOW). Fix: implement the daily escalation; make volume checks one-sided with
a per-source "quiet is normal" flag.

**B3 — Thesis pipeline frozen at 18/30, all April backfill.** Manual-markdown
authoring stopped; `warming_up` can never clear; Kelly/Brier engine starves.
→ **Machine-thesis generator** (see P1-3): qualifying live events auto-write
pre-registered theses (regime flips, divergence-HIGH once fixed, bear-regime
insider clusters — auto-arming the surviving hypothesis for the next bear,
discovery-CONFIRMED names). Existing scorer grades them daily. Calibration
becomes self-sustaining instead of gated on hand-written files.

**B4 — Polymarket noise.** 462 sig/wk from ONE bitcoin market with a
pseudo-ticker (`PM:what-price-will-bitcoin-hit-in…`) pollutes diversity stats
and volume ratios. Map to portfolio-relevant markets or tag/exclude from
per-ticker stats.

**B5 — Dead sources (known, 06-22 diagnosis stands):** reddit_rss IP-blocked
(and still burning ~2.2k log-spam lines/day), capitol_trades upstream 503.

### C. Ops/data hygiene
`$NONE` symbol queried; NVDA "possibly delisted"/Invalid-Crumb transients (needs
retry/backoff, symbol hygiene); recurring `UnusualWhales 'NoneType'.run`;
`claude_analyses` schema drift; cost ledger stuck at $0 despite 300 analyses;
publisher pushes unconditionally every ~7.8 min (Pages emails — fix pending
approval); `_PHASE_META` frozen at April.

### D. What's working — keep and protect
Quarantine + 35% cap (engine side) verified holding; upside↔target math clean;
deploy discipline (backup → py_compile → swap → verify → rollback);
pre-registration culture; permanent retention + log-on-change; regime detector
itself; the research sandbox pattern.

---

## 3. The roadmap

### P0 — Correctness batch (days; one wife-approval covering the batch)
| # | Item | Why |
|---|---|---|
| P0-1 | **Fix A1 yield factor** (restore ^TNX feed; `yf=1.0` fallback) | Live mis-weighting of risky names |
| P0-2 | **Regime single-source** (A2): top-level `regime` from detector | Coherent risk display everywhere |
| P0-3 | **Unify allocation_pct** (A3) to capped engine values | One number, three surfaces |
| P0-4 | **Pages push-gate** (already written up) | Stop failure emails, 4–10× fewer deploys |
| P0-5 | Hygiene: $NONE, UW NoneType, reddit spam throttle, cost ledger, schema drift | Log signal/noise + trust |
| P0-6 | Honest calibration box (real weeks, 18/30 theses, "Phase C unbuilt") | Stop dashboard lying |

### P1 — Industrialize measurement (2–3 weeks; design-level approval)
| # | Item | Notes |
|---|---|---|
| P1-1 | **Phase C source-weight engine** — as designed, plus refinements below | Shadow-only |
| P1-2 | **Divergence redesign** (B1) — cohort-based, correct weights | Re-enables the H1 use-case |
| P1-3 | **Machine-thesis generator** (B3) — auto-pre-registered theses from live events | Unfreezes Brier/Kelly; arms the bear-regime insider test |
| P1-4 | health_monitor escalation + quiet-source semantics (B2) | Kills false YELLOW/eternal RED |
| P1-5 | **Pick ledger**: every DCA/AC pick auto-tracked for +5/+20/+60d excess vs SPY (eo1 entry), rolling report | The backtest, made permanent |

**Phase C refinements (from this review — amend the design doc):**
- **Entry convention = next-day open (eo1) everywhere.** The insider-5y lesson
  is now a *methodological law*: no source gets credit for day-0 drift.
- **Per-regime conditional weights** (bull/bear/neutral splits) — your most
  consistently recurring finding.
- Weight moves only when the stat's **CI excludes zero** (not point estimates);
  survivorship % logged per source; optional beta-adjustment noted per source.
- Each source carries an **evidence tier** field (validated / shadow / prior /
  rejected) — surfaced on the dashboard.

### P2 — Wire the validated lever into capital (gated: shadow first, then wife approval)
| # | Item | Notes |
|---|---|---|
| P2-1 | **Regime-scaled DCA**: `monthly_dca_eff = monthly_dca × sizing_mult` (RISK_ON 1.0 / NEUTRAL 0.75 / RISK_OFF 0.5 / CRISIS 0.25), detector-driven | THE evidence-backed change. 4-week shadow log ("would have deployed $X") → review → live |
| P2-2 | **Ranking A/B shadow**: log plain-upside rank beside `_allocScore` every cycle into the pick ledger; revisit after ~6 months of data | Your own backtest's recommendation — measure, don't tune |
| P2-3 | Decide **Option A** (pending since 05-04): deploy the recalibration or close it | Don't leave designed-not-deployed forks open |
| P2-4 | Concentration rule: if <3 DCA candidates, allocate ≤ n×35% and hold the rest as cash (today: 1 pick still gets 35%, but display said 100%) | Anti-single-name failure mode |

### P3 — Sources (parallel, low priority)
Capitol → Quiver/House-Stock-Watcher replacement; reddit → OAuth-or-retire
decision; FINRA quiet-exemption (P1-4 covers); revisit UW integration error.

### D — Decision-support layer (what actually helps you decide)
1. **Evidence-tier badges** on every decision surface: DCA picks labeled
   "ranking: unproven (backtest: no edge over upside sort)"; regime banner
   labeled "validated (2022 stress test)". The UI stops implying false precision.
2. **Weekly Decision Digest** (unify Monday digest + discovery digest + new pick
   ledger): what changed, regime state, pick performance vs SPY with CIs,
   calibration drift, "what would change our mind" (n needed).
3. **Kelly advisory** (from calibration_report) displayed next to DCA sizing —
   display-only until the thesis engine has real n.

---

## 4. Sequencing & gates

```
Week 1   P0 batch (one approval) ──────────► deploy with rollback discipline
Week 2-3 P1-1..P1-5 build (shadow-only) ───► design doc amendments approved first
Week 4+  P2-1 shadow log running ──────────► 4 weeks of "would-have" data
         └─► wife reviews shadow evidence ─► P2-1 live or rejected
6 months P2-2 ranking verdict from pick ledger data
Next bear: machine-thesis engine auto-tests bear-regime insider hypothesis
```

Cost: all pure-Python/zero-LLM except unchanged existing flows. No new paid
sources until a shadow-validated edge justifies one (per the options-flow
$48/mo rule already in the YAML).

## 5. One-line philosophy for the whole plan

**Stop spending complexity on ranking (nothing proves it works); spend it on
regime-aware sizing (proven), measurement that can't fool you (eo1 entries,
CIs, pre-registration), and honest surfaces — the skepticism machine is the
edge, so industrialize it.**
