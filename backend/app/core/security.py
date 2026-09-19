"""Security utilities — SSRF protection, input validation, safe URL handling.

All external-facing code must use these utilities to prevent server-side
request forgery and other injection attacks.
"""

from __future__ import annotations

import ipaddress
import logging
import re
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# RFC 1918 + loopback + link-local + cloud metadata ranges
_BLOCKED_NETWORKS = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),  # link-local / cloud metadata
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),  # IPv6 ULA
    ipaddress.ip_network("fe80::/10"),  # IPv6 link-local
]

# Blocked hostname patterns
_BLOCKED_HOSTNAMES = re.compile(
    r"^(localhost|"
    r"0\.0\.0\.0|"
    r"metadata\.google\.internal|"
    r"169\.254\.169\.254)$",
    re.IGNORECASE,
)


class SSRFBlockedError(Exception):
    """Raised when a URL targets a blocked internal network."""


def validate_url_not_internal(url: str) -> str:
    """Validate that a URL does not target internal/private networks.

    Prevents SSRF by blocking requests to:
    - RFC 1918 private ranges (10.x, 172.16-31.x, 192.168.x)
    - Loopback (127.x, ::1)
    - Link-local (169.254.x, fe80::)
    - Cloud metadata endpoints (169.254.169.254)
    - IPv6 ULA (fc00::/7)

    Args:
        url: The URL to validate.

    Returns:
        The original URL if safe.

    Raises:
        SSRFBlockedError: If the URL targets a blocked network.
    """
    parsed = urlparse(url)
    hostname = parsed.hostname

    if hostname is None:
        raise SSRFBlockedError(f"Invalid URL: no hostname in {url}")

    # Check blocked hostname patterns
    if _BLOCKED_HOSTNAMES.match(hostname):
        raise SSRFBlockedError(f"SSRF blocked: hostname '{hostname}' targets internal network")

    # Try to parse as IP address
    try:
        ip = ipaddress.ip_address(hostname)
        for network in _BLOCKED_NETWORKS:
            if ip in network:
                raise SSRFBlockedError(f"SSRF blocked: IP {hostname} is in blocked range {network}")
    except ValueError:
        # Not an IP address, that's fine — it's a hostname
        pass

    return url


def validate_target_for_collector(target: str, target_type: str) -> str:
    """Validate and sanitize a target before passing to a collector.

    Strips dangerous characters, validates format, and prevents injection
    into URL paths or query strings.

    Args:
        target: The target string (domain, IP, URL, etc.).
        target_type: The classified target type.

    Returns:
        Sanitized target string.

    Raises:
        ValueError: If target is empty or contains dangerous characters.
    """
    if not target or not target.strip():
        raise ValueError("Target cannot be empty")

    # Strip null bytes and control characters
    cleaned = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", target)

    # Universal SSRF check on the raw target (prevents bypassing via classification)
    try:
        ip = ipaddress.ip_address(cleaned)
        for network in _BLOCKED_NETWORKS:
            if ip in network:
                raise SSRFBlockedError(f"SSRF blocked: IP {cleaned} is in blocked range {network}")
    except ValueError:
        pass

    if _BLOCKED_HOSTNAMES.match(cleaned):
        raise SSRFBlockedError(f"SSRF blocked: hostname '{cleaned}' targets internal network")

    # For URLs, validate the scheme and SSRF
    if target_type == "url":
        parsed = urlparse(cleaned)
        if parsed.scheme not in ("http", "https"):
            raise ValueError(f"Only http/https URLs are supported, got: {parsed.scheme}")
        # Validate the URL isn't trying to use credentials
        if parsed.username or parsed.password:
            raise ValueError("URLs with embedded credentials are not allowed")
        validate_url_not_internal(cleaned)

    # For domains/IPs, basic character validation
    if target_type in ("domain", "ip"):
        if not re.match(r"^[a-zA-Z0-9.\-:\/\[\]]+$", cleaned):
            raise ValueError(f"Target contains invalid characters: {cleaned}")

    return cleaned


def sanitize_error_message(exc: Exception) -> str:
    """Sanitize an exception message for client-facing error responses.

    Removes internal paths, stack traces, and sensitive details while
    preserving enough information for debugging.

    Args:
        exc: The caught exception.

    Returns:
        Safe, client-facing error message.
    """
    msg = str(exc)

    # Remove file paths (Windows and Unix)
    msg = re.sub(r"[A-Za-z]:\\[^\s\"']+", "[path]", msg)
    msg = re.sub(r"\/(?:usr|etc|var|home|tmp|opt|proc|sys)\/[^\s\"']+", "[path]", msg)

    # Remove IP addresses and ports that might be internal
    msg = re.sub(r"\b(?:10\.|172\.(?:1[6-9]|2\d|3[01])\.|192\.168\.)[^\s\"']+", "[internal]", msg)

    # Remove connection strings
    msg = re.sub(r"postgresql://[^\s\"']+", "[db]", msg)
    msg = re.sub(r"bolt://[^\s\"']+", "[neo4j]", msg)

    # Truncate very long messages
    if len(msg) > 200:
        msg = msg[:200] + "..."

    return msg


# Pattern for secrets/tokens that must never be persisted
_SECRET_RE = re.compile(
    r"(?:api[_-]?key|token|secret|password|authorization|bearer|credential)"
    r"\s*[=:]\s*\S+(?:\s+\S+)?",
    re.IGNORECASE,
)


def sanitize_collector_error(msg: str | None) -> str:
    """Sanitize a collector error message for safe persistence.

    Removes secrets, API keys, internal paths, connection strings, and
    other sensitive details. Used before persisting error_message to the
    observations table.

    Args:
        msg: Raw error message from a collector.

    Returns:
        Safe, truncated error message suitable for storage.
    """
    if not msg:
        return ""

    # Redact secrets/tokens
    msg = _SECRET_RE.sub(
        lambda m: m.group(0).split("=")[0].split(":")[0].strip() + "=[REDACTED]", msg
    )

    # Remove file paths (Windows and Unix)
    msg = re.sub(r"[A-Za-z]:\\[^\s\"']+", "[path]", msg)
    msg = re.sub(r"\/(?:usr|etc|var|home|tmp|opt|proc|sys)\/[^\s\"']+", "[path]", msg)

    # Remove internal IP addresses
    msg = re.sub(r"\b(?:10\.|172\.(?:1[6-9]|2\d|3[01])\.|192\.168\.)[^\s\"']+", "[internal]", msg)

    # Remove connection strings
    msg = re.sub(r"postgresql://[^\s\"']+", "[db]", msg)
    msg = re.sub(r"bolt://[^\s\"']+", "[neo4j]", msg)

    # Truncate
    if len(msg) > 500:
        msg = msg[:500] + "..."

    return msg
