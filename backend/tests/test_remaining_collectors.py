"""Tests for IP-to-ASN, GitHub, HTTP, and Threat Intel collectors."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.collectors.github_collector import GitHubCollector
from app.collectors.http_collector import HTTPCollector
from app.collectors.ip_asn_collector import IPToASNBCollector
from app.collectors.threat_intel_collector import ThreatIntelCollector
from app.models import ObservationStatus, TargetType

# ── IP-to-ASN Tests ─────────────────────────────────────────────────────────


class TestIPToASNBCollector:
    def setup_method(self):
        self.collector = IPToASNBCollector()

    def test_metadata(self):
        assert self.collector.name == "ip_to_asn"
        assert TargetType.IP in self.collector.supported_target_types

    @pytest.mark.anyio
    async def test_ripestat_success(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": {
                "records": [
                    {"asn": 15169, "descr": "Google LLC", "prefix": "8.8.8.0/24", "country": "US"}
                ]
            }
        }
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("app.collectors.ip_asn_collector.httpx.AsyncClient", return_value=mock_client):
            result = await self.collector._collect("8.8.8.8", TargetType.IP)

        assert result.status == ObservationStatus.SUCCESS
        assert result.normalized_value == "AS15169"
        assert result.raw_response["asn"] == "15169"


# ── GitHub Tests ─────────────────────────────────────────────────────────────


class TestGitHubCollector:
    def setup_method(self):
        self.collector = GitHubCollector()

    def test_metadata(self):
        assert self.collector.name == "github"
        assert TargetType.USERNAME in self.collector.supported_target_types

    @pytest.mark.anyio
    async def test_github_user_not_found(self):
        mock_response = MagicMock()
        mock_response.status_code = 404

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("app.collectors.github_collector.httpx.AsyncClient", return_value=mock_client):
            result = await self.collector._collect("nonexistent_user_xyz", TargetType.USERNAME)

        assert result.status == ObservationStatus.ERROR
        assert "not found" in result.error_message.lower()

    @pytest.mark.anyio
    async def test_github_user_success(self):
        profile_response = MagicMock()
        profile_response.status_code = 200
        profile_response.json.return_value = {
            "login": "octocat",
            "name": "The Octocat",
            "email": "octocat@github.com",
            "bio": "GitHub mascot",
            "company": "GitHub",
            "location": "San Francisco",
            "public_repos": 8,
            "followers": 100,
            "following": 9,
            "created_at": "2011-01-25T18:44:36Z",
            "updated_at": "2024-01-01T00:00:00Z",
            "avatar_url": "https://avatars.githubusercontent.com/u/1?v=4",
        }

        repos_response = MagicMock()
        repos_response.status_code = 200
        repos_response.json.return_value = [
            {
                "name": "Hello-World",
                "description": "First repo",
                "language": "Ruby",
                "stargazers_count": 100,
                "forks_count": 50,
                "created_at": "2011-01-25T18:44:36Z",
                "updated_at": "2024-01-01T00:00:00Z",
                "html_url": "https://github.com/octocat/Hello-World",
            },
        ]

        orgs_response = MagicMock()
        orgs_response.status_code = 200
        orgs_response.json.return_value = [
            {"login": "github", "description": "GitHub org", "blog": "https://github.com"},
        ]

        mock_client = AsyncMock()

        async def get_side_effect(url, **kwargs):
            if "orgs" in str(url):
                return orgs_response
            elif "repos" in str(url):
                return repos_response
            return profile_response

        mock_client.get = AsyncMock(side_effect=get_side_effect)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("app.collectors.github_collector.httpx.AsyncClient", return_value=mock_client):
            result = await self.collector._collect("octocat", TargetType.USERNAME)

        assert result.status == ObservationStatus.SUCCESS
        assert result.raw_response["profile"]["login"] == "octocat"
        assert len(result.raw_response["repositories"]) == 1
        assert len(result.raw_response["organizations"]) == 1
        assert result.confidence == 0.95


# ── HTTP Collector Tests ────────────────────────────────────────────────────


class TestHTTPCollector:
    def setup_method(self):
        self.collector = HTTPCollector()

    def test_metadata(self):
        assert self.collector.name == "http"
        assert TargetType.DOMAIN in self.collector.supported_target_types
        assert TargetType.URL in self.collector.supported_target_types

    def test_extract_title(self):
        html = "<html><head><title>Test Page</title></head><body></body></html>"
        assert self.collector._extract_title(html) == "Test Page"

    def test_extract_title_no_title(self):
        html = "<html><body>No title here</body></html>"
        assert self.collector._extract_title(html) == ""

    def test_detect_technologies_nginx(self):
        headers = {"server": "nginx/1.18.0"}
        techs = self.collector._detect_technologies(headers, [])
        assert any(t["name"] == "Nginx" for t in techs)

    def test_detect_technologies_php(self):
        headers = {"x-powered-by": "PHP/8.2.1"}
        techs = self.collector._detect_technologies(headers, [])
        assert any(t["name"] == "PHP" for t in techs)

    def test_extract_version(self):
        assert self.collector._extract_version("nginx/1.18.0") == "1.18.0"
        assert self.collector._extract_version("PHP/8.2") == "8.2"
        assert self.collector._extract_version("no version") == ""


# ── Threat Intelligence Tests ───────────────────────────────────────────────


class TestThreatIntelCollector:
    def setup_method(self):
        self.collector = ThreatIntelCollector()

    def test_metadata(self):
        assert self.collector.name == "threat_intel"
        assert TargetType.IP in self.collector.supported_target_types
        assert TargetType.DOMAIN in self.collector.supported_target_types

    def test_calculate_threat_score_empty(self):
        assert self.collector._calculate_threat_score({}) == 0.0

    def test_calculate_threat_score_abuseipdb(self):
        results = {"abuseipdb": {"abuse_confidence_score": 85}}
        score = self.collector._calculate_threat_score(results)
        assert score == 0.85

    def test_calculate_threat_score_urlhaus_online(self):
        results = {"urlhaus": {"url_status": "online"}}
        score = self.collector._calculate_threat_score(results)
        assert score == 0.9

    @pytest.mark.anyio
    async def test_threat_intel_no_data(self):
        """When no sources return data, should return empty success."""
        with (
            patch.object(self.collector, "_query_abuseipdb", return_value=None),
            patch.object(self.collector, "_query_urlhaus", return_value=None),
        ):
            result = await self.collector._collect("safe.example.com", TargetType.DOMAIN)

        assert result.status == ObservationStatus.SUCCESS
        assert "No threat intelligence" in result.raw_response.get("message", "")
