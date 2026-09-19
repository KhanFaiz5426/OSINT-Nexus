"""DNS collector — Query DNS records for domains and IPs.

Collects A, AAAA, MX, NS, TXT, SOA, CAA records using dnspython.
For IPs, performs reverse DNS (PTR) lookup.
"""

from __future__ import annotations

import ipaddress
import logging
from typing import Any

import dns.exception
import dns.name
import dns.resolver
import dns.reversename

from app.collectors.base import OSINTCollector
from app.core.config import get_settings
from app.models import ObservationStatus, RawResult, TargetType

logger = logging.getLogger(__name__)

# Record types to query for domains
DOMAIN_RECORD_TYPES = ["A", "AAAA", "MX", "NS", "TXT", "SOA", "CAA"]


class DNSCollector(OSINTCollector):
    """DNS record collector using dnspython."""

    name = "dns"
    version = "1.0.0"
    supported_target_types = [TargetType.DOMAIN, TargetType.IP, TargetType.EMAIL]
    requires_api_key = False
    cache_ttl = 86400  # 24 hours
    rate_limit_rpm = 600  # 10 req/s

    def _is_ip_address(self, target: str) -> bool:
        try:
            ipaddress.ip_address(target)
            return True
        except ValueError:
            return False

    async def _collect(self, target: str, target_type: TargetType) -> RawResult:
        settings = get_settings()
        resolver = dns.resolver.Resolver()
        resolver.lifetime = settings.DNS_TIMEOUT

        # Extract domain from email for DNS lookup
        if target_type == TargetType.EMAIL and "@" in target:
            domain = target.split("@")[-1].strip().lower()
            return await self._forward_dns(resolver, domain)

        if target_type == TargetType.IP and self._is_ip_address(target):
            return await self._reverse_dns(resolver, target)
        elif target_type == TargetType.DOMAIN:
            return await self._forward_dns(resolver, target)
        else:
            return RawResult(
                collector_name=self.name,
                collector_version=self.version,
                target=target,
                target_type=target_type,
                status=ObservationStatus.ERROR,
                error_message=f"DNS cannot handle target type: {target_type}",
            )

    async def _forward_dns(self, resolver: dns.resolver.Resolver, domain: str) -> RawResult:
        """Query DNS records for a domain."""
        records: dict[str, list[dict[str, Any]]] = {}
        errors: list[str] = []

        for rtype in DOMAIN_RECORD_TYPES:
            try:
                answers = resolver.resolve(domain, rtype)
                record_list = []
                for rdata in answers:
                    record_list.append(
                        {
                            "type": rtype,
                            "value": str(rdata),
                            "ttl": answers.rrset.ttl,
                        }
                    )
                if record_list:
                    records[rtype] = record_list
            except dns.resolver.NoAnswer:
                pass
            except dns.resolver.NXDOMAIN:
                return RawResult(
                    collector_name=self.name,
                    collector_version=self.version,
                    target=domain,
                    target_type=TargetType.DOMAIN,
                    query=", ".join(DOMAIN_RECORD_TYPES),
                    status=ObservationStatus.ERROR,
                    error_message=f"Domain {domain} does not exist (NXDOMAIN)",
                )
            except dns.exception.Timeout:
                errors.append(f"{rtype}: timeout")
            except Exception as exc:
                errors.append(f"{rtype}: {exc}")

        if not records and errors:
            return RawResult(
                collector_name=self.name,
                collector_version=self.version,
                target=domain,
                target_type=TargetType.DOMAIN,
                query=", ".join(DOMAIN_RECORD_TYPES),
                status=ObservationStatus.ERROR,
                error_message="; ".join(errors),
            )

        # Build normalized value from A records
        normalized = ""
        if "A" in records:
            normalized = records["A"][0]["value"]
        elif "AAAA" in records:
            normalized = records["AAAA"][0]["value"]

        return RawResult(
            collector_name=self.name,
            collector_version=self.version,
            target=domain,
            target_type=TargetType.DOMAIN,
            query=", ".join(DOMAIN_RECORD_TYPES),
            status=ObservationStatus.SUCCESS,
            raw_response=records,
            normalized_value=normalized,
            confidence=0.95 if records else 0.5,
            metadata={"record_types_queried": DOMAIN_RECORD_TYPES, "errors": errors},
        )

    async def _reverse_dns(self, resolver: dns.resolver.Resolver, ip: str) -> RawResult:
        """Perform reverse DNS lookup for an IP address."""
        try:
            rev_name = dns.reversename.from_address(ip)
            answers = resolver.resolve(rev_name, "PTR")
            ptr_records = [str(rdata) for rdata in answers]

            return RawResult(
                collector_name=self.name,
                collector_version=self.version,
                target=ip,
                target_type=TargetType.IP,
                query="PTR",
                status=ObservationStatus.SUCCESS,
                raw_response={"PTR": ptr_records},
                normalized_value=ptr_records[0] if ptr_records else "",
                confidence=0.9,
                metadata={"ptr_count": len(ptr_records)},
            )
        except dns.resolver.NoAnswer:
            return RawResult(
                collector_name=self.name,
                collector_version=self.version,
                target=ip,
                target_type=TargetType.IP,
                query="PTR",
                status=ObservationStatus.SUCCESS,
                raw_response={"PTR": []},
                normalized_value="",
                confidence=0.3,
                metadata={"message": "No PTR record found"},
            )
        except dns.exception.Timeout:
            return RawResult(
                collector_name=self.name,
                collector_version=self.version,
                target=ip,
                target_type=TargetType.IP,
                query="PTR",
                status=ObservationStatus.TIMEOUT,
                error_message="Reverse DNS lookup timed out",
            )
        except Exception as exc:
            return RawResult(
                collector_name=self.name,
                collector_version=self.version,
                target=ip,
                target_type=TargetType.IP,
                query="PTR",
                status=ObservationStatus.ERROR,
                error_message=str(exc),
            )
