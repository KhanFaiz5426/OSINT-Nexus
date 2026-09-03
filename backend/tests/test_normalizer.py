"""Tests for input normalizer."""

from app.models import TargetType
from app.services.normalizer import normalize_target


class TestNormalizeDomain:
    """Test domain normalization."""

    def test_lowercase(self):
        assert normalize_target("EXAMPLE.COM", TargetType.DOMAIN) == "example.com"

    def test_strip_trailing_dot(self):
        assert normalize_target("example.com.", TargetType.DOMAIN) == "example.com"

    def test_strip_whitespace(self):
        assert normalize_target("  example.com  ", TargetType.DOMAIN) == "example.com"

    def test_mixed_case_with_trailing_dot(self):
        assert normalize_target("Example.COM.", TargetType.DOMAIN) == "example.com"

    def test_already_normalized(self):
        assert normalize_target("example.com", TargetType.DOMAIN) == "example.com"

    def test_subdomain(self):
        assert normalize_target("Sub.Example.COM.", TargetType.DOMAIN) == "sub.example.com"


class TestNormalizeIP:
    """Test IP normalization."""

    def test_ipv4_strip_leading_zeros(self):
        assert normalize_target("192.168.001.001", TargetType.IP) == "192.168.1.1"

    def test_ipv4_canonical(self):
        assert normalize_target("10.0.0.1", TargetType.IP) == "10.0.0.1"

    def test_ipv4_max(self):
        assert normalize_target("255.255.255.255", TargetType.IP) == "255.255.255.255"

    def test_ipv4_strip_whitespace(self):
        assert normalize_target("  192.168.1.1  ", TargetType.IP) == "192.168.1.1"

    def test_ipv6_lowercased(self):
        addr = "2001:0DB8:85A3:0000:0000:8A2E:0370:7334"
        result = normalize_target(addr, TargetType.IP)
        assert result == "2001:db8:85a3::8a2e:370:7334"

    def test_ipv6_compressed(self):
        assert normalize_target("::1", TargetType.IP) == "::1"

    def test_ipv6_loopback(self):
        assert normalize_target("0:0:0:0:0:0:0:1", TargetType.IP) == "::1"


class TestNormalizeURL:
    """Test URL normalization."""

    def test_lowercase_scheme_and_host(self):
        result = normalize_target("HTTP://EXAMPLE.COM/path", TargetType.URL)
        assert result == "http://example.com/path"

    def test_preserve_path(self):
        result = normalize_target("https://example.com/path/to/page", TargetType.URL)
        assert result == "https://example.com/path/to/page"

    def test_strip_trailing_slash(self):
        result = normalize_target("https://example.com/", TargetType.URL)
        assert result == "https://example.com"

    def test_root_path_preserved(self):
        result = normalize_target("https://example.com", TargetType.URL)
        assert result == "https://example.com"

    def test_preserve_query(self):
        result = normalize_target("https://example.com/search?q=test&page=1", TargetType.URL)
        assert result == "https://example.com/search?q=test&page=1"

    def test_preserve_fragment(self):
        result = normalize_target("https://example.com/page#section", TargetType.URL)
        assert result == "https://example.com/page#section"

    def test_mixed_case_url(self):
        result = normalize_target("HTTPS://SHOP.Example.COM/Login.PHP", TargetType.URL)
        assert result == "https://shop.example.com/Login.PHP"

    def test_url_with_port(self):
        result = normalize_target("https://example.com:8443/path", TargetType.URL)
        assert result == "https://example.com:8443/path"


class TestNormalizeEmail:
    """Test email normalization."""

    def test_lowercase(self):
        assert normalize_target("User@Example.COM", TargetType.EMAIL) == "user@example.com"

    def test_strip_whitespace(self):
        assert normalize_target("  user@example.com  ", TargetType.EMAIL) == "user@example.com"

    def test_already_normalized(self):
        assert normalize_target("user@example.com", TargetType.EMAIL) == "user@example.com"

    def test_mixed_case(self):
        result = normalize_target("First.Last@Domain.Com", TargetType.EMAIL)
        assert result == "first.last@domain.com"


class TestNormalizeUsername:
    """Test username normalization."""

    def test_lowercase(self):
        assert normalize_target("CyberResearcher42", TargetType.USERNAME) == "cyberresearcher42"

    def test_strip_whitespace(self):
        assert normalize_target("  user  ", TargetType.USERNAME) == "user"

    def test_already_normalized(self):
        assert normalize_target("user", TargetType.USERNAME) == "user"

    def test_preserve_special_chars(self):
        assert normalize_target("user_name-123", TargetType.USERNAME) == "user_name-123"


class TestNormalizeOrganization:
    """Test organization normalization."""

    def test_strip_whitespace(self):
        assert normalize_target("  Acme Corp  ", TargetType.ORGANIZATION) == "Acme Corp"

    def test_preserve_case(self):
        # Organization names preserve original casing
        result = normalize_target("SecureHosting Inc.", TargetType.ORGANIZATION)
        assert result == "SecureHosting Inc."

    def test_already_normalized(self):
        assert normalize_target("Acme Corp", TargetType.ORGANIZATION) == "Acme Corp"


class TestNormalizeUnknown:
    """Test unknown type normalization."""

    def test_passthrough(self):
        assert normalize_target("some weird input", TargetType.UNKNOWN) == "some weird input"
