# Track A — Formula Comparison Backtest

**Window:** 2026-04-21 → 2026-05-04 (13 trading days)
**Picks per snapshot:** top 5
**Forward horizons:** +3d, +5d (vs SPY excess)
**Universe:** portfolio.positions ∪ outside_opps ∪ dca_new_picks per snapshot

## Strategies tested

| Strategy | Ranking |
|---|---|
| **DCA** | sort `allocation_usd` desc, take >0 (mirrors Smart DCA top-5 logic) |
| **ActionCenter** | tier (STRONG BUY → BUY → WATCH → TRIM → EXIT), then composite `_confidence×0.6 + brain/10×0.15 + upside/100×0.25` |
| **UpsideOnly** | sort `upside_pct` desc within STRONG BUY/BUY (baseline) |

## Results

### +3d forward (n=110 picks with completed forward windows)

| Strategy | n | mean_excess | hit_rate | hit_rate 95% CI |
|---|---|---|---|---|
| ActionCenter | 40 | **-0.62%** | 47.5% | [33%, 63%] |
| DCA | 30 | **-1.23%** | 33.3% | [19%, 51%] |
| **UpsideOnly** | 40 | **-0.48%** | **55.0%** | [40%, 69%] |

### +5d forward (n=85 picks with completed forward windows)

| Strategy | n | mean_excess | hit_rate | hit_rate 95% CI |
|---|---|---|---|---|
| ActionCenter | 30 | -1.04% | 43.3% | [27%, 61%] |
| DCA | 25 | **-1.94%** | 32.0% | [17%, 52%] |
| **UpsideOnly** | 30 | **-0.44%** | **56.7%** | [39%, 73%] |

### +10d
Insufficient forward data — earliest snapshots (2026-04-21) need 11 trading days of look-forward; we only have 10 available.

## Headline findings

1. **UpsideOnly wins both horizons** on mean-excess AND hit-rate. The simplest possible strategy — "rank by analyst upside within STRONG BUY/BUY" — produces the best picks in this window.

2. **DCA underperforms both** at +3d and +5d, with the worst hit rate (32–33%) and the most negative mean excess (-1.23% / -1.94%). The multiplicative `_allocScore` formula appears to be over-engineering compared to a simple upside sort, at least at short horizons.

3. **All three strategies are net-negative vs SPY** in this window. SPY had a strong run; growth/individual names lagged. This is a market-regime artefact more than a formula problem.

4. **Confidence intervals overlap heavily.** None of the differences are statistically significant. With only ~13 independent days, we can read direction-of-effect, not significance.

## Caveats

- **Pre-2026-04-30 ActionCenter** uses fallback `_confidence=0.7` (sidecar didn't exist), so the formula collapses to "sort within tier by upside" for 8 of the 13 days — making it nearly identical to UpsideOnly during that period. The two strategies diverge meaningfully only after 2026-04-30.
- **DCA had no opinion on 2026-04-27 / 04-28** — entire portfolio had `allocation_usd=0`, dca_new_picks empty (Smart DCA rollout days, allocator transient).
- **Brain confidence is never set on portfolio positions** — confirmed structurally. The `+ brain/10 × 0.15` term in the Action Center formula is a constant 0.075 for every portfolio row, contributing zero to ranking. Only `outside_opps` carries it.
- **Survivor / pick-set bias**: the universe is current portfolio + watchlist; doesn't include tickers that were dropped from the dashboard during the window.
- **Overlapping forward windows**: 5-day forwards from consecutive snapshots are highly correlated. Wilson CIs assume independence; true CIs are wider.

## What this suggests for the actual decision

If the goal is **picking what to buy next**, this micro-window says:

- **Smart DCA's `_allocScore` is not pulling its weight** vs a plain upside rank. It may even be harming results — possibly because the multiplicative formula's RSI penalty + MA200 bonus + risk_weight push toward "comfortable" names (BAC, MSFT, AVGO) that lagged the higher-upside names (IONQ, ASML, CLSK) during this window.
- **Action Center's tier-first sort is doing real work** — it beats DCA — but its in-tier composite score doesn't beat plain upside. Probably because pre-2026-04-30 the formula degenerated to upside anyway.
- **Don't change anything based on this alone.** 13 days × 5 picks is direction-of-effect, not signal. The HIMS / HOOD deep-loss period sits inside this window, which heavily punishes any strategy that picked them.

## Recommended next steps

1. **Run again in 2 weeks** with the same script — by then we'll have +10d completed and +21d on the earliest snapshots, ~3× the data with no extra coding work.
2. **Track B (yfinance reconstruction back to 2024)** is still where statistical power lives. We can reconstruct everything except `upside_pct`, and run with upside held neutral. Estimated 8–10h of work.
3. **Don't tune the formula yet** — the most actionable observation is that DCA's complexity may not be earning its keep, but we'd want a 6-month sample before changing anything in production.

## Files

- [backtest/run_backtest.py](run_backtest.py) — driver (re-runnable)
- [backtest/picks.csv](picks.csv) — raw pick + forward return data
- [backtest/report.md](report.md) — auto-generated report
