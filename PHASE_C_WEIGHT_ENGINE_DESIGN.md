# Phase C — Source Empirical-Weight Engine — Design (for review, NOT deployed)

**Status:** 2026-07-10 — design only. Respects the Wife Approval Gate; nothing
ships until the plain-English summary (bottom) is approved. Shadow-only at first:
computes and displays empirical weights; does **not** touch any buy/sell decision
until a separate, later approval.

---

## Plain-English summary (for wife — read this first)

We have 6 "data sources" that each try to predict stock moves (insider buying,
options flow, Reddit, etc.). Right now each source has a **guess** at how much to
trust it, taken from research papers ("prior weight"). The plan was always to
replace those guesses with **scores earned from real results** ("empirical
weight") — e.g. "when OpenInsider flagged a stock, it beat the market 55% of the
time, so trust it 0.60." That scoring engine was **never built** — the dashboard
just shows a blank ("null") for every empirical weight, forever.

This document designs that missing engine. It will, once a week, look back at
what each source flagged, measure how those picks actually did vs the market, and
compute an earned trust score per source. **Crucially, for now these scores are
display-only** — they get shown on the dashboard and logged, but they do **not**
change a single buy/sell decision. Wiring them into real decisions would be a
*separate* future approval, only after we see the scores look sane for a few
weeks. This step is safe: worst case, a number on the dashboard looks off.

---

## What exists today vs. what's missing

| Piece | State |
|---|---|
| 6 calibration sources defined, with prior weights | ✅ `source_weights.yaml` §B `sources_g_a` |
| Per-source, per-bucket weight lookup | ✅ `claim_engine_weights.weight_for()` |
| Retro (historical) empirical weights for 2 sources | ✅ OpenInsider (n=276→0.60), FINRA (per-bucket) — already in YAML |
| Weekly **thesis** calibration (Brier, Kelly sizing, regime) | ✅ `calibration_report.py` — but this scores *theses*, not *sources* |
| Live shadow signals accumulating | ✅ `sentiment_signals` (options_flow ~1200/wk, apewisdom ~2250/wk, …) |
| **Per-source EMPIRICAL weight from live signals** | ❌ **MISSING — this is Phase C** |
| `weight_empirical` in dashboard | ❌ hardcoded `None` in `calibration_status_writer.py:130` |
| Phase/progress metadata | ❌ hardcoded stale literals (`60%`, April dates) in `_PHASE_META` |

**Key clarification:** `calibration_report.py` already does Brier/Kelly on
*theses*. Phase C is a **different axis** — scoring the *sources*. It reuses the
same statistical spirit (hit-rate + mean-excess → banded weight) that the retro
loaders used to set the OpenInsider/FINRA priors, but on forward/live data.

---

## The method (mirrors the pre-registered retro banding)

For each source `s` and bucket `b ∈ {core, swing, spec}` (and a `default`
aggregate):

1. **Collect signals.** Pull `sentiment_signals` rows for source `s` with a
   resolvable direction (bull/bear) and a timestamp older than the horizon.
2. **Measure outcome.** For each signal, compute **forward excess return vs SPY**
   over the source's horizon:
   - discrete-event sources (openinsider, capitol, options_flow, polymarket): **+20 trading days**
   - trend-feature sources (finra, reddit): **+5 trading days**
   (Same horizons the retro study used. Prices via the existing yfinance path.)
3. **Aggregate per (source, bucket):** `n`, `hit_rate` (share with excess in the
   signal's predicted direction), `mean_excess`.
4. **Map to weight via the locked bands** (same table that produced the retro
   priors — e.g. OpenInsider 55.4% hit / +4.52% excess → 0.60). Encode the bands
   once as a pure function `weight_from_stats(hit_rate, mean_excess, source_type)`.
   Apply the existing guardrails: **Magnitude rule** (cap trend-features at 0.40
   when mean_excess ≤ 0), **anti-information floor** (a bucket with negative
   excess and <50% hit gets its weight cut, e.g. FINRA swing → 0.20).
5. **Shrink toward the prior** by sample size (Bayesian-style):
   `w = (n·w_emp + k·w_prior) / (n + k)`, with `k≈30` pseudo-counts. New/thin
   sources stay near their prior; only well-sampled sources move.
6. **Min-N gate:** emit an empirical weight only when `n ≥ N_MIN` (proposed 40
   for default, 25 per bucket). Below that → `weight_empirical = null` (unchanged
   behavior), so dead/thin sources (reddit, capitol, finra-quiet) simply keep
   showing null and running on their prior. **No dead-source contamination.**

---

## Storage & integration

- **New table** `source_empirical_weights(source_id, bucket, n, hit_rate,
  mean_excess, weight_emp, weight_blended, computed_at)`. Written weekly.
- **`calibration_status_writer.py`:** replace the hardcoded `None` on line 130
  with a lookup into this table (falls back to `None` when below min-N). Also
  replace `_PHASE_META` literals with **computed** values (real elapsed weeks,
  real progress %, honest next-milestone) so the dashboard stops showing April.
- **`claim_engine_weights.weight_for()`:** **UNCHANGED in this phase.** It keeps
  returning the prior/retro weight. The blended empirical weight is stored and
  displayed but **not** consumed by any live decision. Wiring `weight_for()` to
  prefer `weight_blended` is a **separate future approval** ("Phase C-live"),
  gated on ≥N weeks of sane shadow output.
- **Runner:** a new `source_calibrator.py`, invoked on the existing weekly
  `CALIBRATION_INTERVAL` right after `calibration_report.run()`. Pure Python +
  yfinance, zero LLM cost.

---

## Safety / no-harm (the load-bearing part)

- **Shadow-only:** no capital path, no `effective_action`, no DCA, no Kelly
  sizing reads the new weights. Money logic is byte-for-byte unchanged.
- **Dead sources can't poison anything:** min-N gate → they emit `null` → they
  stay on prior. (Reddit/Capitol being dead is irrelevant to correctness here.)
- **Look-ahead safe:** only signals older than the horizon are scored (no peeking
  at unfinished windows).
- **Deploy discipline:** backup → `py_compile` → swap → restart → verify →
  auto-rollback, same pattern as the KLAC DCA fix. New file + 2 surgical edits to
  the status writer; `claim_engine_weights.py` untouched.

## What this does NOT do
- Does not change buy/sell/hold, targets, stops, DCA amounts, the 35% cap, or the
  >200% quarantine.
- Does not fix the dead scrapers (separate work) or the 18/30 **thesis** warming
  gate (that's the Brier/Kelly axis, independent of source weights).

---

## Proposed rollout
1. **Sandbox prototype (read-only, no prod):** build the scorer in `research/`,
   run it against the current live `sentiment_signals`, and produce a table of
   *what the empirical weights would be today* — so we review real numbers before
   committing. (No mutations; mirrors the existing research-sandbox discipline.)
2. **Review** that sample output together (wife-approval on the numbers + method).
3. **Deploy shadow-only** (`source_calibrator.py` + status-writer edits).
4. **Watch 2–4 weeks**; if the weights look sane and stable, bring a *separate*
   "go-live" proposal to wire them into `weight_for()`.

---

## Open questions for you
1. **Horizons** — keep the retro 20d/5d split, or you want different windows?
2. **Go-live appetite** — is the end goal to eventually let these weights steer
   decisions (Phase C-live), or do you want them permanently as a shadow
   scoreboard you read manually?
3. **Thesis warming gate (side issue)** — the dashboard's "warming up" flag needs
   30 graded theses (you have 18, all April backfill). Want me to also make the
   display honest about that, or leave it?
