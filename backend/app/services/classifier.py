"""Target classifier — determines target type from input string.

Uses deterministic regex rules to classify investigation targets into:
domain, IP (v4/v6), URL, email, username, or organization.
"""

import re

from app.models import TargetType

# ── Regex patterns ────────────────────────────────────────────────────────────

# IPv4: four octets (allowing leading zeros for classification, normalizer handles canonical form)
_IPV4_PATTERN = re.compile(
    r"^(?:(?:25[0-5]|2[0-4]\d|1\d{2}|[0-9]{1,3})\.){3}" r"(?:25[0-5]|2[0-4]\d|1\d{2}|[0-9]{1,3})$"
)

# IPv6: full, compressed, and mixed notation
_IPV6_PATTERN = re.compile(
    r"^(?:[0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}$"  # full
    r"|(?:[0-9a-fA-F]{1,4}:){1,7}:"  # ends with ::
    r"|(?:[0-9a-fA-F]{1,4}:){1,6}:[0-9a-fA-F]{1,4}$"  # ::x
    r"|(?:[0-9a-fA-F]{1,4}:){1,5}(?::[0-9a-fA-F]{1,4}){1,2}$"
    r"|(?:[0-9a-fA-F]{1,4}:){1,4}(?::[0-9a-fA-F]{1,4}){1,3}$"
    r"|(?:[0-9a-fA-F]{1,4}:){1,3}(?::[0-9a-fA-F]{1,4}){1,4}$"
    r"|(?:[0-9a-fA-F]{1,4}:){1,2}(?::[0-9a-fA-F]{1,4}){1,5}$"
    r"|[0-9a-fA-F]{1,4}:(?::[0-9a-fA-F]{1,4}){1,6}$"
    r"|:(?::[0-9a-fA-F]{1,4}){1,7}$"  # starts with ::
    r"|::"  # just ::
    r"|(?:25[0-5]|2[0-4]\d|1\d{2}|[0-9]{1,3})\."  # IPv4-mapped
    r"(?:25[0-5]|2[0-4]\d|1\d{2}|[0-9]{1,3})\."
    r"(?:25[0-5]|2[0-4]\d|1\d{2}|[0-9]{1,3})\."
    r"(?:25[0-5]|2[0-4]\d|1\d{2}|[0-9]{1,3})"
)

# URL: starts with http(s):// — host can be domain or IP
_URL_PATTERN = re.compile(
    r"^https?://"
    r"(?:"
    r"(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]*[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}"  # domain
    r"|(?:25[0-5]|2[0-4]\d|1\d{2}|[0-9]{1,3}\.){3}"  # IPv4
    r"(?:25[0-5]|2[0-4]\d|1\d{2}|[0-9]{1,3})"
    r")"
    r"(?::\d{1,5})?"
    r"(?:/[^\s]*)?$",
    re.IGNORECASE,
)

# Domain: labels separated by dots, with valid TLD (allow optional trailing dot)
_DOMAIN_PATTERN = re.compile(r"^(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]*[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}\.?$")

# Email: standard format — domain can be domain name or IP
_EMAIL_PATTERN = re.compile(
    r"^[a-zA-Z0-9._%+-]+@"
    r"(?:"
    r"[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"  # domain with TLD
    r"|(?:25[0-5]|2[0-4]\d|1\d{2}|[0-9]{1,3}\.){3}"  # IPv4
    r"(?:25[0-5]|2[0-4]\d|1\d{2}|[0-9]{1,3})"
    r")$"
)


# ── Classification logic ─────────────────────────────────────────────────────


def classify_target(raw_input: str) -> TargetType:
    """Classify a raw input string into a TargetType.

    Classification rules (in priority order):
    1. If it contains '@' and looks like email → EMAIL
    2. If it starts with http:// or https:// → URL
    3. If it's a valid IPv4 address → IP
    4. If it's a valid IPv6 address → IP
    5. If it looks like a domain (has dots, valid TLD) → DOMAIN
    6. Otherwise → USERNAME (could be username, org, or other)

    Args:
        raw_input: The raw target string provided by the user.

    Returns:
        The classified TargetType.
    """
    cleaned = raw_input.strip()

    if not cleaned:
        return TargetType.UNKNOWN

    # 1. Email: contains @ and matches email pattern
    if "@" in cleaned and _EMAIL_PATTERN.match(cleaned):
        return TargetType.EMAIL

    # 2. URL: starts with http(s)://
    if _URL_PATTERN.match(cleaned):
        return TargetType.URL

    # 3. IPv4
    if _IPV4_PATTERN.match(cleaned):
        return TargetType.IP

    # 4. IPv6 (check before domain since IPv6 contains colons, not dots)
    if ":" in cleaned and _IPV6_PATTERN.match(cleaned):
        return TargetType.IP

    # 5. Domain: has dots and ends with valid TLD
    if _DOMAIN_PATTERN.match(cleaned):
        return TargetType.DOMAIN

    # 6. Default: treat as username
    return TargetType.USERNAME
