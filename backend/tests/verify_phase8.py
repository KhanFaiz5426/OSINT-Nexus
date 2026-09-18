import asyncio
import httpx
import json
import logging
import os
import re
import sqlite3
import subprocess
import time
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

def get_ephemeral_port() -> int:
    """Find the ephemeral port from the app.log file."""
    log_file = Path(os.environ.get("APPDATA", os.path.expanduser("~"))) / "osint-nexus" / "logs" / "app.log"
    
    # Wait for the log to be written with the port
    start = time.time()
    while time.time() - start < 15:
        if log_file.exists():
            try:
                with open(log_file, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                    for line in reversed(lines):
                        m = re.search(r"Uvicorn bound to ephemeral port: (\d+)", line)
                        if m:
                            return int(m.group(1))
            except Exception:
                pass
        time.sleep(0.5)
    raise RuntimeError("Could not find ephemeral port in log.")

async def poll_investigation(client: httpx.AsyncClient, inv_id: str, timeout: int = 60) -> dict:
    start = time.time()
    while time.time() - start < timeout:
        resp = await client.get(f"/investigations/{inv_id}/status")
        resp.raise_for_status()
        data = resp.json()
        if data["status"] in ("completed", "error", "stopped"):
            return data
        await asyncio.sleep(1)
    raise TimeoutError("Investigation timed out")

async def run_collector_e2e(client: httpx.AsyncClient, ws_path: str):
    logger.info("=== Running Collector E2E ===")
    
    # Create workspace
    resp = await client.post("/workspace/new", json={"path": ws_path})
    resp.raise_for_status()
    logger.info(f"Workspace created at {ws_path}")
    
    # Create investigation
    inv_data = {"name": "Phase 8 E2E", "target": "example.com", "description": "Test E2E"}
    resp = await client.post("/investigations", json=inv_data)
    resp.raise_for_status()
    inv_id = resp.json()["id"]
    logger.info(f"Created investigation {inv_id}")
    
    # Start with DNS collector
    resp = await client.post(f"/investigations/{inv_id}/start", json={"collectors": ["dns"]})
    resp.raise_for_status()
    logger.info("Investigation started")
    
    # Poll for completion
    status = await poll_investigation(client, inv_id)
    if status["status"] != "completed":
        raise RuntimeError(f"Investigation failed with status {status['status']}")
    
    # Check SQLite directly to verify persistence
    logger.info("Verifying SQLite persistence")
    conn = sqlite3.connect(ws_path)
    try:
        c = conn.cursor()
        c.execute("SELECT count(*) FROM observations WHERE investigation_id = ?", (inv_id,))
        obs_count = c.fetchone()[0]
        c.execute("SELECT count(*) FROM entities")
        ent_count = c.fetchone()[0]
        c.execute("SELECT count(*) FROM relationships")
        rel_count = c.fetchone()[0]
        logger.info(f"DB Stats: {obs_count} observations, {ent_count} entities, {rel_count} relationships")
        if obs_count == 0 or ent_count == 0:
            raise RuntimeError("Pipeline did not persist entities/observations!")
    finally:
        conn.close()
    
    logger.info("Collector E2E Passed!\n")

async def run_migration_integrity(client: httpx.AsyncClient, ws_path: str):
    logger.info("=== Running Migration Integrity ===")
    
    # We create a new workspace
    resp = await client.post("/workspace/new", json={"path": ws_path})
    resp.raise_for_status()
    
    # Create an authentic legacy JSON fixture
    legacy_json = {
        "investigation": {
            "id": "legacy-1234",
            "name": "Legacy Import",
            "target": "example.com",
            "target_type": "domain",
            "status": "completed",
            "depth": "standard",
            "created_at": "2026-01-01T00:00:00Z"
        },
        "observations": [
            {
                "id": "obs-1",
                "collector_name": "dns",
                "data": {"ip": "1.2.3.4"},
                "created_at": "2026-01-01T00:00:00Z"
            }
        ],
        "entities": [
            {"id": "ent-1", "type": "domain", "value": "example.com", "properties": {}},
            {"id": "ent-2", "type": "ipv4", "value": "1.2.3.4", "properties": {}}
        ],
        "relationships": [
            {"source_id": "ent-1", "target_id": "ent-2", "type": "hosted_on", "confidence": 1.0, "evidence_ids": ["obs-1"]}
        ],
        "graph": {
            "nodes": [
                {"data": {"id": "domain:example.com", "type": "domain", "label": "example.com", "confidence": 1.0}},
                {"data": {"id": "ipv4:1.2.3.4", "type": "ipv4", "label": "1.2.3.4", "confidence": 1.0}}
            ],
            "edges": [
                {"data": {"id": "edge-1", "source": "domain:example.com", "target": "ipv4:1.2.3.4", "relationship_type": "hosted_on", "confidence": 1.0, "discovered_at": "2026-01-01T00:00:00Z"}}
            ]
        },
        "activity_log": []
    }
    
    resp = await client.post("/investigations/import", json={"data": legacy_json})
    if resp.status_code != 201:
        raise RuntimeError(f"Import failed: {resp.text}")
    
    new_inv_id = resp.json()["id"]
    
    # Verify in DB
    conn = sqlite3.connect(ws_path)
    try:
        c = conn.cursor()
        c.execute("SELECT value FROM entities ORDER BY value")
        ents = [row[0] for row in c.fetchall()]
        if "1.2.3.4" not in ents or "example.com" not in ents:
            raise RuntimeError(f"Missing entities in DB: {ents}")
        
        c.execute("SELECT relationship_type FROM relationships")
        rels = [row[0] for row in c.fetchall()]
        if "HOSTED_ON" not in rels:
            raise RuntimeError(f"Missing relationship in DB. Found: {rels}")
    finally:
        conn.close()
        
    logger.info("Migration Integrity Passed!\n")

async def run_crash_recovery(client: httpx.AsyncClient, ws_path: str):
    logger.info("=== Running Crash/Recovery ===")
    
    resp = await client.post("/workspace/new", json={"path": ws_path})
    resp.raise_for_status()
    
    inv_data = {"name": "Crash Test", "target": "example.com", "description": "Crash"}
    resp = await client.post("/investigations", json=inv_data)
    inv_id = resp.json()["id"]
    
    # Start task
    resp = await client.post(f"/investigations/{inv_id}/start", json={"collectors": ["dns"]})
    
    # Immediately kill the app to simulate crash while writing
    logger.info("Killing application forcefully...")
    subprocess.run(["taskkill", "/F", "/IM", "osint-nexus.exe"], capture_output=True)
    
    # Let it die
    await asyncio.sleep(2)
    
    # Verify DB integrity
    conn = sqlite3.connect(ws_path)
    try:
        c = conn.cursor()
        c.execute("PRAGMA integrity_check")
        res = c.fetchone()[0]
        if res != "ok":
            raise RuntimeError(f"Integrity check failed: {res}")
        logger.info("SQLite PRAGMA integrity_check passed")
        
        # Application level consistency (every rel must have valid source/target)
        c.execute("SELECT count(*) FROM relationships WHERE source_id NOT IN (SELECT id FROM entities) OR target_id NOT IN (SELECT id FROM entities)")
        bad_rels = c.fetchone()[0]
        if bad_rels > 0:
            raise RuntimeError("Orphaned relationships found!")
    finally:
        conn.close()
        
    logger.info("Crash/Recovery Passed (Part 1 - Verification)!\n")
    
    # Part 2: Resume operation
    # Restart app
    logger.info("Restarting application for recovery test...")
    
    log_file = Path(os.environ.get("APPDATA", os.path.expanduser("~"))) / "osint-nexus" / "logs" / "app.log"
    try:
        os.remove(log_file)
    except FileNotFoundError:
        pass
        
    exe_path = r"D:\Desktop\My_Projects\AI-Assisted OSINT Investigation and Correlation Framework\backend\dist\osint-nexus\osint-nexus.exe"
    subprocess.Popen([exe_path])
    
    port = get_ephemeral_port()
    async with httpx.AsyncClient(base_url=f"http://127.0.0.1:{port}/api/v1", timeout=10.0) as new_client:
        # Re-open workspace
        resp = await new_client.post("/workspace/open", json={"path": ws_path})
        resp.raise_for_status()
        
        # Ensure we can still query
        resp = await new_client.get(f"/investigations/{inv_id}/status")
        resp.raise_for_status()
        
        # Create a new investigation to prove it still works
        inv_data = {"name": "Crash Test 2", "target": "example.org", "description": "Crash 2"}
        resp = await new_client.post("/investigations", json=inv_data)
        resp.raise_for_status()
        
    logger.info("Crash/Recovery Passed (Part 2 - Continued Operation)!\n")

async def run_security_scan(client: httpx.AsyncClient, ws_path: str):
    logger.info("=== Running Security Scan ===")
    
    # SSRF Testing
    ssrf_targets = ["127.0.0.1", "localhost", "169.254.169.254", "0.0.0.0", "::1"]
    resp = await client.post("/workspace/new", json={"path": ws_path})
    
    for t in ssrf_targets:
        inv_data = {"name": "SSRF Test", "target": t, "description": "SSRF"}
        resp = await client.post("/investigations", json=inv_data)
        if resp.status_code == 201:
            inv_id = resp.json()["id"]
            # Try to start it
            start_resp = await client.post(f"/investigations/{inv_id}/start", json={"collectors": ["dns"]})
            if start_resp.status_code == 200:
                # Poll
                status = await poll_investigation(client, inv_id)
                if status["status"] != "error":
                    raise RuntimeError(f"SSRF target {t} was not rejected! Status: {status['status']}")
        else:
            # Blocked at creation, that's fine too.
            pass
            
    logger.info("SSRF Rejection Passed!")
    
    # Malicious .osint SQLite Testing
    # We will create fake sqlite files with malicious content
    
    # 1. Trigger testing
    malicious_ws = str(Path(ws_path).with_name("malicious.osint"))
    conn = sqlite3.connect(malicious_ws)
    try:
        c = conn.cursor()
        c.execute("CREATE TABLE metadata (schema_version INTEGER)")
        c.execute("INSERT INTO metadata VALUES (1)")
        # create a malicious trigger
        c.execute("CREATE TRIGGER pwn_trigger AFTER INSERT ON metadata BEGIN SELECT load_extension('foo.dll'); END;")
    finally:
        conn.close()
        
    resp = await client.post("/workspace/open", json={"path": malicious_ws})
    if resp.status_code == 200:
        raise RuntimeError("App successfully opened a malicious SQLite file with triggers/extensions!")
        
    logger.info("Malicious DB Rejection Passed!\n")

async def main():
    # Setup test workspace paths
    temp_dir = Path(os.environ.get("TEMP", "."))
    ws_e2e = str(temp_dir / "test_e2e.osint")
    ws_mig = str(temp_dir / "test_mig.osint")
    ws_crash = str(temp_dir / "test_crash.osint")
    ws_sec = str(temp_dir / "test_sec.osint")
    
    # Clean up previous runs
    for p in [ws_e2e, ws_mig, ws_crash, ws_sec, str(temp_dir / "malicious.osint")]:
        try:
            os.remove(p)
        except FileNotFoundError:
            pass
            
    # Clean up app.log to ensure we get the fresh port
    log_file = Path(os.environ.get("APPDATA", os.path.expanduser("~"))) / "osint-nexus" / "logs" / "app.log"
    try:
        os.remove(log_file)
    except FileNotFoundError:
        pass
        
    # Make sure app is not running
    subprocess.run(["taskkill", "/F", "/IM", "osint-nexus.exe"], capture_output=True)
    
    # Launch app
    logger.info("Launching osint-nexus.exe...")
    exe_path = r"D:\Desktop\My_Projects\AI-Assisted OSINT Investigation and Correlation Framework\backend\dist\osint-nexus\osint-nexus.exe"
    subprocess.Popen([exe_path])
    
    try:
        port = get_ephemeral_port()
        logger.info(f"Connected to app on port {port}")
        
        async with httpx.AsyncClient(base_url=f"http://127.0.0.1:{port}/api/v1", timeout=10.0) as client:
            # 1. Collector E2E
            await run_collector_e2e(client, ws_e2e)
            
            # 2. Migration Integrity
            await run_migration_integrity(client, ws_mig)
            
            # 4. Security Scan
            await run_security_scan(client, ws_sec)
            
            # 3. Crash/Recovery
            # This kills the app! Must run last.
            await run_crash_recovery(client, ws_crash)
            
    finally:
        # Cleanup process
        subprocess.run(["taskkill", "/F", "/IM", "osint-nexus.exe"], capture_output=True)

if __name__ == "__main__":
    asyncio.run(main())
