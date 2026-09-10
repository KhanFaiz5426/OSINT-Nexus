"""Username Intelligence Engine — first-party platform probing.

A data-driven engine that checks whether a username exists on public
platforms by probing profile URLs directly. Does not wrap Sherlock,
WhatsMyName, Holehe, or any third-party tool.

Platform definitions are stored in ``platforms.json``. Adding a new
platform is a data change, not a code change.
"""

from app.services.username_engine.platform_store import load_platforms
from app.services.username_engine.probe import UsernameProbeEngine

__all__ = ["UsernameProbeEngine", "load_platforms"]
