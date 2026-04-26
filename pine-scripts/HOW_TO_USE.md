# Alpha Director Pine Scripts — Setup Guide

## Files

| File | Type | Purpose |
|---|---|---|
| `alpha_director_signals.pine` | Overlay | Main signals: SMA 50/150/200, entry zone, stop-loss, target, verdict table |
| `multi_timeframe_trend.pine` | Panel | Trend strength across swing / medium / long-term horizons |
| `macro_regime_overlay.pine` | Overlay | VIX-based RISK-ON / CAUTION / RISK-OFF background on SPY or any ticker |

---

## How to Load in TradingView

1. Open **TradingView Desktop** (installed — search Start Menu for "TradingView")
2. Open a chart for any ticker (e.g., GOOG, AMZN, VOO)
3. Click **Pine Editor** at the bottom
4. Click **New script** → paste the contents of any `.pine` file above
5. Click **Add to chart**
6. Repeat for each indicator you want

### Recommended chart layout (requires **Plus** plan or above):
- **Top pane (overlay):** `alpha_director_signals.pine`
- **Top pane (overlay, on SPY/QQQ):** `macro_regime_overlay.pine`
- **Bottom pane (separate panel):** `multi_timeframe_trend.pine`

---

## Per-Indicator Settings

### Alpha Director Signals
| Setting | Default | Description |
|---|---|---|
| Position Class | `core` | `core` needs all 3 MAs; `swing` needs SMA50 + one other; `spec` needs SMA50 only |
| Target Upside % | `10` | Target line drawn at this % above last close |
| Show Entry Zone | on | Green shaded band from SMA50 to SMA50+5% |
| Show Stop-Loss | on | Red dashed line at SMA50 level |
| Show Target | on | Blue line at close + upside % |

### Multi-Timeframe Trend Panel
- Green bars = bullish, orange = mixed, red = bearish
- Top half = SWING score, bottom half = MEDIUM score
- Table shows LONG-TERM (weekly) score as well

### Macro Regime Overlay
- Add to SPY or QQQ chart for market-wide regime context
- VIX Neutral Threshold: 20 (below = calm, above = elevated)
- VIX Fear Threshold: 30 (above = risk-off)

---

## TradingView Plan Recommendation

| Plan | Price | Indicators | Alerts | Verdict |
|---|---|---|---|---|
| Free | $0 | 3 per chart | 1 | Too limited for full setup |
| Essential | ~$15/mo | 5 | 20 | OK for 1 ticker at a time |
| **Plus** | **~$30/mo** | **10** | **100** | **Minimum recommended** |
| **Premium** | **~$60/mo** | **25** | **400** | **Best for active swing trading** |

**Recommendation: Start with Plus.** It gives 10 indicators (enough for all 3 scripts + some extras) and 100 alerts so you can set entry-zone alerts per ticker.

If you want to run multiple tickers open at the same time in a multi-layout view, **Premium** is worth it.

---

## What Each Signal Means

| Color | Verdict | Alpha Director Action |
|---|---|---|
| Green background | Above all 3 SMAs | STRONG BUY (core) / BUY (swing/spec) |
| Orange background | Mixed MAs | WAIT — monitor for confirmation |
| Red background | Below all 3 SMAs | WAIT / avoid new entries |

The **entry zone** (green shaded area) = SMA50 to SMA50+5%, matching Alpha Director's `entry_zone` field.
The **stop-loss** (red dashed) = SMA50 level (standard stop used by Alpha Director).
