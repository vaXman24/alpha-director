"""Option A merge recalibration — dry run only, NO production code changes.

Re-applies a hypothetical merge rule to the current sidecar's chart_rec values,
comparing old vs new effective_action distribution and which tickers move tier.
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

REPO = Path(r"c:\Users\kaiha\Desktop\Repos\alpha-director")
SIDECAR = REPO / "docs" / "charts" / "analysis.json"
DATA = REPO / "docs" / "data.json"


def merge_old(brain: str, chart: str) -> tuple[str, int]:
    brain = (brain or "").upper().strip()
    chart = (chart or "").lower().strip()
    if brain == "TRIM": return ("TRIM", 80)
    if brain == "EXIT": return ("EXIT", 85)
    if brain == "STRONG BUY":
        if chart == "buy":  return ("STRONG BUY", 95)
        if chart == "hold": return ("BUY",        75)
        if chart == "wait": return ("BUY",        65)
        if chart == "skip": return ("WATCH",      45)
        return ("BUY", 70)
    if brain == "BUY":
        if chart == "buy":  return ("BUY",   90)
        if chart == "hold": return ("BUY",   70)
        if chart == "wait": return ("WATCH", 55)
        if chart == "skip": return ("WAIT",  35)
        return ("BUY", 65)
    if brain == "WAIT":
        if chart == "buy":  return ("WAIT", 50)
        if chart == "hold": return ("WAIT", 60)
        if chart == "wait": return ("WAIT", 80)
        if chart == "skip": return ("WAIT", 90)
        return ("WAIT", 70)
    if chart == "buy":  return ("BUY",   60)
    if chart == "hold": return ("WAIT",  55)
    if chart == "wait": return ("WAIT",  60)
    if chart == "skip": return ("WAIT",  70)
    return ("WAIT", 50)


def merge_new(brain: str, chart: str) -> tuple[str, int]:
    """Option A: chart='wait' no longer demotes STRONG BUY a full tier;
    only chart='skip' overrides brain conviction."""
    brain = (brain or "").upper().strip()
    chart = (chart or "").lower().strip()
    if brain == "TRIM": return ("TRIM", 80)
    if brain == "EXIT": return ("EXIT", 85)
    if brain == "STRONG BUY":
        if chart == "buy":  return ("STRONG BUY", 95)
        if chart == "hold": return ("STRONG BUY", 80)
        if chart == "wait": return ("STRONG BUY", 70)
        if chart == "skip": return ("BUY",        50)
        return ("STRONG BUY", 75)
    if brain == "BUY":
        if chart == "buy":  return ("BUY",   90)
        if chart == "hold": return ("BUY",   70)
        if chart == "wait": return ("WATCH", 55)
        if chart == "skip": return ("WAIT",  35)
        return ("BUY", 65)
    if brain == "WAIT":
        if chart == "buy":  return ("WAIT", 50)
        if chart == "hold": return ("WAIT", 60)
        if chart == "wait": return ("WAIT", 80)
        if chart == "skip": return ("WAIT", 90)
        return ("WAIT", 70)
    if chart == "buy":  return ("BUY",   60)
    if chart == "hold": return ("WAIT",  55)
    if chart == "wait": return ("WAIT",  60)
    if chart == "skip": return ("WAIT",  70)
    return ("WAIT", 50)


def main() -> None:
    side = json.loads(SIDECAR.read_text(encoding="utf-8"))
    data = json.loads(DATA.read_text(encoding="utf-8"))

    brain_lookup: dict[str, str] = {}
    for p in (data.get("portfolio", {}) or {}).get("positions", []) or []:
        brain_lookup[p["ticker"].upper()] = (p.get("action") or "").upper()
    for p in data.get("outside_opps") or []:
        brain_lookup.setdefault(p["ticker"].upper(), (p.get("action") or "").upper())
    for p in data.get("dca_new_picks") or []:
        brain_lookup.setdefault(p["ticker"].upper(), (p.get("action") or "").upper())

    rows = []
    for t, blob in side.items():
        a = blob.get("analysis") or {}
        chart_rec = a.get("chart_rec")
        brain_a = brain_lookup.get(t)
        if brain_a is None:
            continue
        old_act, old_conf = merge_old(brain_a, chart_rec)
        new_act, new_conf = merge_new(brain_a, chart_rec)
        rows.append({
            "ticker": t,
            "bucket": blob.get("bucket", ""),
            "brain": brain_a,
            "chart_rec": chart_rec or "",
            "old": old_act,
            "old_conf": old_conf,
            "new": new_act,
            "new_conf": new_conf,
            "moved": old_act != new_act,
        })

    print("=" * 78)
    print("Option A — Merge Recalibration Dry Run (current sidecar)")
    print("=" * 78)
    print(f"Tickers analyzed: {len(rows)}\n")

    old_dist = Counter(r["old"] for r in rows)
    new_dist = Counter(r["new"] for r in rows)
    print(f"{'Tier':<14} {'OLD':>6} {'NEW':>6} {'Δ':>6}")
    print("-" * 36)
    for tier in ["STRONG BUY", "BUY", "WATCH", "WAIT", "TRIM", "EXIT"]:
        o = old_dist.get(tier, 0)
        n = new_dist.get(tier, 0)
        print(f"{tier:<14} {o:>6} {n:>6} {n-o:>+6}")

    moves = [r for r in rows if r["moved"]]
    print(f"\nTickers moving tier: {len(moves)} of {len(rows)}\n")

    move_pivot: Counter = Counter()
    for r in moves:
        move_pivot[(r["old"], r["new"])] += 1
    print(f"{'OLD':<14} -> {'NEW':<14} {'count':>6}")
    print("-" * 38)
    for (o, n), c in sorted(move_pivot.items(), key=lambda x: -x[1]):
        print(f"{o:<14} -> {n:<14} {c:>6}")

    print("\n--- Tickers that NEW marks STRONG BUY (would re-enter HighConviction pool) ---")
    new_sb = [r for r in rows if r["new"] == "STRONG BUY"]
    for r in sorted(new_sb, key=lambda r: (r["bucket"], r["ticker"])):
        marker = "(was " + r["old"] + ")" if r["moved"] else "(unchanged)"
        print(f"  {r['ticker']:6s} {r['bucket']:6s} chart={r['chart_rec']:5s} conf={r['new_conf']}  {marker}")

    print("\n--- Tickers DEMOTED by NEW vs OLD (sanity check — should only be chart=skip) ---")
    demoted = [r for r in moves if _tier_idx(r["new"]) > _tier_idx(r["old"])]
    if not demoted:
        print("  (none — no ticker is downgraded by the new rules)")
    else:
        for r in demoted:
            print(f"  {r['ticker']:6s} chart={r['chart_rec']:5s} {r['old']} -> {r['new']}")


def _tier_idx(tier: str) -> int:
    order = {"STRONG BUY": 0, "BUY": 1, "WATCH": 2, "WAIT": 3, "TRIM": 4, "EXIT": 5}
    return order.get(tier, 99)


if __name__ == "__main__":
    main()
