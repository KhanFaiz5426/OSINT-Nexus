"""Tests for Certificate Transparency collector with mocked responses."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.collectors.ct_collector import CTCollector
from app.models import ObservationStatus, TargetType


class TestCTCollector:
    """Tests for Certificate Transparency collection."""

    def setup_method(self):
        self.collector = CTCollector()

    def test_collector_metadata(self):
        assert self.collector.name == "certificate_transparency"
        assert TargetType.DOMAIN in self.collector.supported_target_types
        assert self.collector.requires_api_key is False
        assert self.collector.cache_ttl == 86400
        assert self.collector.rate_limit_rpm == 60

    def test_process_certs(self):
        data = [
            {"id": 123, "common_name": "example.com", "name_value": "*.example.com",
             "issuer_name": "Let's Encrypt", "not_before": "2024-01-01",
             "not_after": "2024-04-01", "serial_number": "abc123"},
            {"id": 123, "common_name": "example.com", "name_value": "www.example.com",
             "issuer_name": "Let's Encrypt", "not_before": "2024-01-01",
             "not_after": "2024-04-01", "serial_number": "abc123"},
            {"id": 456, "common_name": "example.com", "name_value": "mail.example.com",
             "issuer_name": "DigiCert", "not_before": "2024-02-01",
             "not_after": "2024-05-01", "serial_number": "def456"},
        ]
        certs = self.collector._process_certs(data)
        assert len(certs) == 2  # Two unique cert IDs

    def test_extract_subdomains(self):
        data = [
            {"name_value": "www.example.com"},
            {"name_value": "*.example.com"},
            {"name_value": "mail.example.com"},
            {"name_value": "other.com"},  # Not related
            {"name_value": "shop.example.com"},
        ]
        subdomains = self.collector._extract_subdomains(data, "example.com")
        assert "www.example.com" in subdomains
        assert "mail.example.com" in subdomains
        assert "shop.example.com" in subdomains
        assert "other.com" not in subdomains
        assert "example.com" in subdomains  # The domain itself

    @pytest.mark.anyio
    async def test_ct_success(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {"id": 100, "common_name": "example.com", "name_value": "example.com",
             "issuer_name": "Let's Encrypt", "not_before": "2024-01-01",
             "not_after": "2024-04-01", "serial_number": "abc"},
            {"id": 100, "common_name": "example.com", "name_value": "www.example.com",
             "issuer_name": "Let's Encrypt", "not_before": "2024-01-01",
             "not_after": "2024-04-01", "serial_number": "abc"},
        ]

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("app.collectors.ct_collector.httpx.AsyncClient", return_value=mock_client):
            result = await self.collector._collect("example.com", TargetType.DOMAIN)

        assert result.status == ObservationStatus.SUCCESS
        assert result.raw_response["subdomains"] == ["example.com", "www.example.com"]
        assert len(result.raw_response["certificates"]) == 1
        assert result.confidence == 0.95

    @pytest.mark.anyio
    async def test_ct_rate_limit(self):
        mock_response = MagicMock()
        mock_response.status_code = 429

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("app.collectors.ct_collector.httpx.AsyncClient", return_value=mock_client):
            result = await self.collector._collect("example.com", TargetType.DOMAIN)

        assert result.status == ObservationStatus.ERROR
        assert "429" in result.error_message

    @pytest.mark.anyio
    async def test_ct_empty_response(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = []

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("app.collectors.ct_collector.httpx.AsyncClient", return_value=mock_client):
            result = await self.collector._collect("newdomain.example", TargetType.DOMAIN)

        assert result.status == ObservationStatus.SUCCESS
        assert result.raw_response["certificates"] == []
        assert result.raw_response["subdomains"] == []
