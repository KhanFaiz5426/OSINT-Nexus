"""Tests for GitHub blog/website extraction in correlator.

Regression tests ensuring that the GitHub collector's blog field is
properly extracted as URL and Domain entities.
"""

from __future__ import annotations

from app.models import EntityType
from app.services.correlator import _extract_from_github


class TestGitHubBlogExtraction:
    """Test GitHub blog field extraction."""

    def test_blog_with_url(self):
        """Blog field with full URL should extract URL and Domain entities."""
        raw_response = {
            "login": "testuser",
            "profile": {
                "blog": "https://mysite.com/about",
                "email": "",
            },
            "repositories": [],
        }

        entities, _ = _extract_from_github("testuser", raw_response)
        types_values = [(e.entity_type, e.value) for e in entities]

        # Should have URL entity
        assert any(t == EntityType.URL and "mysite.com" in v for t, v in types_values), (
            f"Missing URL entity in {types_values}"
        )

        # Should have Domain entity (www stripped)
        assert any(t == EntityType.DOMAIN and v == "mysite.com" for t, v in types_values), (
            f"Missing Domain entity in {types_values}"
        )

    def test_blog_without_scheme(self):
        """Blog field without https:// should still work."""
        raw_response = {
            "login": "testuser",
            "profile": {
                "blog": "mysite.com",
            },
            "repositories": [],
        }

        entities, _ = _extract_from_github("testuser", raw_response)
        types_values = [(e.entity_type, e.value) for e in entities]

        assert any(t == EntityType.DOMAIN and v == "mysite.com" for t, v in types_values), (
            f"Missing Domain entity in {types_values}"
        )

    def test_blog_with_www_prefix(self):
        """Blog with www. should strip www from domain."""
        raw_response = {
            "login": "testuser",
            "profile": {
                "blog": "https://www.example.org",
            },
            "repositories": [],
        }

        entities, _ = _extract_from_github("testuser", raw_response)
        domains = [e for e in entities if e.entity_type == EntityType.DOMAIN]

        assert len(domains) == 1
        assert domains[0].value == "example.org"

    def test_empty_blog(self):
        """Empty blog should not create extra entities."""
        raw_response = {
            "login": "testuser",
            "profile": {
                "blog": "",
            },
            "repositories": [],
        }

        entities, _ = _extract_from_github("testuser", raw_response)
        non_username = [e for e in entities if e.entity_type != EntityType.USERNAME]

        assert len(non_username) == 0

    def test_missing_profile(self):
        """Missing profile key should not crash."""
        raw_response = {
            "login": "testuser",
        }

        entities, _ = _extract_from_github("testuser", raw_response)
        non_username = [e for e in entities if e.entity_type != EntityType.USERNAME]

        assert len(non_username) == 0

    def test_blog_none_value(self):
        """Blog set to None should not crash."""
        raw_response = {
            "login": "testuser",
            "profile": {
                "blog": None,
            },
            "repositories": [],
        }

        entities, _ = _extract_from_github("testuser", raw_response)
        non_username = [e for e in entities if e.entity_type != EntityType.USERNAME]

        assert len(non_username) == 0

    def test_blog_has_observation_id(self):
        """Extracted entities should carry observation_id in evidence."""
        raw_response = {
            "login": "testuser",
            "profile": {
                "blog": "https://example.com",
            },
            "repositories": [],
        }

        entities, _ = _extract_from_github("testuser", raw_response, observation_id="obs-123")
        for entity in entities:
            assert "obs-123" in entity.evidence_ids

    def test_blog_entity_ids_are_namespaced(self):
        """URL and Domain entity IDs should be properly namespaced."""
        raw_response = {
            "login": "testuser",
            "profile": {
                "blog": "https://myblog.dev/posts",
            },
            "repositories": [],
        }

        entities, _ = _extract_from_github("testuser", raw_response)

        url_entities = [e for e in entities if e.entity_type == EntityType.URL]
        domain_entities = [e for e in entities if e.entity_type == EntityType.DOMAIN]

        assert url_entities[0].id.startswith("url:")
        assert domain_entities[0].id.startswith("domain:")

    def test_blog_with_port(self):
        """Blog URL with non-standard port should preserve port in URL."""
        raw_response = {
            "login": "testuser",
            "profile": {
                "blog": "https://mysite.com:8080",
            },
            "repositories": [],
        }

        entities, _ = _extract_from_github("testuser", raw_response)
        url_entities = [e for e in entities if e.entity_type == EntityType.URL]

        assert len(url_entities) == 1
        assert "mysite.com:8080" in url_entities[0].value

    def test_blog_source_is_github(self):
        """All entities should have 'github' as source."""
        raw_response = {
            "login": "testuser",
            "profile": {
                "blog": "https://example.com",
            },
            "repositories": [],
        }

        entities, _ = _extract_from_github("testuser", raw_response)
        for entity in entities:
            assert "github" in entity.sources

    def test_full_github_response_with_blog(self):
        """Full GitHub response including blog and other fields."""
        raw_response = {
            "login": "octocat",
            "email": "octocat@github.com",
            "organization": "GitHub",
            "profile": {
                "blog": "https://github.blog",
            },
            "repositories": [
                {"name": "Hello-World", "html_url": "https://github.com/octocat/Hello-World"}
            ],
        }

        entities, _ = _extract_from_github("octocat", raw_response)
        types = [e.entity_type for e in entities]

        assert EntityType.USERNAME in types
        assert EntityType.EMAIL in types
        assert EntityType.ORGANIZATION in types
        assert EntityType.REPOSITORY in types
        assert EntityType.URL in types
        assert EntityType.DOMAIN in types
