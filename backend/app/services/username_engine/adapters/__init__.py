"""Platform Intelligence Adapters — pluggable acquisition strategies.

Adapters implement different methods for discovering username presence
on platforms that cannot be probed via simple HTTP requests.
"""

from app.services.username_engine.adapters.base import (
    AcquisitionMethod,
    AdapterResult,
    EvidenceConfidence,
    PlatformAdapter,
)
from app.services.username_engine.adapters.http_adapter import DirectHTTPAdapter
from app.services.username_engine.adapters.youtube_api_adapter import YouTubeAPIAdapter
from app.services.username_engine.adapters.search_discovery_adapter import (
    SearchDiscoveryAdapter,
)

__all__ = [
    "AcquisitionMethod",
    "AdapterResult",
    "EvidenceConfidence",
    "PlatformAdapter",
    "DirectHTTPAdapter",
    "YouTubeAPIAdapter",
    "SearchDiscoveryAdapter",
]
