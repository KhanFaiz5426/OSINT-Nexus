"""Threat Intelligence collector — Query AbuseIPDB, URLhaus, and other feeds.

Checks IPs against AbuseIPDB for abuse reports and confidence scores.
Checks URLs against URLhaus for malicious URL reports.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.collectors.base import OSINTCollector
from app.core.config import get_settings
from app.models import ObservationStatus, RawResult, TargetType

logger = logging.getLogger(__name__)

ABUSEIPDB_BASE = "https://api.abuseipdb.com/api/v2"
URLHAUS_BASE = "https://urlhaus-api.abuse.ch/v1"


class ThreatIntelCollector(OSINTCollector):
    """Threat intelligence collector using AbuseIPDB and URLhaus."""

    name = "threat_intel"
    version = "1.0.0"
    supported_target_types = [TargetType.IP, TargetType.DOMAIN, TargetType.URL]
    requires_api_key = False  # AbuseIPDB needs key; URLhaus is free
    cache_ttl = 3600  # 1 hour
    rate_limit_rpm = 4  # AbuseIPDB free tier: 4 req/min

    def _is_api_key_available(self) -> bool:
        settings = get_settings()
        return bool(settings.ABUSEIPDB_API_KEY)

    async def _collect(self, target: str, target_type: TargetType) -> RawResult:
        results: dict[str, Any] = {}

        if target_type == TargetType.IP:
            abuseipdb = await self._query_abuseipdb(target)
            if abuseipdb:
                results["abuseipdb"] = abuseipdb

        # URLhaus for domains and URLs (and IPs if AbuseIPDB unavailable)
        if target_type in (TargetType.DOMAIN, TargetType.URL):
            urlhaus = await self._query_urlhaus(target, "url")
            if urlhaus:
                results["urlhaus"] = urlhaus
        elif target_type == TargetType.IP and "abuseipdb" not in results:
            urlhaus = await self._query_urlhaus(target, "host")
            if urlhaus:
                results["urlhaus"] = urlhaus

        if not results:
            return RawResult(
                collector_name=self.name,
                collector_version=self.version,
                target=target,
                target_type=target_type,
                query="threat_intel",
                status=ObservationStatus.SUCCESS,
                raw_response={"message": "No threat intelligence data found"},
                normalized_value="",
                confidence=0.3,
                metadata={"sources_checked": ["abuseipdb", "urlhaus"]},
            )

        # Calculate overall threat score
        threat_score = self._calculate_threat_score(results)

        return RawResult(
            collector_name=self.name,
            collector_version=self.version,
            target=target,
            target_type=target_type,
            query="threat_intel",
            status=ObservationStatus.SUCCESS,
            raw_response=results,
            normalized_value="",
            confidence=threat_score,
            metadata={
                "sources": list(results.keys()),
                "threat_score": threat_score,
            },
        )

    async def _query_abuseipdb(self, ip: str) -> dict[str, Any] | None:
        """Query AbuseIPDB for an IP address."""
        settings = get_settings()
        if not settings.ABUSEIPDB_API_KEY:
            return None

        url = f"{ABUSEIPDB_BASE}/check"
        headers = {
            "Accept": "application/json",
            "Key": settings.ABUSEIPDB_API_KEY,
        }
        params = {"ipAddress": ip, "maxAgeInDays": 90, "verbose": ""}

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                response = await client.get(url, headers=headers, params=params)

                if response.status_code == 429:
                    logger.warning("AbuseIPDB rate limit exceeded")
                    return None

                if response.status_code != 200:
                    return None

                data = response.json().get("data", {})

                return {
                    "ip": data.get("ipAddress", ip),
                    "abuse_confidence_score": data.get("abuseConfidenceScore", 0),
                    "total_reports": data.get("totalReports", 0),
                    "num_distinct_users": data.get("numDistinctUsers", 0),
                    "last_reported_at": data.get("lastReportedAt", ""),
                    "is_public": data.get("isPublic", True),
                    "is_whitelisted": data.get("isWhitelisted", False),
                    "isp": data.get("isp", ""),
                    "domain": data.get("domain", ""),
                    "country_code": data.get("countryCode", ""),
                    "usage_type": data.get("usageType", ""),
                }

        except Exception as exc:
            logger.debug("AbuseIPDB query failed: %s", exc)
            return None

    async def _query_urlhaus(self, target: str, search_type: str) -> dict[str, Any] | None:
        """Query URLhaus for a URL, domain, or host."""
        url = f"{URLHAUS_BASE}/url/"
        data = {"host": target, "limit": 10}

        if search_type == "url":
            data = {"url": target}

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                response = await client.post(url, data=data)

                if response.status_code != 200:
                    return None

                result = response.json()
                urls = result.get("urls", [])

                if not urls:
                    return None

                return {
                    "query": target,
                    "url_status": urls[0].get("url_status", ""),
                    "threat": urls[0].get("threat", ""),
                    "date_added": urls[0].get("date_added", ""),
                    "tags": urls[0].get("tags", []),
                    "total_urls": result.get("urls_online", 0),
                }

        except Exception as exc:
            logger.debug("URLhaus query failed: %s", exc)
            return None

    def _calculate_threat_score(self, results: dict[str, Any]) -> float:
        """Calculate overall threat confidence from available sources."""
        scores: list[float] = []

        if "abuseipdb" in results:
            score = results["abuseipdb"].get("abuse_confidence_score", 0)
            scores.append(score / 100.0)  # Normalize to 0-1

        if "urlhaus" in results:
            status = results["urlhaus"].get("url_status", "")
            if status == "online":
                scores.append(0.9)
            elif status == "offline":
                scores.append(0.5)
            else:
                scores.append(0.7)

        if not scores:
            return 0.0

        return max(scores)  # Use highest threat score from any source
