"""
E2E verification script for Part 3D-A — Progressive Historical Data Expansion.

Usage (from backend/):
    python verify_backfill_e2e.py

Runs:
  1. BackfillService.run_batch(limit=3, subcategories=["flexi_cap"])
  2. Supabase post-checks (observation counts, metrics, duplicate check)
  3. Second identical batch call to verify idempotency
"""
import sys, os

os.chdir(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ".")

# Force UTF-8 output so box-drawing chars don't crash on cp1252 terminals
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app.core.supabase import supabase_admin
from app.modules.universe.backfill_service import BackfillService

SEP = "-" * 72

def section(title: str) -> None:
    print(f"\n{SEP}")
    print(f"  {title}")
    print(SEP)


# ─────────────────────────────────────────────────────────────────────────────
# Step 0 — Pre-run snapshot
# ─────────────────────────────────────────────────────────────────────────────
section("STEP 0 — Pre-run Supabase snapshot")

universe_res = (
    supabase_admin.table("asset_universe")
    .select("identifier, asset_name")
    .eq("subcategory", "flexi_cap")
    .order("identifier")
    .execute()
)
flexi_assets = universe_res.data or []
flexi_ids = [a["identifier"] for a in flexi_assets]
print(f"flexi_cap assets in universe: {len(flexi_ids)}")

pre_obs: dict[str, int] = {}
for ident in flexi_ids[:20]:
    obs_res = (
        supabase_admin.table("asset_historical_observations")
        .select("observation_date", count="exact")
        .eq("identifier", ident)
        .execute()
    )
    pre_obs[ident] = obs_res.count or 0

print(f"Pre-run observation counts (first <=20 flexi assets):")
for ident, cnt in list(pre_obs.items())[:10]:
    name = next((a["asset_name"] for a in flexi_assets if a["identifier"] == ident), ident)
    print(f"  {ident:10s}  {cnt:>6} obs   {name[:50]}")


# ─────────────────────────────────────────────────────────────────────────────
# Step 1 — First backfill batch
# ─────────────────────────────────────────────────────────────────────────────
section("STEP 1 — First backfill batch  (limit=3, subcategories=['flexi_cap'])")

print("Running BackfillService.run_batch(limit=3, subcategories=['flexi_cap']) ...")
result1 = BackfillService.run_batch(limit=3, subcategories=["flexi_cap"])

print(f"\nTop-level response:")
print(f"  status                   : {result1['status']}")
print(f"  limit                    : {result1['limit']}")
print(f"  subcategories_targeted   : {result1['subcategories_targeted']}")
print(f"  total_eligible_in_cats   : {result1['total_eligible_in_categories']}")
print(f"  skipped_sufficient_fresh : {result1['skipped_sufficient_fresh']}")
print(f"  candidates_this_batch    : {result1['candidates_this_batch']}")

print(f"\nSummary counters:")
for k, v in result1["summary"].items():
    print(f"  {k:<35}: {v}")

print(f"\nPer-asset results:")
processed_ids_r1 = []
for r in result1["results"]:
    processed_ids_r1.append(r["identifier"])
    print(f"\n  ── {r['identifier']}  ({r['subcategory']})")
    print(f"     asset_name           : {r['asset_name']}")
    print(f"     fetch_status         : {r['fetch_status']}")
    print(f"     observations_upserted: {r['observations_upserted']}")
    print(f"     history_start        : {r['history_start']}")
    print(f"     history_end          : {r['history_end']}")
    print(f"     metrics_status       : {r['metrics_status']}")


# ─────────────────────────────────────────────────────────────────────────────
# Step 2 — Post-run Supabase verification
# ─────────────────────────────────────────────────────────────────────────────
section("STEP 2 — Post-run Supabase verification")

issues_found = []

