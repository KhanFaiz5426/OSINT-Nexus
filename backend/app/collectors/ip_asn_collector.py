"""IP-to-ASN collector — Map IP addresses to ASN and hosting info.

Uses Team Cymru's HTTP API and RIPEstat for ASN mapping.
Identifies hosting provider, BGP prefix, country, and ASN.
"""

from __future__ import annotations

import logging

import httpx

from app.collectors.base import OSINTCollector
from app.core.config import get_settings
from app.models import ObservationStatus, RawResult, TargetType

logger = logging.getLogger(__name__)


def _normalize_asn(value: object) -> str:
    """Normalize an ASN to canonical ``AS<number>`` form ("" when absent/invalid)."""
    text = str(value or "").strip().upper()
    if text.startswith("AS"):
        text = text[2:]
    text = text.strip()
    return f"AS{text}" if text.isdigit() else ""


class IPToASNBCollector(OSINTCollector):
    """IP-to-ASN collector using Team Cymru and RIPEstat APIs."""

    name = "ip_to_asn"
    version = "1.0.0"
    supported_target_types = [TargetType.IP]
    requires_api_key = False
    cache_ttl = 86400  # 24 hours
    rate_limit_rpm = 60  # 1 req/s

    async def _collect(self, target: str, target_type: TargetType) -> RawResult:
        settings = get_settings()

        # Try RIPEstat API first (reliable, no auth needed)
        result = await self._query_ripestat(target, settings.HTTP_TIMEOUT)
        if result.status == ObservationStatus.SUCCESS:
            return result

        # Fallback to Team Cymru HTTP API
        result = await self._query_team_cymru(target, settings.HTTP_TIMEOUT)
        return result

    async def _query_ripestat(self, ip: str, timeout: int) -> RawResult:
        """Query RIPEstat for IP ASN data."""
        url = f"https://stat.ripe.net/data/network-info/data.json?resource={ip}"

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.get(
                    url,
                    headers={"User-Agent": "OSINT-Nexus/1.0 (research)"},
                )

                if response.status_code != 200:
                    return RawResult(
                        collector_name=self.name,
                        collector_version=self.version,
                        target=ip,
                        target_type=TargetType.IP,
                        query=f"ripestat:{ip}",
                        status=ObservationStatus.ERROR,
                        error_message=f"RIPEstat returned HTTP {response.status_code}",
                    )

                data = response.json()
                result_data = data.get("data", {})

                if not result_data:
                    return RawResult(
                        collector_name=self.name,
                        collector_version=self.version,
                        target=ip,
                        target_type=TargetType.IP,
                        query=f"ripestat:{ip}",
                        status=ObservationStatus.ERROR,
                        error_message="RIPEstat returned empty data",
                    )

                # Current network-info format: {"asns": ["15169"], "prefix": "8.8.8.0/24"}
                # (no per-record descr/country). Legacy format used data.records[].
                asns = result_data.get("asns") or []
                if asns:
                    asn = _normalize_asn(asns[0])
                    prefix = str(result_data.get("prefix", "") or "")
                    raw_response = {
                        "asn": asn,
                        "asn_description": "",
                        "organization": "",
                        "prefix": prefix,
                        "country": "",
                        "source": "ripestat",
                    }
                else:
                    records = result_data.get("records", [])
                    if not records:
                        return RawResult(
                            collector_name=self.name,
                            collector_version=self.version,
                            target=ip,
                            target_type=TargetType.IP,
                            query=f"ripestat:{ip}",
                            status=ObservationStatus.ERROR,
                            error_message="No ASN records found for IP",
                        )

                    record = records[0]
                    asn = _normalize_asn(record.get("asn", ""))
                    asn_desc = str(record.get("descr", "") or "")
                    prefix = str(record.get("prefix", "") or "")
                    country = str(record.get("country", "") or "")

                    raw_response = {
                        "asn": asn,
                        "asn_description": asn_desc,
                        "organization": asn_desc,
                        "prefix": prefix,
                        "country": country,
                        "source": "ripestat",
                    }

                return RawResult(
                    collector_name=self.name,
                    collector_version=self.version,
                    target=ip,
                    target_type=TargetType.IP,
                    query=f"ripestat:{ip}",
                    status=ObservationStatus.SUCCESS,
                    raw_response=raw_response,
                    normalized_value=asn,
                    confidence=0.95 if asn else 0.3,
                    metadata={"source": "ripestat"},
                )

        except Exception as exc:
            return RawResult(
                collector_name=self.name,
                collector_version=self.version,
                target=ip,
                target_type=TargetType.IP,
                query=f"ripestat:{ip}",
                status=ObservationStatus.ERROR,
                error_message=f"RIPEstat query failed: {exc}",
            )

    async def _query_team_cymru(self, ip: str, timeout: int) -> RawResult:
        """Query Team Cymru IP-to-ASN mapping service."""
        url = f"https://api.hackertarget.com/aslookup/?q={ip}"

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.get(
                    url,
                    headers={"User-Agent": "OSINT-Nexus/1.0 (research)"},
                )

                if response.status_code != 200:
                    return RawResult(
                        collector_name=self.name,
                        collector_version=self.version,
                        target=ip,
                        target_type=TargetType.IP,
                        query=f"hackertarget:{ip}",
                        status=ObservationStatus.ERROR,
                        error_message=f"HackerTarget returned HTTP {response.status_code}",
                    )

                text = response.text.strip()

                if "error" in text.lower():
                    return RawResult(
                        collector_name=self.name,
                        collector_version=self.version,
                        target=ip,
                        target_type=TargetType.IP,
                        query=f"hackertarget:{ip}",
                        status=ObservationStatus.ERROR,
                        error_message=f"Unexpected response: {text[:200]}",
                    )

                asn = ""
                org = ""
                prefix = ""
                country = ""

                # Current format: single CSV line
                #   "8.8.8.8","15169","8.8.8.0/24","GOOGLE, US"
                csv_parts = [p.strip().strip('"') for p in text.split('","')]
                if len(csv_parts) >= 2 and csv_parts[1].strip().isdigit():
                    asn = _normalize_asn(csv_parts[1])
                    prefix = csv_parts[2].strip() if len(csv_parts) > 2 else ""
                    org_country = csv_parts[3].strip() if len(csv_parts) > 3 else ""
                    if "," in org_country:
                        org, country = (s.strip() for s in org_country.rsplit(",", 1))
                    else:
                        org = org_country
                else:
                    # Legacy two-line "AS12345 Organization Name" format.
                    lines = text.split("\n")
                    if len(lines) < 2:
                        return RawResult(
                            collector_name=self.name,
                            collector_version=self.version,
                            target=ip,
                            target_type=TargetType.IP,
                            query=f"hackertarget:{ip}",
                            status=ObservationStatus.ERROR,
                            error_message=f"Unexpected response: {text[:200]}",
                        )
                    asn_line = lines[0].strip()
                    org = lines[1].strip() if len(lines) > 1 else ""
                    if asn_line.startswith("AS"):
                        asn = _normalize_asn(asn_line)

                raw_response = {
                    "asn": asn,
                    "asn_description": org,
                    "organization": org,
                    "prefix": prefix,
                    "country": country,
                    "source": "hackertarget",
                }

                return RawResult(
                    collector_name=self.name,
                    collector_version=self.version,
                    target=ip,
                    target_type=TargetType.IP,
                    query=f"hackertarget:{ip}",
                    status=ObservationStatus.SUCCESS,
                    raw_response=raw_response,
                    normalized_value=asn,
                    confidence=0.9 if asn else 0.3,
                    metadata={"source": "hackertarget"},
                )

        except Exception as exc:
            return RawResult(
                collector_name=self.name,
                collector_version=self.version,
                target=ip,
                target_type=TargetType.IP,
                query=f"hackertarget:{ip}",
                status=ObservationStatus.ERROR,
                error_message=f"HackerTarget query failed: {exc}",
            )
