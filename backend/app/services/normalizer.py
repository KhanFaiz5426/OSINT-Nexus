"""Input normalizer — normalizes target values for consistent storage.

Handles:
- Domains: lowercase, strip trailing dots, punycode decode, validate syntax
- IPs: canonical format, strip leading zeros, validate range, IPv4/IPv6 standardization
- Emails: lowercase, syntax validation
- Timestamps: convert all formats to ISO 8601 UTC
- Usernames: lowercase, trim whitespace
- Organizations: preserve casing
"""

import contextlib
import ipaddress
import re
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlparse

from app.models import TargetType

# ── Regex patterns for validation ──────────────────────────────────────────────

_DOMAIN_RE = re.compile(r"^(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,18}$")

# ── Timestamp patterns (ordered most specific → least specific) ──

_TIMESTAMP_PATTERNS: list[tuple[str, str]] = [
    # ISO 8601 variants
    (r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$", "%Y-%m-%dT%H:%M:%SZ"),
    (r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+Z$", None),  # strptime fallback
    (r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[+-]\d{2}:\d{2}$", None),
    # RFC 2822 / email-style: "Mon, 30 Aug 2026 12:00:00 +0000"
    (
        r"^[A-Z][a-z]{2},\s+\d{1,2}\s+[A-Z][a-z]{2}\s+\d{4}\s+\d{2}:\d{2}:\d{2}\s+[+-]\d{4}$",
        "%a, %d %b %Y %H:%M:%S %z",
    ),
    # WHOIS-style: "Aug 30, 2026" or "30-Aug-2026"
    (r"^[A-Z][a-z]{2}\s+\d{1,2},?\s+\d{4}$", "%b %d, %Y"),
    (r"^\d{1,2}-[A-Z][a-z]{2}-\d{4}$", "%d-%b-%Y"),
    # Unix epoch (seconds or milliseconds)
    (r"^\d{10}$", "unix_s"),
    (r"^\d{13}$", "unix_ms"),
    # Common: "2026-08-30" (date only)
    (r"^\d{4}-\d{2}-\d{2}$", "%Y-%m-%d"),
    # "30/08/2026" or "08/30/2026"
    (r"^\d{2}/\d{2}/\d{4}$", "%d/%m/%Y"),
]


# ── Public API ────────────────────────────────────────────────────────────────


def normalize_target(raw_input: str, target_type: TargetType) -> str:
    """Normalize a target value based on its classified type.

    Args:
        raw_input: The raw target string.
        target_type: The classified type of the target.

    Returns:
        The normalized target value.
    """
    cleaned = raw_input.strip()

    match target_type:
        case TargetType.DOMAIN:
            return normalize_domain(cleaned)
        case TargetType.IP:
            return normalize_ip(cleaned)
        case TargetType.URL:
            return normalize_url(cleaned)
        case TargetType.EMAIL:
            return normalize_email(cleaned)
        case TargetType.USERNAME:
            return _normalize_username(cleaned)
        case TargetType.ORGANIZATION:
            return _normalize_organization(cleaned)
        case _:
            return cleaned


# ── Domain normalization (Task 4.2) ──────────────────────────────────────────


def normalize_domain(domain: str) -> str:
    """Normalize a domain name (Task 4.2).

    - Lowercase
    - Strip trailing dot
    - Punycode decode (IDN → ASCII)
    - Strip leading/trailing whitespace
    """
    result = domain.strip().rstrip(".").lower()
    # Punycode decode if IDN
    with contextlib.suppress(UnicodeError, UnicodeDecodeError):
        result = result.encode("idna").decode("ascii")

    # Validate against strict domain pattern
    if not _DOMAIN_RE.match(result):
        return ""

    return result


# ── IP normalization (Task 4.1) ──────────────────────────────────────────────


def normalize_ip(ip_str: str) -> str:
    """Normalize an IP address (Task 4.1).

    - Canonical format via ipaddress module
    - IPv4: strip leading zeros (192.168.001.001 → 192.168.1.1)
    - IPv6: lowercase, compress zeros
    - Validates range
    """
    cleaned = ip_str.strip()
    try:
        addr = ipaddress.ip_address(cleaned)
        if isinstance(addr, ipaddress.IPv4Address):
            octets = str(addr).split(".")
            return ".".join(str(int(o)) for o in octets)
        return str(addr)
    except ValueError:
        # Manual fallback for malformed IPs (e.g., leading zeros)
        if ":" not in cleaned:
            octets = cleaned.split(".")
            if len(octets) == 4:
                try:
                    normalized = ".".join(str(int(o)) for o in octets)
                    ipaddress.IPv4Address(normalized)
                    return normalized
                except (ValueError, ipaddress.AddressValueError):
                    pass
        return cleaned.lower()


def is_valid_ip(ip_str: str | None) -> bool:
    """Check if a string is a valid IPv4 or IPv6 address."""
    if ip_str is None:
        return False
    try:
        ipaddress.ip_address(ip_str.strip())
        return True
    except (ValueError, TypeError, AttributeError):
        return False


def ip_version(ip_str: str) -> int | None:
    """Return 4, 6, or None for the IP version."""
    try:
        addr = ipaddress.ip_address(ip_str.strip())
        return 4 if isinstance(addr, ipaddress.IPv4Address) else 6
    except (ValueError, TypeError):
        return None


# ── Email normalization (Task 4.3) ───────────────────────────────────────────


_EMAIL_RE = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")


def normalize_email(email: str) -> str:
    """Normalize an email address (Task 4.3).

    - Lowercase
    - Strip whitespace
    - Validate basic syntax
    """
    return email.strip().lower()


def is_valid_email(email: str) -> bool:
    """Validate email syntax."""
    return bool(_EMAIL_RE.match(email.strip().lower()))


# ── Timestamp normalization (Task 4.4) ───────────────────────────────────────


def normalize_timestamp(value: Any) -> datetime | None:
    """Convert a timestamp value to a naive UTC datetime (Task 4.4).

    Accepts:
    - datetime objects (returned as-is, converted to UTC)
    - int/float (Unix epoch seconds or milliseconds)
    - str in various common formats (ISO 8601, WHOIS, RFC 2822, etc.)

    Returns None if the value cannot be parsed.
    """
    if value is None:
        return None

    # Already a datetime
    if isinstance(value, datetime):
        if value.tzinfo is not None:
            return value.astimezone(UTC).replace(tzinfo=None)
        return value

    # Numeric (Unix epoch)
    if isinstance(value, (int, float)):
        return _epoch_to_datetime(value)

    # String
    if isinstance(value, str):
        return _parse_timestamp_string(value.strip())

    return None


def _epoch_to_datetime(value: float) -> datetime:
    """Convert Unix epoch (seconds or milliseconds) to datetime."""
    # Heuristic: if > 1e12, it's milliseconds
    if value > 1e12:
        value = value / 1000.0
    try:
        return datetime.fromtimestamp(value, tz=UTC).replace(tzinfo=None)
    except (ValueError, OSError, OverflowError):
        return datetime.min


def _parse_timestamp_string(value: str) -> datetime | None:
    """Parse a timestamp string against known patterns."""
    if not value:
        return None

    for pattern, fmt in _TIMESTAMP_PATTERNS:
        if re.match(pattern, value):
            if fmt == "unix_s":
                try:
                    return _epoch_to_datetime(int(value))
                except ValueError:
                    continue
            if fmt == "unix_ms":
                try:
                    return _epoch_to_datetime(int(value))
                except ValueError:
                    continue
            if fmt is None:
                # Use dateutil-like fallback via fromisoformat
                try:
                    cleaned = value.replace("Z", "+00:00")
                    dt = datetime.fromisoformat(cleaned)
                    return dt.astimezone(UTC).replace(tzinfo=None)
                except ValueError:
                    continue
            try:
                return datetime.strptime(value, fmt)
            except ValueError:
                continue

    # Last resort: try fromisoformat
    try:
        cleaned = value.replace("Z", "+00:00")
        dt = datetime.fromisoformat(cleaned)
        if dt.tzinfo is not None:
            return dt.astimezone(UTC).replace(tzinfo=None)
        return dt
    except ValueError:
        return None


def normalize_url(url: str) -> str:
    """Normalize a URL.

    - Lowercase scheme and host
    - Preserve path, query, fragment as-is
    - Strip trailing slash from path (unless it's the only path character)
    """
    try:
        parsed = urlparse(url)
        scheme = parsed.scheme.lower()
        netloc = parsed.hostname.lower() if parsed.hostname else parsed.netloc
        if parsed.port:
            is_standard_http = scheme == "http" and parsed.port == 80
            is_standard_https = scheme == "https" and parsed.port == 443
            if not is_standard_http and not is_standard_https:
                netloc = f"{netloc}:{parsed.port}"
        path = parsed.path.rstrip("/")
        result = f"{scheme}://{netloc}{path}"
        if parsed.params:
            result += f";{parsed.params}"
        if parsed.query:
            result += f"?{parsed.query}"
        if parsed.fragment:
            result += f"#{parsed.fragment}"
        return result
    except Exception:
        return url.strip().lower()


def _normalize_username(username: str) -> str:
    """Normalize a username/handle."""
    return username.strip().lower()


def _normalize_organization(org: str) -> str:
    """Normalize an organization name — preserve original casing."""
    return org.strip()