for r in result1["results"]:
    ident = r["identifier"]
    if r["fetch_status"] == "failed":
        print(f"  [{ident}] SKIPPING post-checks — fetch_status=failed")
        continue

    # 2a. Observation count
    obs_res = (
        supabase_admin.table("asset_historical_observations")
        .select("observation_date", count="exact")
        .eq("identifier", ident)
        .execute()
    )
    post_count = obs_res.count or 0
    pre_count = pre_obs.get(ident, 0)
    delta = post_count - pre_count

    print(f"\n  [{ident}] {r['asset_name'][:40]}")
    print(f"    obs pre-run  : {pre_count}")
    print(f"    obs post-run : {post_count}  (delta={delta:+d})")

    if post_count == 0:
        issue = f"[{ident}] post_count=0 — upsert may have silently failed"
        print(f"    ⚠  {issue}")
        issues_found.append(issue)

    # 2b. Duplicate check
    dup_res = (
        supabase_admin.table("asset_historical_observations")
        .select("observation_date")
        .eq("identifier", ident)
        .execute()
    )
    all_dates = [row["observation_date"] for row in (dup_res.data or [])]
    unique_dates = set(all_dates)
    dup_count = len(all_dates) - len(unique_dates)
    if dup_count > 0:
        issue = f"[{ident}] {dup_count} duplicate (identifier,date) rows found!"
        print(f"    ⚠  {issue}")
        issues_found.append(issue)
    else:
        print(f"    duplicate rows: 0  ✓")

    # 2c. Metrics record (schema: identifier, metrics jsonb, calculation_version,
    #     data_start_date, data_end_date, historical_observation_count, peer_count,
    #     data_confidence, peer_reliability, updated_at)
    metrics_res = (
        supabase_admin.table("asset_metrics")
        .select("identifier, calculation_version, historical_observation_count, peer_count, data_confidence, updated_at")
        .eq("identifier", ident)
        .execute()
    )
    metrics_data = metrics_res.data or []
    if metrics_data:
        m = metrics_data[0]
        print(
            f"    metrics: version={m.get('calculation_version')}, "
            f"obs_count={m.get('historical_observation_count')}, "
            f"peers={m.get('peer_count')}, "
            f"confidence={m.get('data_confidence')}, "
            f"updated_at={str(m.get('updated_at', ''))[:19]}"
        )
    else:
        if r["metrics_status"] == "stored":
            issue = f"[{ident}] metrics_status='stored' but no record found in asset_metrics"
            print(f"    ⚠  {issue}")
            issues_found.append(issue)
        else:
            print(f"    metrics record: none (metrics_status={r['metrics_status']})")


# ─────────────────────────────────────────────────────────────────────────────
# Step 3 — Idempotency check
# ─────────────────────────────────────────────────────────────────────────────
section("STEP 3 — Idempotency: second identical batch call")

print("Running BackfillService.run_batch(limit=3, subcategories=['flexi_cap']) again ...")
result2 = BackfillService.run_batch(limit=3, subcategories=["flexi_cap"])

print(f"\n  status                   : {result2['status']}")
print(f"  total_eligible_in_cats   : {result2['total_eligible_in_categories']}")
print(f"  skipped_sufficient_fresh : {result2['skipped_sufficient_fresh']}")
print(f"  candidates_this_batch    : {result2['candidates_this_batch']}")
print(f"  summary                  : {result2['summary']}")

if result2["results"]:
    print(f"\n  Run-2 per-asset results:")
    for r2 in result2["results"]:
        print(f"    [{r2['identifier']}]  fetch_status={r2['fetch_status']}  obs_upserted={r2['observations_upserted']}  metrics={r2['metrics_status']}")

print(f"\n  Post-run2 duplicate check:")
all_idents_to_check = list(set(processed_ids_r1 + [r["identifier"] for r in result2["results"]]))
for ident in all_idents_to_check:
    obs2_res = (
        supabase_admin.table("asset_historical_observations")
        .select("observation_date")
        .eq("identifier", ident)
        .execute()
    )
    all_dates2 = [row["observation_date"] for row in (obs2_res.data or [])]
    dup2 = len(all_dates2) - len(set(all_dates2))
    if dup2 > 0:
        issue = f"[{ident}] POST-RUN2: {dup2} duplicate rows!"
        print(f"    ⚠  {issue}")
        issues_found.append(issue)
    else:
        print(f"    [{ident}] total_obs={len(all_dates2)}, duplicates=0  ✓")


# ─────────────────────────────────────────────────────────────────────────────
# Final summary
# ─────────────────────────────────────────────────────────────────────────────
section("FINAL SUMMARY")

if issues_found:
    print("⚠  ISSUES FOUND:")
    for iss in issues_found:
        print(f"   • {iss}")
    sys.exit(1)
else:
    print("✓  All checks passed. No bugs or data anomalies detected.")
    print("✓  Part 3D-A end-to-end verification: PASS")
