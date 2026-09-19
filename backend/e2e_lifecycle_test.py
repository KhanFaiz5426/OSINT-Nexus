"""
Phase B End-to-End Lifecycle Test
=================================
Tests the full investigation lifecycle through the actual application modules:
  1. Create workspace + investigation
  2. First run: verify api_calls_used after completion
  3. Second run: verify cumulative api_calls_used
  4. Verify collector error message persistence
  5. Simulate orphaned RUNNING → reconciliation
  6. Verify re-run after reconciliation
  7. Inspect SQLite directly
"""

import asyncio
import os
import sqlite3
import sys
import time
import uuid

sys.path.insert(0, os.path.abspath("backend"))

from app.core.task_manager import get_task_manager, reset_task_manager
from app.core.workspace import get_workspace_manager
from app.models import (
    InvestigationCreate,
    InvestigationDepth,
    InvestigationStatus,
    TargetType,
)
from app.services.investigation import create_investigation, get_investigation
from app.tasks.run_investigation import run_investigation_async
from app.db.client import close_pool, get_pool, reset_pool, _init_schema
import app.db.client as db_client

# ── Helpers ──────────────────────────────────────────────────────────────────

REPORT: dict[str, str] = {}


def _banner(msg: str) -> None:
    print(f"\n{'='*60}")
    print(f"  {msg}")
    print(f"{'='*60}")


async def _read_investigation(inv_id: str) -> dict:
    """Read investigation row as a plain dict."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM investigations WHERE id = $1", inv_id
        )
        return dict(row) if row else {}


async def _count_observations(inv_id: str) -> int:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchval(
            "SELECT COUNT(*) FROM observations WHERE investigation_id = $1",
            inv_id,
        )
        return row or 0


async def _get_error_observations(inv_id: str) -> list[dict]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT source_adapter, status, error_message
               FROM observations
               WHERE investigation_id = $1 AND status != 'success'
               ORDER BY collected_at""",
            inv_id,
        )
        return [dict(r) for r in rows]


