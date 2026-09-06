"""WHOIS/RDAP collector — Query domain registration data.

Uses python-whois for WHOIS queries. Extracts registrant info,
registrar, name servers, creation/expiry dates, and domain status.
"""

from __future__ import annotations

import logging
from typing import Any

import whois

from app.collectors.base import OSINTCollector
from app.core.config import get_settings
from app.models import ObservationStatus, RawResult, TargetType

logger = logging.getLogger(__name__)


def _extract_field(data: Any) -> str | None:
    """Extract a single value from whois output (handles lists)."""
    if data is None:
        return None
    if isinstance(data, list):
        return data[0] if data else None
    return str(data)


def _extract_list(data: Any) -> list[str]:
    """Extract a list of values from whois output."""
    if data is None:
        return []
    if isinstance(data, list):
        return [str(item) for item in data]
    return [str(data)]


class WhoisCollector(OSINTCollector):
    """WHOIS/RDAP collector using python-whois library."""

    name = "whois"
    version = "1.0.0"
    supported_target_types = [TargetType.DOMAIN, TargetType.EMAIL]
    requires_api_key = False
    cache_ttl = 86400  # 24 hours
    rate_limit_rpm = 300  # 5 req/s

    async def _collect(self, target: str, target_type: TargetType) -> RawResult:
        get_settings()

        # Extract domain from email for WHOIS lookup
        if target_type == TargetType.EMAIL and "@" in target:
            target = target.split("@")[-1].strip().lower()

        try:
            # python-whois is synchronous; run in executor to avoid blocking
            import asyncio

            w = await asyncio.get_event_loop().run_in_executor(
                None, whois.whois, target
            )

            if w is None:
                return RawResult(
                    collector_name=self.name,
                    collector_version=self.version,
                    target=target,
                    target_type=target_type,
                    query="whois",
                    status=ObservationStatus.ERROR,
                    error_message="WHOIS returned no data",
                )

            # Extract structured data
            registrar = _extract_field(w.registrar)
            registrant_name = _extract_field(w.name)
            registrant_org = _extract_field(w.org)
            registrant_email = (
                _extract_field(w.emails)
                if hasattr(w, "emails")
                else _extract_field(w.email)
            )
            creation_date = _extract_field(w.creation_date)
            expiry_date = _extract_field(w.expiration_date)
            updated_date = _extract_field(w.updated_date)
            name_servers = _extract_list(w.name_servers) if hasattr(w, "name_servers") else []
            domain_status = _extract_list(w.status) if hasattr(w, "status") else []

            # Convert dates to strings for JSON serialization
            def to_str(val: Any) -> str:
                if val is None:
                    return ""
                return str(val)

            raw_response: dict[str, Any] = {
                "registrar": registrar,
                "registrant_name": registrant_name,
                "registrant_org": registrant_org,
                "registrant_email": registrant_email,
                "creation_date": to_str(creation_date),
                "expiry_date": to_str(expiry_date),
                "updated_date": to_str(updated_date),
                "name_servers": name_servers,
                "domain_status": domain_status,
                "dnssec": getattr(w, "dnssec", None),
            }

            return RawResult(
                collector_name=self.name,
                collector_version=self.version,
                target=target,
                target_type=target_type,
                query="whois",
                status=ObservationStatus.SUCCESS,
                raw_response=raw_response,
                normalized_value=target.lower().strip("."),
                confidence=0.9,
                metadata={
                    "registrar": registrar or "",
                    "has_name_servers": bool(name_servers),
                },
            )

        except whois.WhoisError as exc:
            return RawResult(
                collector_name=self.name,
                collector_version=self.version,
                target=target,
                target_type=target_type,
                query="whois",
                status=ObservationStatus.ERROR,
                error_message=f"WHOIS error: {exc}",
            )
        except Exception as exc:
            error_str = str(exc)
            if "no match" in error_str.lower() or "not found" in error_str.lower():
                return RawResult(
                    collector_name=self.name,
                    collector_version=self.version,
                    target=target,
                    target_type=target_type,
                    query="whois",
                    status=ObservationStatus.SUCCESS,
                    raw_response={"error": "Domain not found in WHOIS database"},
                    normalized_value="",
                    confidence=0.1,
                    metadata={"message": "No WHOIS record found"},
                )
            return RawResult(
                collector_name=self.name,
                collector_version=self.version,
                target=target,
                target_type=target_type,
                query="whois",
                status=ObservationStatus.ERROR,
                error_message=f"WHOIS lookup failed: {exc}",
            )
