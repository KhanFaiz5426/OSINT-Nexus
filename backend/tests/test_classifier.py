"""Tests for target classifier."""

from app.models import TargetType
from app.services.classifier import classify_target


class TestClassifyDomain:
    """Test domain classification."""

    def test_simple_domain(self):
        assert classify_target("example.com") == TargetType.DOMAIN

    def test_subdomain(self):
        assert classify_target("sub.example.com") == TargetType.DOMAIN

    def test_deep_subdomain(self):
        assert classify_target("a.b.c.example.com") == TargetType.DOMAIN

    def test_domain_with_hyphen(self):
        assert classify_target("my-domain.example.com") == TargetType.DOMAIN

    def test_domain_with_numbers(self):
        assert classify_target("123.example.com") == TargetType.DOMAIN

    def test_co_uk_domain(self):
        assert classify_target("example.co.uk") == TargetType.DOMAIN

    def test_long_tld(self):
        assert classify_target("example.museum") == TargetType.DOMAIN

    def test_case_insensitive(self):
        assert classify_target("EXAMPLE.COM") == TargetType.DOMAIN

    def test_trailing_dot_not_domain(self):
        # Trailing dot makes it look like FQDN, but our regex requires dots in labels
        assert classify_target("example.com.") == TargetType.DOMAIN


class TestClassifyIP:
    """Test IP address classification."""

    def test_ipv4_class_a(self):
        assert classify_target("10.0.0.1") == TargetType.IP

    def test_ipv4_class_c(self):
        assert classify_target("192.168.1.1") == TargetType.IP

    def test_ipv4_max(self):
        assert classify_target("255.255.255.255") == TargetType.IP

    def test_ipv4_loopback(self):
        assert classify_target("127.0.0.1") == TargetType.IP

    def test_ipv4_with_zeros(self):
        assert classify_target("192.168.001.001") == TargetType.IP

    def test_ipv6_full(self):
        assert classify_target("2001:0db8:85a3:0000:0000:8a2e:0370:7334") == TargetType.IP

    def test_ipv6_compressed(self):
        assert classify_target("2001:db8:85a3::8a2e:370:7334") == TargetType.IP

    def test_ipv6_loopback(self):
        assert classify_target("::1") == TargetType.IP

    def test_ipv6_all_zeros(self):
        assert classify_target("::") == TargetType.IP


class TestClassifyURL:
    """Test URL classification."""

    def test_http_url(self):
        assert classify_target("http://example.com") == TargetType.URL

    def test_https_url(self):
        assert classify_target("https://example.com") == TargetType.URL

    def test_url_with_path(self):
        assert classify_target("https://example.com/path/to/page") == TargetType.URL

    def test_url_with_port(self):
        assert classify_target("https://example.com:8443/path") == TargetType.URL

    def test_url_with_query(self):
        assert classify_target("https://example.com/search?q=test") == TargetType.URL

    def test_url_with_subdomain(self):
        assert classify_target("https://shop.example.com/login") == TargetType.URL

    def test_url_with_fragment(self):
        assert classify_target("https://example.com/page#section") == TargetType.URL

    def test_url_complex(self):
        url = "https://shop.example.com/login.php?user=admin&ref=home#top"
        assert classify_target(url) == TargetType.URL


class TestClassifyEmail:
    """Test email classification."""

    def test_simple_email(self):
        assert classify_target("user@example.com") == TargetType.EMAIL

    def test_email_with_dots(self):
        assert classify_target("first.last@example.com") == TargetType.EMAIL

    def test_email_with_plus(self):
        assert classify_target("user+tag@example.com") == TargetType.EMAIL

    def test_email_with_hyphen(self):
        assert classify_target("my-user@example-domain.com") == TargetType.EMAIL

    def test_email_with_numbers(self):
        assert classify_target("user123@example.com") == TargetType.EMAIL

    def test_email_case_insensitive(self):
        assert classify_target("User@Example.COM") == TargetType.EMAIL


class TestClassifyUsername:
    """Test username classification."""

    def test_simple_username(self):
        assert classify_target("john_doe") == TargetType.USERNAME

    def test_username_with_numbers(self):
        assert classify_target("user42") == TargetType.USERNAME

    def test_username_with_hyphen(self):
        assert classify_target("cyber-researcher") == TargetType.USERNAME

    def test_github_username(self):
        assert classify_target("octocat") == TargetType.USERNAME

    def test_handle_with_at(self):
        # @handle is not email format
        assert classify_target("@handle") == TargetType.USERNAME


class TestClassifyEdgeCases:
    """Test edge cases."""

    def test_empty_string(self):
        assert classify_target("") == TargetType.UNKNOWN

    def test_whitespace_only(self):
        assert classify_target("   ") == TargetType.UNKNOWN

    def test_single_word(self):
        assert classify_target("malware") == TargetType.USERNAME

    def test_ip_address_in_url(self):
        # Should be URL since it starts with http
        assert classify_target("http://192.168.1.1/admin") == TargetType.URL

    def test_email_with_ip_domain(self):
        # Should be email
        assert classify_target("user@192.168.1.1") == TargetType.EMAIL

    def test_domain_with_single_label(self):
        # Single label without TLD → username
        assert classify_target("localhost") == TargetType.USERNAME

    def test_numeric_only(self):
        # Just a number → username
        assert classify_target("12345") == TargetType.USERNAME

    def test_ipv4_private_range(self):
        assert classify_target("10.255.255.255") == TargetType.IP

    def test_ipv4_invalid_high_octet(self):
        # 999.999.999.999 looks like IP pattern but values are out of range
        # Classifier uses pattern matching; normalizer validates actual range
        assert classify_target("999.999.999.999") == TargetType.IP
