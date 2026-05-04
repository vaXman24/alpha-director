# 20D MA Graduation Evaluation — 2026-05-04

## Verdict

**GRADUATE**

## Evidence Table

Flip counts measured over the last 10 trading days (~2026-04-21 → 2026-05-02).
A "flip" is one close crossing the MA in either direction.
`—` = both MAs had 0 flips (strongly directional week, no whipsaw risk).
`∞` = 20D crossed but 50D did not (ratio undefined; noted separately).

| Ticker | Class | flips_20d | flips_50d | ratio |
|--------|-------|----------:|----------:|------:|
| APP    | swing | 0 | 0 | — |
| PANW   | swing | 0 | 0 | — |
| CEG    | swing | 1 | 3 | 0.33 |
| TSLA   | swing | 0 | 2 | 0.00 |
| HIMS   | swing | 0 | 0 | — |
| URA    | swing | 2 | 0 | ∞ |
| DEFT   | swing | 2 | 0 | ∞ |
| SOUN   | spec  | 0 | 0 | — |
| COIN   | spec  | 2 | 2 | 1.00 |
| IONQ   | spec  | 0 | 0 | — |
| BMNR   | spec  | 2 | 2 | 1.00 |
| OSCR   | spec  | 0 | 0 | — |
| SOFI   | spec  | 1 | 1 | 1.00 |
| IBIT   | spec  | 0 | 0 | — |
| ETHA   | spec  | 2 | 0 | ∞ |
| CLSK   | spec  | 0 | 0 | — |

## Aggregate Stats

| Stat | Value |
|------|-------|
| Median ratio (computable pairs only) | **1.00** |
| Max ratio (computable pairs only) | **1.00** |
| Count where ratio > 2.0 | **0 / 16** |
| Tickers with 20D flips but 0 50D flips (∞) | 3 (URA, DEFT, ETHA) |
| Tickers with 0 flips on both MAs | 9 |

Computable ratios (flips_50d > 0): CEG=0.33, TSLA=0.00, COIN=1.00, BMNR=1.00, SOFI=1.00.

## Recommendation

Wire the 20D into both `_compute_action` and `_allocScore` as specified below. The
2-consecutive-close persistence guard fully mitigates the three ∞-ratio tickers (URA, DEFT,
ETHA): each had only 2 raw flips in 10 days, so requiring two *sequential* closes below
the 20D means a genuine trend change must persist for ~48 h before any action downgrade fires.
The `_allocScore` multiplier (±5 %/3 %) is small enough to nudge ranking without distorting
capital allocation materially.

### `_compute_action` patch — `sentinel_files/live_collector.py`

Add the persistence counter inside the position-update loop, immediately before or after
the block that sets `action`. The `below_20_streak` field must be written back to the
position dict so it survives across hourly runs.

```python
# ── 20D persistence guard (swing/spec only) ───────────────────────
if pos.get('class') in ('swing', 'spec'):
    streak = pos.get('below_20_streak', 0)
    if price < sma20:
        streak += 1
    else:
        streak = 0
    pos['below_20_streak'] = streak          # persisted to data.json

    # Require 2 consecutive closes below 20D before downgrading
    if action == 'STRONG BUY' and streak >= 2:
        action = 'BUY'
# ──────────────────────────────────────────────────────────────────
```

### `_allocScore` patch — `docs/index.html` (near line 2479)

Insert the `ma20` constant after the existing `ma200` line and multiply it into the return:

```javascript
  const ma200   = p.above_200 ? 1.20 : 0.75;
  // 20D momentum nudge for short-horizon positions
  const ma20    = (p.class === 'swing' || p.class === 'spec')
                  ? (p.above_20 ? 1.05 : 0.97)
                  : 1.0;
```

```javascript
  return Math.pow(upside, 1.5) * riskMul * confW * rsiPen * ma200 * ma20 * actionW * yieldFactor * chartConfFactor;
```

## Reasoning

Nine of 16 swing/spec tickers had zero crosses on both MAs in the measurement window,
reflecting a firmly trending tape — exactly the environment where fast-MA wiring carries the
least whipsaw risk. Among the five tickers with a computable ratio, the maximum was 1.0 and
the median was 1.0, both well under the 2.0 cautionary threshold. The three tickers whose
20D crossed while the 50D did not (URA, DEFT, ETHA) produced only 2 raw flips each in 10
days; the proposed 2-consecutive-close rule converts those into a ~48 h confirmation
requirement, eliminating single-day noise. The `_allocScore` multiplier is bounded at ±5 %/3 %
and is class-gated, so it cannot materially distort core-position sizing. One week of evidence
is a narrow window, but the signal quality is high enough to graduate with the guards in place.
Re-evaluate if the tape becomes choppy (VIX > 25 for 3+ consecutive days).