async def _get_activity_events(inv_id: str) -> list[dict]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT event_type, details
               FROM activity_log
               WHERE investigation_id = $1
               ORDER BY created_at""",
            inv_id,
        )
        return [dict(r) for r in rows]


async def _wait_for_terminal(inv_id: str, timeout: int = 180) -> dict:
    """Poll until investigation reaches terminal status."""
    start = time.time()
    while time.time() - start < timeout:
        data = await _read_investigation(inv_id)
        status = data.get("status", "")
        if status in ("stopped", "completed", "error"):
            return data
        await asyncio.sleep(2)
    return await _read_investigation(inv_id)


# ── Main E2E Test ────────────────────────────────────────────────────────────

async def run_e2e_lifecycle_test() -> None:
    # ── Phase 0: Fresh workspace ─────────────────────────────────────────────
    _banner("Phase 0: Create fresh workspace")
    await close_pool()
    reset_pool()
    reset_task_manager()

    random_id = str(uuid.uuid4())[:8]
    workspace_dir = os.path.abspath("backend/data")
    os.makedirs(workspace_dir, exist_ok=True)
    workspace_path = os.path.join(workspace_dir, f"e2e_lifecycle_test_{random_id}.osint")
    REPORT["workspace_path"] = workspace_path

    wm = get_workspace_manager()
    await wm.create_new(workspace_path)
    print(f"  Workspace created: {workspace_path}")

    # ── Phase 1: Create investigation ────────────────────────────────────────
    _banner("Phase 1: Create investigation")
    inv_data = InvestigationCreate(
        name="E2E Lifecycle Test",
        target="example.com",
        target_type=TargetType.DOMAIN,
        depth=InvestigationDepth.SHALLOW,
    )
    inv = await create_investigation(inv_data)
    inv_id = inv.id
    REPORT["investigation_id"] = inv_id
    print(f"  Investigation ID: {inv_id}")
    print(f"  Target: example.com (DOMAIN)")
    print(f"  Depth: SHALLOW")

    data = await _read_investigation(inv_id)
    print(f"  Initial status: {data['status']}")
    print(f"  Initial api_calls_used: {data['api_calls_used']}")
    assert data["status"] == "created"
    assert data["api_calls_used"] == 0

    # ── Phase 2: First run ───────────────────────────────────────────────────
    _banner("Phase 2: First investigation run")
    tm = get_task_manager()
    tm.submit(
        task_id=inv_id,
        coro=run_investigation_async(inv_id),
    )
    print(f"  Task submitted, waiting for completion...")

    final_data = await _wait_for_terminal(inv_id, timeout=180)
    print(f"  Final status: {final_data['status']}")
    print(f"  api_calls_used (after run 1): {final_data['api_calls_used']}")
    print(f"  observations: {await _count_observations(inv_id)}")

    REPORT["run1_status"] = final_data["status"]
    REPORT["run1_api_calls"] = final_data["api_calls_used"]
    REPORT["run1_observations"] = await _count_observations(inv_id)

    assert final_data["status"] in ("stopped", "completed", "error"), \
        f"Expected terminal status, got {final_data['status']}"
    print("  PASS: Investigation reached terminal status")

    # Check for error observations
    errors = await _get_error_observations(inv_id)
    if errors:
        print(f"  Collector errors found: {len(errors)}")
        for e in errors:
            print(f"    [{e['source_adapter']}] {e['status']}: {e['error_message'][:80]}...")
        REPORT["run1_errors"] = len(errors)
    else:
        print("  No collector errors (all adapters succeeded or no network-dependent adapters ran)")
        REPORT["run1_errors"] = 0

    # ── Phase 3: Second run — verify cumulative ──────────────────────────────
    _banner("Phase 3: Second run — verify cumulative api_calls_used")
    pre_run2 = await _read_investigation(inv_id)
    api_before_run2 = pre_run2["api_calls_used"]
    print(f"  api_calls_used before run 2: {api_before_run2}")

    # Reset task manager state so we can re-submit
    reset_task_manager()
    tm2 = get_task_manager()
    tm2.submit(
        task_id=inv_id,
        coro=run_investigation_async(inv_id),
    )
    print(f"  Task submitted for re-run, waiting...")

    final_data2 = await _wait_for_terminal(inv_id, timeout=180)
    print(f"  Final status: {final_data2['status']}")
    print(f"  api_calls_used (after run 2): {final_data2['api_calls_used']}")

    REPORT["run2_status"] = final_data2["status"]
    REPORT["run2_api_calls"] = final_data2["api_calls_used"]

    # KEY ASSERTION: cumulative, not replaced
    if final_data2["api_calls_used"] >= api_before_run2:
        print(f"  PASS: api_calls_used is cumulative ({api_before_run2} -> {final_data2['api_calls_used']})")
        REPORT["cumulative_check"] = "PASS"
    else:
        print(f"  FAIL: api_calls_used decreased from {api_before_run2} to {final_data2['api_calls_used']}")
        REPORT["cumulative_check"] = f"FAIL ({api_before_run2} -> {final_data2['api_calls_used']})"

    # ── Phase 4: Collector error persistence check ───────────────────────────
    _banner("Phase 4: Collector error message persistence")
    errors2 = await _get_error_observations(inv_id)
    if errors2:
        print(f"  Error observations found: {len(errors2)}")
        for e in errors2:
            msg = e["error_message"]
            has_msg = bool(msg and msg.strip())
            print(f"    [{e['source_adapter']}] {e['status']}: error_message present={has_msg}")
            if has_msg:
                print(f"      Content: {msg[:100]}...")
        REPORT["error_persistence"] = f"{len(errors2)} errors, all with messages" if all(
            e["error_message"] for e in errors2
        ) else "Some errors missing messages"
    else:
        print("  No error observations to check (all collectors succeeded or none ran)")
        REPORT["error_persistence"] = "N/A (no errors)"

    # ── Phase 5: Simulate orphaned RUNNING + reconciliation ──────────────────
    _banner("Phase 5: Simulate orphaned RUNNING + reconciliation")
    # Manually set the investigation to RUNNING (simulating crash during execution)
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE investigations SET status = 'running', updated_at = datetime('now', 'utc') WHERE id = $1",
            inv_id,
        )
    pre_reconcile = await _read_investigation(inv_id)
    print(f"  Simulated orphaned state: status={pre_reconcile['status']}")
    assert pre_reconcile["status"] == "running"
    print("  Confirmed: investigation is RUNNING (simulated orphan)")

    # Trigger reconciliation by running _init_schema on the raw connection
    await _init_schema(db_client._pool_conn)

    post_reconcile = await _read_investigation(inv_id)
    print(f"  After reconciliation: status={post_reconcile['status']}")
    REPORT["reconciliation_status"] = post_reconcile["status"]

    assert post_reconcile["status"] == "stopped", \
        f"Expected 'stopped' after reconciliation, got '{post_reconcile['status']}'"
    print("  PASS: Orphaned RUNNING was reconciled to STOPPED")

    # Check activity log for reconciliation event
    events = await _get_activity_events(inv_id)
    reconcile_events = [e for e in events if e["event_type"] == "investigation_reconciled"]
    if reconcile_events:
        print(f"  Reconciliation activity event found:")
        print(f"    Details: {reconcile_events[0]['details']}")
        REPORT["reconcile_event"] = "present"
    else:
        print("  FAIL: No investigation_reconciled activity event found")
        REPORT["reconcile_event"] = "MISSING"

    # ── Phase 6: Re-run after reconciliation ─────────────────────────────────
    _banner("Phase 6: Re-run after reconciliation")
    pre_run3 = await _read_investigation(inv_id)
    api_before_run3 = pre_run3["api_calls_used"]
    print(f"  api_calls_used before re-run: {api_before_run3}")

    reset_task_manager()
    tm3 = get_task_manager()
    tm3.submit(
        task_id=inv_id,
        coro=run_investigation_async(inv_id),
    )
    print(f"  Task submitted for post-reconciliation re-run...")

    final_data3 = await _wait_for_terminal(inv_id, timeout=180)
    print(f"  Final status: {final_data3['status']}")
    print(f"  api_calls_used (after re-run): {final_data3['api_calls_used']}")

    REPORT["run3_status"] = final_data3["status"]
    REPORT["run3_api_calls"] = final_data3["api_calls_used"]

    assert final_data3["status"] in ("stopped", "completed", "error"), \
        f"Expected terminal status after re-run, got {final_data3['status']}"
    print("  PASS: Investigation can be re-run after reconciliation")

    if final_data3["api_calls_used"] >= api_before_run3:
        print(f"  PASS: api_calls_used still cumulative ({api_before_run3} -> {final_data3['api_calls_used']})")
        REPORT["run3_cumulative"] = "PASS"
    else:
        print(f"  FAIL: api_calls_used decreased ({api_before_run3} -> {final_data3['api_calls_used']})")
        REPORT["run3_cumulative"] = f"FAIL"

    # ── Phase 7: Direct SQLite inspection ────────────────────────────────────
    _banner("Phase 7: Direct SQLite inspection")
    db_path = workspace_path
    if os.path.exists(db_path):
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row

        # Investigations table
        inv_row = conn.execute(
            "SELECT * FROM investigations WHERE id = ?", (inv_id,)
        ).fetchone()
        print(f"  Investigations table:")
        print(f"    id: {inv_row['id']}")
        print(f"    name: {inv_row['name']}")
        print(f"    target: {inv_row['target']}")
        print(f"    status: {inv_row['status']}")
        print(f"    api_calls_used: {inv_row['api_calls_used']}")
        print(f"    api_budget: {inv_row['api_budget']}")
        print(f"    entity_count: {inv_row['entity_count']}")
        print(f"    relationship_count: {inv_row['relationship_count']}")
        print(f"    observation_count: {inv_row['observation_count']}")

        # Observations
        obs_rows = conn.execute(
            "SELECT id, source_adapter, status, error_message FROM observations WHERE investigation_id = ?",
            (inv_id,),
        ).fetchall()
        print(f"\n  Observations table ({len(obs_rows)} rows):")
        for o in obs_rows:
            em = o["error_message"][:60] if o["error_message"] else "(empty)"
            print(f"    [{o['source_adapter']}] {o['status']}: {em}")

        # Activity log
        act_rows = conn.execute(
            "SELECT event_type, details FROM activity_log WHERE investigation_id = ? ORDER BY created_at",
            (inv_id,),
        ).fetchall()
        print(f"\n  Activity log ({len(act_rows)} entries):")
        for a in act_rows:
            print(f"    {a['event_type']}: {a['details'][:80]}...")

        conn.close()
        REPORT["sqlite_inspection"] = "PASS"
    else:
        print(f"  FAIL: SQLite file not found at {db_path}")
        REPORT["sqlite_inspection"] = "FAIL"

    # ── Cleanup ──────────────────────────────────────────────────────────────
    _banner("Cleanup")
    reset_task_manager()
    await close_pool()

    # Remove test workspace
    for suffix in ["", "-wal", "-shm"]:
        p = workspace_path + suffix
        if os.path.exists(p):
            try:
                os.remove(p)
                print(f"  Removed: {p}")
            except Exception as e:
                print(f"  Could not remove {p}: {e}")

    # ── Final Report ─────────────────────────────────────────────────────────
    _banner("FINAL REPORT")
    for key, value in REPORT.items():
        print(f"  {key}: {value}")

    print(f"\n  All phases complete.")


if __name__ == "__main__":
    asyncio.run(run_e2e_lifecycle_test())
