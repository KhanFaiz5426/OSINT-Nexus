"""Tests for DNS collector with mocked responses."""

from unittest.mock import MagicMock, patch

import dns.exception
import dns.resolver
import pytest

from app.collectors.dns_collector import DNSCollector
from app.models import ObservationStatus, TargetType


class TestDNSCollector:
    """Tests for DNS record collection."""

    def setup_method(self):
        self.collector = DNSCollector()

    def test_collector_metadata(self):
        assert self.collector.name == "dns"
        assert self.collector.version == "1.0.0"
        assert TargetType.DOMAIN in self.collector.supported_target_types
        assert TargetType.IP in self.collector.supported_target_types
        assert self.collector.requires_api_key is False
        assert self.collector.cache_ttl == 86400
        assert self.collector.rate_limit_rpm == 600

    def test_is_ip_address(self):
        assert self.collector._is_ip_address("8.8.8.8") is True
        assert self.collector._is_ip_address("2001:db8::1") is True
        assert self.collector._is_ip_address("example.com") is False

    @patch("app.collectors.dns_collector.dns.resolver.Resolver")
    @pytest.mark.anyio
    async def test_forward_dns_success(self, mock_resolver_cls):
        mock_resolver = MagicMock()
        mock_resolver_cls.return_value = mock_resolver

        # Mock A record
        mock_a_rrset = MagicMock()
        mock_a_rrset.ttl = 300
        mock_a_rdata = MagicMock()
        mock_a_rdata.__str__ = lambda self: "93.184.216.34"
        mock_a_rrset.__iter__ = lambda self: iter([mock_a_rdata])

        # Mock NS record
        mock_ns_rrset = MagicMock()
        mock_ns_rrset.ttl = 86400
        mock_ns_rdata = MagicMock()
        mock_ns_rdata.__str__ = lambda self: "ns1.example.com"
        mock_ns_rrset.__iter__ = lambda self: iter([mock_ns_rdata])

        def resolve(domain, rtype):
            if rtype == "A":
                return mock_a_rrset
            elif rtype == "NS":
                return mock_ns_rrset
            raise dns.resolver.NoAnswer()

        mock_resolver.resolve = resolve
        mock_resolver.lifetime = 10

        result = await self.collector._collect("example.com", TargetType.DOMAIN)

        assert result.status == ObservationStatus.SUCCESS
        assert result.raw_response.get("A") is not None
        assert result.normalized_value == "93.184.216.34"
        assert result.confidence > 0.9

    @patch("app.collectors.dns_collector.dns.resolver.Resolver")
    @pytest.mark.anyio
    async def test_forward_dns_nxdomain(self, mock_resolver_cls):
        mock_resolver = MagicMock()
        mock_resolver_cls.return_value = mock_resolver

        def resolve(domain, rtype):
            raise dns.resolver.NXDOMAIN()

        mock_resolver.resolve = resolve
        mock_resolver.lifetime = 10

        result = await self.collector._collect("nonexistent.invalid", TargetType.DOMAIN)

        assert result.status == ObservationStatus.ERROR
        assert "NXDOMAIN" in result.error_message

    @patch("app.collectors.dns_collector.dns.resolver.Resolver")
    @pytest.mark.anyio
    async def test_reverse_dns_success(self, mock_resolver_cls):
        mock_resolver = MagicMock()
        mock_resolver_cls.return_value = mock_resolver

        mock_rev_name = MagicMock()
        mock_rev_name.__str__ = lambda self: "34.216.184.93.in-addr.arpa."

        mock_ptr_rrset = MagicMock()
        mock_ptr_rrset.__iter__ = lambda self: iter([MagicMock(__str__=lambda s: "example.com.")])  # noqa: E501

        patch_target = "app.collectors.dns_collector.dns.reversename.from_address"
        with patch(patch_target, return_value=mock_rev_name):
            mock_resolver.resolve = lambda name, rtype: mock_ptr_rrset
            mock_resolver.lifetime = 10

            result = await self.collector._collect("93.184.216.34", TargetType.IP)

            assert result.status == ObservationStatus.SUCCESS
            assert "PTR" in result.raw_response

    @pytest.mark.anyio
    async def test_unsupported_target_type(self):
        result = await self.collector._collect("test", TargetType.USERNAME)
        assert result.status == ObservationStatus.ERROR
        assert "cannot handle" in result.error_message.lower()
