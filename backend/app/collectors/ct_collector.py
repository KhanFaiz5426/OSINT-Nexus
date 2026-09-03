"""Certificate Transparency collector — Query crt.sh for certificate data.

Uses the crt.sh API (https://crt.sh) to discover certificates issued
for a domain. One of the most reliable subdomain discovery methods.
"""

from __future__ import annotations

import logging
from typing import Any
from urllib.parse import quote

import httpx

from app.collectors.base import OSINTCollector
from app.core.config import get_settings
from app.models import ObservationStatus, RawResult, TargetType

logger = logging.getLogger(__name__)

CRTSH_BASE_URL = "https://crt.sh"


class CTCollector(OSINTCollector):
    """Certificate Transparency collector using crt.sh API."""

    name = "certificate_transparency"
    version = "1.0.0"
    supported_target_types = [TargetType.DOMAIN]
    requires_api_key = False
    cache_ttl = 86400  # 24 hours
    rate_limit_rpm = 60  # 1 req/s — crt.sh has limited capacity

    async def _collect(self, target: str, target_type: TargetType) -> RawResult:
        settings = get_settings()
        encoded_domain = quote(target)

        url = f"{CRTSH_BASE_URL}/?q={encoded_domain}&output=json"

        try:
            async with httpx.AsyncClient(timeout=settings.CT_TIMEOUT) as client:
                response = await client.get(
                    url,
                    headers={"User-Agent": "OSINT-Nexus/1.0 (research)"},
                    follow_redirects=True,
                )

                if response.status_code == 429:
                    return RawResult(
                        collector_name=self.name,
                        collector_version=self.version,
                        target=target,
                        target_type=target_type,
                        query=f"crt.sh:{target}",
                        status=ObservationStatus.ERROR,
                        error_message="crt.sh rate limit exceeded (429)",
                    )

                if response.status_code != 200:
                    return RawResult(
                        collector_name=self.name,
                        collector_version=self.version,
                        target=target,
                        target_type=target_type,
                        query=f"crt.sh:{target}",
                        status=ObservationStatus.ERROR,
                        error_message=f"crt.sh returned HTTP {response.status_code}",
                    )

                data = response.json()

                if not isinstance(data, list):
                    return RawResult(
                        collector_name=self.name,
                        collector_version=self.version,
                        target=target,
                        target_type=target_type,
                        query=f"crt.sh:{target}",
                        status=ObservationStatus.ERROR,
                        error_message="Unexpected response format from crt.sh",
                    )

                # Process certificates
                certificates = self._process_certs(data)
                subdomains = self._extract_subdomains(data, target)

                return RawResult(
                    collector_name=self.name,
                    collector_version=self.version,
                    target=target,
                    target_type=target_type,
                    query=f"crt.sh:{target}",
                    status=ObservationStatus.SUCCESS,
                    raw_response={
                        "certificates": certificates,
                        "subdomains": sorted(subdomains),
                        "total_entries": len(data),
                    },
                    normalized_value=target,
                    confidence=0.95,
                    metadata={
                        "cert_count": len(certificates),
                        "subdomain_count": len(subdomains),
                    },
                )

        except httpx.TimeoutException:
            return RawResult(
                collector_name=self.name,
                collector_version=self.version,
                target=target,
                target_type=target_type,
                query=f"crt.sh:{target}",
                status=ObservationStatus.TIMEOUT,
                error_message=f"crt.sh request timed out after {settings.CT_TIMEOUT}s",
            )
        except Exception as exc:
            return RawResult(
                collector_name=self.name,
                collector_version=self.version,
                target=target,
                target_type=target_type,
                query=f"crt.sh:{target}",
                status=ObservationStatus.ERROR,
                error_message=f"crt.sh query failed: {exc}",
            )

    def _process_certs(self, data: list[dict]) -> list[dict[str, Any]]:
        """Process raw crt.sh entries into structured certificate data."""
        seen_certs: dict[int, dict[str, Any]] = {}

        for entry in data:
            cert_id = entry.get("id")
            if cert_id is None:
                continue

            if cert_id not in seen_certs:
                seen_certs[cert_id] = {
                    "id": cert_id,
                    "common_name": entry.get("common_name", ""),
                    "name_value": entry.get("name_value", ""),
                    "issuer_ca_id": entry.get("issuer_ca_id"),
                    "issuer_name": entry.get("issuer_name", ""),
                    "not_before": entry.get("not_before", ""),
                    "not_after": entry.get("not_after", ""),
                    "serial_number": entry.get("serial_number", ""),
                }

        return list(seen_certs.values())

    def _extract_subdomains(self, data: list[dict], domain: str) -> set[str]:
        """Extract unique subdomains from certificate entries."""
        subdomains: set[str] = set()
        domain_lower = domain.lower().strip(".")

        for entry in data:
            name_value = entry.get("name_value", "")
            if isinstance(name_value, str):
                names = [name_value]
            elif isinstance(name_value, list):
                names = name_value
            else:
                continue

            for name in names:
                name = name.strip().lower()
                if name.startswith("*."):
                    name = name[2:]
                if name.endswith(f".{domain_lower}") or name == domain_lower:
                    subdomains.add(name)

        return subdomains
