import asyncio
import json
import os
from pathlib import Path

from app.models import TargetType
from app.services.orchestrator import _run_username_probe_engine, InvestigationState, InvestigationDepth
from app.core.settings_store import SETTINGS_FILE, get_app_settings

async def run_ab_test():
    original_settings = None
    if SETTINGS_FILE.exists():
        original_settings = SETTINGS_FILE.read_text()
    
    state = InvestigationState(
        investigation_id="test_low",
        target="johndoe",
        target_type=TargetType.USERNAME,
        depth=InvestigationDepth.STANDARD,
        budget=2000
    )
    
    print("Running LOW LIMITS...")
    low_settings = {
        "investigation": {
            "api_budget": 500,
            "probe": {
                "max_variations": 1,
                "max_platforms": 1,
                "max_total_requests": 2,
                "timeout": 5.0
            }
        },
        "collectors": {}
    }
    SETTINGS_FILE.write_text(json.dumps(low_settings))
    # force cache reload
    import app.core.settings_store as store
    store._settings_cache = None
    
    low_results = await _run_username_probe_engine(state, "test_low")
    print(f"Low Limits found {len(low_results)} observations")
    
    print("Running HIGH LIMITS...")
    state.investigation_id = "test_high"
    high_settings = {
        "investigation": {
            "api_budget": 500,
            "probe": {
                "max_variations": 10,
                "max_platforms": 20,
                "max_total_requests": 200,
                "timeout": 15.0
            }
        },
        "collectors": {}
    }
    SETTINGS_FILE.write_text(json.dumps(high_settings))
    store._settings_cache = None
    
    high_results = await _run_username_probe_engine(state, "test_high")
    print(f"High Limits found {len(high_results)} observations")
    
    if original_settings is not None:
        SETTINGS_FILE.write_text(original_settings)
    else:
        SETTINGS_FILE.unlink(missing_ok=True)
    store._settings_cache = None

if __name__ == "__main__":
    asyncio.run(run_ab_test())
