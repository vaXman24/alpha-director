# Radar Tier — Design (for review, NOT yet deployed)

**Goal:** make discovery visibly proactive — auto-surface QUALIFIED/CONFIRMED
discovered names on the dashboard, fully priced/charted/scored — **without ever
letting an auto-discovered name reach capital** (no DCA Smart Top 5, no Action
Center allocation, no monthly deployment sizing). Promotion to a real,
capital-eligible position stays a manual `/track` decision.

Status: 2026-06-10 — design only. Respects the Wife Approval Gate; nothing here
ships until the plain-English summary is approved.

---

## The core problem with "just flip dry-run off"

Today, `discovery.py` with `DISCOVERY_DRY_RUN=0` writes QUALIFIED/CONFIRMED names
into `portfolio.json` as **`class=spec`, `_discovery=true`, shares=0**
(see discovery.py header + `_reconcile`/`MAX_DAILY_CAP` logic). The `spec` section
is **capital-eligible** — it feeds DCA Smart Top 5 (`_allocScore`), the Action
Center, and monthly deployment sizing. So flipping dry-run off would let a Reddit-
trending small-cap silently enter your buy funnel. That violates "never auto-bought"
and the DEEP-LOSS discipline. We do NOT do that.

## The design: a separate, capital-excluded `radar` class

Introduce a distinct class that gets the *visibility* of a tracked name but is
*hard-excluded* from every allocation path.

### 1. New promotion target (discovery.py)
- Keep **spec auto-promotion OFF permanently** (never auto-spec).
- Add a **radar auto-promotion path**, gated by its own env flag
  `DISCOVERY_RADAR=1` (default off until approved). When on, QUALIFIED+ names are
  written to `portfolio.json` as **`class="radar"`, `_discovery=true`,
  `_radar=true`, shares=0**, reusing the existing cap (`MAX_DAILY_CAP`) and
  30-day prune logic unchanged.
- CONFIRMED names get a `_radar_confirmed=true` flag for dashboard emphasis — still
  no capital implication.

### 2. Hard exclusion from allocation (live_collector.py) — the load-bearing guardrail
Every capital path must skip `_radar`/`class=="radar"` entries:
- **DCA Smart Top 5 / `_allocScore`:** exclude `_radar` from the candidate pool.
- **Action Center / effective_action allocation_usd:** never assign allocation to `_radar`.
- **Monthly deployment sizing (`deployments.json`):** radar names are not deployable.
- Implementation: a single `_is_radar(entry)` predicate, applied at each pool-build
  site. Add a unit assertion that no `_radar` ticker ever appears with
  `allocation_usd > 0`. (Verify the exact pool-build sites in live_collector before
  coding — `_all_port_tickers`, `port_cands`, `watch_cands`, DCA picker.)

### 3. Dashboard surface (data.json + index.html)
- New top-level `radar` array in `data.json`: ticker, price, chart slug, composite
  score, tier, RSI, MA flags, the digest one-liner/verdict (reuse discovery_digest
  output), `added_at`.
- New **"🔭 Radar — watch-only"** section in index.html, visually distinct from the
  portfolio, with an explicit "not in allocation; manual /track to promote" label.
- Reuse the existing per-ticker chart pipeline (`chart_builder` / `publish_charts`)
  so radar names get the same charts as tracked names.

### 4. Promote / dismiss controls
- **Promote:** the existing `/track <TICKER>` skill converts a radar entry to a real
  `class=spec` tracked position (drops `_radar`, sets it capital-eligible). This is
  the ONLY path from radar → capital, and it's manual.
- **Dismiss:** a radar name auto-prunes after 30 days un-promoted (existing logic),
  or you reply `/dismiss <TICKER>` to drop it sooner.

### 5. Guardrails preserved
- Watch-only: radar names never sized, never bought, never in DCA/Action allocation.
- Cap: `MAX_DAILY_CAP` still bounds the radar roster (no 600-name balloon).
- DEEP-LOSS: a radar name down hard is flagged for review, never averaged/auto-anything.
- Calibration untouched: source weights / scoring logic unchanged; radar is a
  surfacing layer, not a signal change.

---

## Rollout (each step gated, reversible)
1. Ship dashboard `radar` section as **read-only from discovery_log** first (no
   portfolio.json writes at all) — zero risk, proves the surface.
2. Add the `_is_radar` exclusion predicate + assertions to live_collector.
3. Only then enable `DISCOVERY_RADAR=1` so names persist into portfolio.json as
   `class=radar`. Watch for one week.
4. Spec auto-promotion remains permanently off.

## Open items to verify before coding
- Exact allocation pool-build sites in live_collector.py (confirm every one skips `_radar`).
- Whether index.html reads a new `radar` array cleanly (dual-source: Obsidian/docs + dashboard repo — see [[project_dashboard_dual_source]] / repo-split note).
- Whether `chart_builder` keys off portfolio.json class or ticker list (so radar names get charts).

## Plain-English summary (for wife approval, when we proceed)
> Right now the "new ideas" scanner finds names but keeps them hidden in a log.
> This change puts the best ones on the dashboard in a clearly-labeled "Radar —
> watch only" shelf with a short write-up, so we can see what the system likes at a
> glance. They are never bought automatically and never enter our buy-sizing — to
> actually track one for buying, we still tap /track ourselves. Nothing about how we
> buy, size, or exit changes.
