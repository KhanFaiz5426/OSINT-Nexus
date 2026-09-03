"""Tests for WHOIS collector with mocked responses."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.collectors.whois_collector import WhoisCollector, _extract_field, _extract_list
from app.models import ObservationStatus, TargetType


class TestWhoisHelpers:
    """Tests for WHOIS helper functions."""

    def test_extract_field_none(self):
        assert _extract_field(None) is None

    def test_extract_field_string(self):
        assert _extract_field("Registrar Inc.") == "Registrar Inc."

    def test_extract_field_list(self):
        assert _extract_field(["First", "Second"]) == "First"

    def test_extract_field_empty_list(self):
        assert _extract_field([]) is None

    def test_extract_list_none(self):
        assert _extract_list(None) == []

    def test_extract_list_string(self):
        assert _extract_list("single") == ["single"]

    def test_extract_list_list(self):
        assert _extract_list(["a", "b"]) == ["a", "b"]


class TestWhoisCollector:
    """Tests for WHOIS data collection."""

    def setup_method(self):
        self.collector = WhoisCollector()

    def test_collector_metadata(self):
        assert self.collector.name == "whois"
        assert self.collector.version == "1.0.0"
        assert TargetType.DOMAIN in self.collector.supported_target_types
        assert self.collector.requires_api_key is False
        assert self.collector.cache_ttl == 86400

    @patch("app.collectors.whois_collector.whois.whois")
    @pytest.mark.anyio
    async def test_whois_success(self, mock_whois):
        mock_result = MagicMock()
        mock_result.registrar = "Example Registrar"
        mock_result.name = "John Doe"
        mock_result.org = "Example Org"
        mock_result.emails = "admin@example.com"
        mock_result.creation_date = "2020-01-15"
        mock_result.expiration_date = "2025-01-15"
        mock_result.updated_date = "2024-01-15"
        mock_result.name_servers = ["ns1.example.com", "ns2.example.com"]
        mock_result.status = ["clientTransferProhibited"]
        mock_result.dnssec = "unsigned"

        mock_whois.return_value = mock_result

        with patch("asyncio.get_event_loop") as mock_loop:
            mock_loop.return_value.run_in_executor = AsyncMock(return_value=mock_result)
            result = await self.collector._collect("example.com", TargetType.DOMAIN)

        assert result.status == ObservationStatus.SUCCESS
        assert result.raw_response["registrar"] == "Example Registrar"
        assert result.raw_response["registrant_name"] == "John Doe"
        assert result.confidence == 0.9

    @patch("app.collectors.whois_collector.whois.whois")
    @pytest.mark.anyio
    async def test_unsupported_target_type(self, mock_whois):
        mock_whois.side_effect = Exception("WHOIS does not support IP lookups")

        with patch("asyncio.get_event_loop") as mock_loop:
            mock_loop.return_value.run_in_executor = AsyncMock(
                side_effect=Exception("WHOIS does not support IP lookups")
            )
            result = await self.collector._collect("8.8.8.8", TargetType.IP)

        assert result.status == ObservationStatus.ERROR
