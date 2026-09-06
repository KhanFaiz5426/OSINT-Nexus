"""Keybase collector — Query Keybase's public API for user proofs.

Uses Keybase's public API to discover linked accounts and cryptographic proofs.
No API key required for public user lookups.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.collectors.base import OSINTCollector
from app.models import ObservationStatus, RawResult, TargetType

logger = logging.getLogger(__name__)

KEYBASE_API_BASE = "https://keybase.io/_/api/1.0"


class KeybaseCollector(OSINTCollector):
    """Keybase API collector for user profiles and linked proofs."""

    name = "keybase"
    version = "1.0.0"
    supported_target_types = [TargetType.USERNAME]
    requires_api_key = False
    cache_ttl = 3600
    rate_limit_rpm = 20

    async def _collect(self, target: str, target_type: TargetType) -> RawResult:
        url = f"{KEYBASE_API_BASE}/user/lookup.json"
        params = {"username": target}

        try:
            async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
                response = await client.get(url, params=params)

                if response.status_code == 404:
                    return RawResult(
                        collector_name=self.name,
                        collector_version=self.version,
                        target=target,
                        target_type=target_type,
                        query=f"keybase:user:{target}",
                        status=ObservationStatus.SUCCESS,
                        raw_response={"username": target, "found": False},
                        normalized_value=target,
                        confidence=0.2,
                        metadata={"message": "Keybase user not found"},
                    )

                if response.status_code != 200:
                    return RawResult(
                        collector_name=self.name,
                        collector_version=self.version,
                        target=target,
                        target_type=target_type,
                        query=f"keybase:user:{target}",
                        status=ObservationStatus.ERROR,
                        error_message=f"Keybase API returned HTTP {response.status_code}",
                    )

                data = response.json()
                them = data.get("them", [])
                if not them:
                    return RawResult(
                        collector_name=self.name,
                        collector_version=self.version,
                        target=target,
                        target_type=target_type,
                        query=f"keybase:user:{target}",
                        status=ObservationStatus.SUCCESS,
                        raw_response={"username": target, "found": False},
                        normalized_value=target,
                        confidence=0.2,
                        metadata={"message": "No Keybase user data returned"},
                    )

                user = them[0]
                basics = user.get("basics", {})
                profile = user.get("profile", {})
                proofs = user.get("proofs", {}).get("summarized", {}).get("social", [])
                crypto = user.get("proofs", {}).get("summarized", {}).get("cryptocurrency", [])

                social_proofs = []
                for proof in proofs:
                    social_proofs.append({
                        "service": proof.get("service", ""),
                        "username": proof.get("username", ""),
                        "proof_url": proof.get("proof_url", ""),
                        "proof_type": proof.get("proof_type", ""),
                    })

                crypto_addresses = []
                for coin in crypto:
                    crypto_addresses.append({
                        "address": coin.get("address", ""),
                        "coin_symbol": coin.get("coin_symbol", ""),
                    })

                profile_data = {
                    "username": basics.get("username", ""),
                    "full_name": profile.get("full_name", ""),
                    "bio": profile.get("bio", ""),
                    "location": profile.get("location", ""),
                    "website": profile.get("website", ""),
                    "twitter": profile.get("twitter", ""),
                    "created": basics.get("created", 0),
                    "last_modified": basics.get("last_modified", 0),
                    "social_proofs": social_proofs,
                    "crypto_addresses": crypto_addresses,
                    "profile_url": f"https://keybase.io/{target}",
                }

                return RawResult(
                    collector_name=self.name,
                    collector_version=self.version,
                    target=target,
                    target_type=target_type,
                    query=f"keybase:user:{target}",
                    status=ObservationStatus.SUCCESS,
                    raw_response={"profile": profile_data, "found": True},
                    normalized_value=target,
                    confidence=0.9,
                    metadata={
                        "proof_count": len(social_proofs),
                        "crypto_count": len(crypto_addresses),
                        "services": [p["service"] for p in social_proofs],
                    },
                )

        except httpx.TimeoutException:
            return RawResult(
                collector_name=self.name,
                collector_version=self.version,
                target=target,
                target_type=target_type,
                query=f"keybase:user:{target}",
                status=ObservationStatus.TIMEOUT,
                error_message="Keybase API request timed out",
            )
        except Exception as exc:
            return RawResult(
                collector_name=self.name,
                collector_version=self.version,
                target=target,
                target_type=target_type,
                query=f"keybase:user:{target}",
                status=ObservationStatus.ERROR,
                error_message=f"Keybase collection failed: {exc}",
            )
