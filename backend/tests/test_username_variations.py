"""Username variation generator tests.

Tests for the username variation generator and search query generation.
"""

from __future__ import annotations

import pytest

from app.services.username_variations import (
    extract_real_name_from_profile,
    generate_search_queries,
    generate_username_variations,
)


class TestUsernameVariations:
    """Tests for username variation generation."""

    def test_original_included_first(self):
        """Original username should always be the first variation."""
        variations = generate_username_variations("mjkhan1400")
        assert variations[0] == "mjkhan1400"

    def test_single_word_variations(self):
        """Single-word username generates prefix/suffix variations."""
        variations = generate_username_variations("mjkhan")
        assert "mjkhan" in variations[0]
        # Should have prefix variations
        assert any("the" in v for v in variations)
        # Should have suffix variations
        assert any(v.endswith("0") for v in variations[1:])

    def test_multi_part_variations(self):
        """Multi-part username generates separator variations."""
        variations = generate_username_variations("mjk_khan1400")
        # Should try different separators
        assert "mjk_khan1400" in variations[0]
        # Should have some variation with different separator or prefix
        assert len(variations) > 1

    def test_max_variations_limit(self):
        """Respects max_variations parameter."""
        variations = generate_username_variations("testuser", max_variations=5)
        assert len(variations) <= 6  # original + 5 variations

    def test_no_duplicates(self):
        """Variations should not contain duplicates."""
        variations = generate_username_variations("mjkhan1400")
        assert len(variations) == len(set(variations))

    def test_case_insensitive(self):
        """Variations should be lowercase."""
        variations = generate_username_variations("MJkhan1400")
        for v in variations:
            assert v == v.lower()

    def test_leet_speak_variations(self):
        """Leet speak substitutions are generated."""
        variations = generate_username_variations("hacker")
        # Should have at least one leet variation (h4cker, etc.)
        assert len(variations) > 1

    def test_empty_username(self):
        """Empty username returns minimal variations."""
        variations = generate_username_variations("")
        # Empty username should still return at least the original
        assert "" in variations
        # But should not generate meaningful variations
        assert len(variations) <= 2


class TestSearchQueries:
    """Tests for OSINT search query generation."""

    def test_queries_have_required_fields(self):
        """All queries should have 'query' and 'description' fields."""
        queries = generate_search_queries("mjkhan1400")
        for q in queries:
            assert "query" in q
            assert "description" in q

    def test_site_searches_included(self):
        """Should include site-specific searches for key platforms."""
        queries = generate_search_queries("mjkhan1400")
        query_texts = [q["query"] for q in queries]
        # Should search GitHub
        assert any("github.com" in qt for qt in query_texts)
        # Should search Reddit
        assert any("reddit.com" in qt for qt in query_texts)

    def test_real_name_queries(self):
        """Should generate queries for real name if provided."""
        queries = generate_search_queries("mjkhan1400", real_name="Muhammad Khan")
        query_texts = [q["query"] for q in queries]
        # Should search for the real name
        assert any("Muhammad Khan" in qt for qt in query_texts)
        # Should search LinkedIn for the name
        assert any("linkedin.com" in qt for qt in query_texts)

    def test_max_queries_limit(self):
        """Respects max_queries parameter."""
        queries = generate_search_queries("mjkhan1400", max_queries=5)
        assert len(queries) <= 5

    def test_variation_queries_included(self):
        """Should include queries for username variations."""
        queries = generate_search_queries("mjkhan1400")
        query_texts = [q["query"] for q in queries]
        # Should have at least one variation query
        assert len(query_texts) > 1


class TestExtractRealName:
    """Tests for real name extraction from profiles."""

    def test_full_name_field(self):
        """Extracts name from 'full_name' field."""
        profile = {"full_name": "Muhammad Khan"}
        name = extract_real_name_from_profile(profile)
        assert name == "Muhammad Khan"

    def test_name_field(self):
        """Extracts name from 'name' field."""
        profile = {"name": "John Doe"}
        name = extract_real_name_from_profile(profile)
        assert name == "John Doe"

    def test_display_name_field(self):
        """Extracts name from 'display_name' field."""
        profile = {"display_name": "Jane Smith"}
        name = extract_real_name_from_profile(profile)
        assert name == "Jane Smith"

    def test_no_name_returns_none(self):
        """Returns None if no name field found."""
        profile = {"username": "johndoe", "bio": "Just a user"}
        name = extract_real_name_from_profile(profile)
        assert name is None

    def test_single_word_name_returns_none(self):
        """Returns None for single-word names (likely not real names)."""
        profile = {"full_name": "Admin"}
        name = extract_real_name_from_profile(profile)
        assert name is None

    def test_empty_name_returns_none(self):
        """Returns None for empty name strings."""
        profile = {"full_name": ""}
        name = extract_real_name_from_profile(profile)
        assert name is None

    def test_strips_whitespace(self):
        """Strips leading/trailing whitespace from names."""
        profile = {"full_name": "  John Doe  "}
        name = extract_real_name_from_profile(profile)
        assert name == "John Doe"
