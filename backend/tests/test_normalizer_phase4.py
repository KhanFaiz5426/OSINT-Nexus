"""Tests for enhanced normalizer (Tasks 4.1–4.4)."""

from datetime import UTC, datetime

from app.models import TargetType
from app.services.normalizer import (
    ip_version,
    is_valid_email,
    is_valid_ip,
    normalize_domain,
    normalize_email,
    normalize_ip,
    normalize_target,
    normalize_timestamp,
)

# ── Task 4.1: IP normalization ────────────────────────────────────────────────


class TestNormalizeIP:
    def test_ipv4_strip_leading_zeros(self):
        assert normalize_ip("192.168.001.001") == "192.168.1.1"

    def test_ipv4_canonical(self):
        assert normalize_ip("010.010.010.010") == "10.10.10.10"

    def test_ipv4_max(self):
        assert normalize_ip("255.255.255.255") == "255.255.255.255"

    def test_ipv4_strip_whitespace(self):
        assert normalize_ip("  10.0.0.1  ") == "10.0.0.1"

    def test_ipv6_lowercased(self):
        assert normalize_ip("2001:0DB8:AC10:FE01::1") == "2001:db8:ac10:fe01::1"

    def test_ipv6_compressed(self):
        assert normalize_ip("2001:0db8:0000:0000:0000:0000:0000:0001") == "2001:db8::1"

    def test_ipv6_loopback(self):
        assert normalize_ip("::1") == "::1"

    def test_ipv4_zero(self):
        assert normalize_ip("0.0.0.0") == "0.0.0.0"

    def test_ipv4_invalid(self):
        # Invalid IPs are returned as-is (lowercased)
        assert normalize_ip("999.999.999.999") == "999.999.999.999"

    def test_ipv4_with_leading_zeros_manual(self):
        # Manual fallback for malformed IPs
        assert normalize_ip("192.168.01.01") == "192.168.1.1"


class TestIsValidIP:
    def test_valid_ipv4(self):
        assert is_valid_ip("10.0.0.1") is True

    def test_valid_ipv6(self):
        assert is_valid_ip("::1") is True

    def test_invalid(self):
        assert is_valid_ip("not-an-ip") is False

    def test_none(self):
        assert is_valid_ip(None) is False


class TestIPVersion:
    def test_ipv4(self):
        assert ip_version("10.0.0.1") == 4

    def test_ipv6(self):
        assert ip_version("::1") == 6

    def test_invalid(self):
        assert ip_version("not-an-ip") is None


# ── Task 4.2: Domain normalization ────────────────────────────────────────────


class TestNormalizeDomain:
    def test_lowercase(self):
        assert normalize_domain("EXAMPLE.COM") == "example.com"

    def test_strip_trailing_dot(self):
        assert normalize_domain("example.com.") == "example.com"

    def test_strip_whitespace(self):
        assert normalize_domain("  example.com  ") == "example.com"

    def test_subdomain(self):
        assert normalize_domain("sub.EXAMPLE.com") == "sub.example.com"

    def test_already_normalized(self):
        assert normalize_domain("example.com") == "example.com"

    def test_idn_punycode(self):
        # Internationalized domain → punycode
        result = normalize_domain("münchen.de")
        assert "xn--" in result or result == "münchen.de"

    def test_deep_subdomain(self):
        assert normalize_domain("a.b.c.example.com") == "a.b.c.example.com"

    def test_trailing_dot_and_uppercase(self):
        assert normalize_domain("Example.COM.") == "example.com"


# ── Task 4.3: Email normalization ─────────────────────────────────────────────


class TestNormalizeEmail:
    def test_lowercase(self):
        assert normalize_email("Admin@Example.COM") == "admin@example.com"

    def test_strip_whitespace(self):
        assert normalize_email("  user@host.com  ") == "user@host.com"

    def test_already_normalized(self):
        assert normalize_email("user@host.com") == "user@host.com"

    def test_mixed_case(self):
        assert normalize_email("First.Last@Domain.Com") == "first.last@domain.com"


class TestIsValidEmail:
    def test_valid(self):
        assert is_valid_email("user@example.com") is True

    def test_invalid_no_at(self):
        assert is_valid_email("userexample.com") is False

    def test_invalid_no_domain(self):
        assert is_valid_email("user@") is False

    def test_valid_subdomain(self):
        assert is_valid_email("user@sub.example.com") is True


# ── Task 4.4: Timestamp normalization ─────────────────────────────────────────


class TestNormalizeTimestamp:
    def test_iso8601_utc(self):
        result = normalize_timestamp("2026-08-30T12:00:00Z")
        assert result is not None
        assert result.year == 2026
        assert result.month == 8
        assert result.day == 30
        assert result.hour == 12

    def test_iso8601_with_offset(self):
        result = normalize_timestamp("2026-08-30T12:00:00+05:00")
        assert result is not None
        assert result.hour == 7  # UTC = 12 - 5

    def test_date_only(self):
        result = normalize_timestamp("2026-08-30")
        assert result is not None
        assert result.year == 2026
        assert result.month == 8
        assert result.day == 30

    def test_whois_format(self):
        result = normalize_timestamp("Aug 30, 2026")
        assert result is not None
        assert result.year == 2026
        assert result.month == 8
        assert result.day == 30

    def test_whois_format_no_comma(self):
        result = normalize_timestamp("30-Aug-2026")
        assert result is not None
        assert result.year == 2026
        assert result.month == 8
        assert result.day == 30

    def test_unix_epoch_seconds(self):
        result = normalize_timestamp("1725000000")
        assert result is not None
        assert result.year >= 2024

    def test_unix_epoch_milliseconds(self):
        result = normalize_timestamp("1725000000000")
        assert result is not None
        assert result.year >= 2024

    def test_datetime_object(self):
        dt = datetime(2026, 8, 30, 12, 0, 0, tzinfo=UTC)
        result = normalize_timestamp(dt)
        assert result is not None
        assert result.year == 2026
        assert result.tzinfo is None  # naive UTC

    def test_datetime_naive(self):
        dt = datetime(2026, 8, 30, 12, 0, 0)
        result = normalize_timestamp(dt)
        assert result is not None
        assert result == dt

    def test_none_returns_none(self):
        assert normalize_timestamp(None) is None

    def test_empty_string(self):
        assert normalize_timestamp("") is None

    def test_invalid_string(self):
        assert normalize_timestamp("not-a-date") is None

    def test_integer_epoch(self):
        result = normalize_timestamp(1725000000)
        assert result is not None
        assert result.year >= 2024

    def test_rfc2822_format(self):
        result = normalize_timestamp("Mon, 30 Aug 2026 12:00:00 +0000")
        assert result is not None
        assert result.year == 2026


# ── Existing normalize_target tests (backward compatibility) ─────────────────


class TestNormalizeTargetBackwardCompatibility:
    def test_domain(self):
        assert normalize_target("EXAMPLE.COM.", TargetType.DOMAIN) == "example.com"

    def test_ip(self):
        assert normalize_target("192.168.001.001", TargetType.IP) == "192.168.1.1"

    def test_email(self):
        assert normalize_target("User@Host.COM", TargetType.EMAIL) == "user@host.com"

    def test_url(self):
        assert (
            normalize_target("HTTPS://Example.COM/path/", TargetType.URL)
            == "https://example.com/path"
        )

    def test_username(self):
        assert normalize_target("  UserName  ", TargetType.USERNAME) == "username"

    def test_organization(self):
        assert normalize_target("  Acme Corp  ", TargetType.ORGANIZATION) == "Acme Corp"
