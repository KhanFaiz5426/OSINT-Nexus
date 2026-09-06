"""Username variation generator — expand investigation targets.

Task 7.12: Generate plausible username variations to expand OSINT coverage.
People often reuse similar usernames across platforms with minor differences
(separators, numbers, prefixes/suffixes). This module generates those
variations systematically.

Security: Output is advisory. Variations are passed to collectors as-is.
Each collector handles sanitization for its target platform.
"""

from __future__ import annotations

import logging
import re
from itertools import product

logger = logging.getLogger(__name__)

# Common separators people use in usernames
_SEPARATORS = ["", ".", "-", "_"]

# Common prefixes/suffixes
_PREFIXES = ["the", "real", "official", "i_am"]
_SUFFIXES = ["0", "1", "2", "00", "01", "42", "1337", "dev", "ops", "sec"]

# Leet speak mapping (letter -> possible numeric substitutes)
_LEET_MAP = {
    "a": ["4", "@"],
    "e": ["3"],
    "i": ["1", "!"],
    "o": ["0"],
    "s": ["5", "$"],
    "t": ["7"],
    "l": ["1"],
    "b": ["8"],
    "g": ["9"],
    "z": ["2"],
}

# Platforms where username profiles are publicly indexed
_PROFILE_PLATFORMS = [
    ("github.com", "GitHub"),
    ("gitlab.com", "GitLab"),
    ("reddit.com", "Reddit"),
    ("keybase.io", "Keybase"),
    ("news.ycombinator.com", "HackerNews"),
    ("twitter.com", "Twitter/X"),
    ("x.com", "Twitter/X"),
    ("instagram.com", "Instagram"),
    ("linkedin.com", "LinkedIn"),
    ("youtube.com", "YouTube"),
    ("medium.com", "Medium"),
    ("dev.to", "Dev.to"),
    ("stackoverflow.com", "StackOverflow"),
    ("twitch.tv", "Twitch"),
    ("t.me", "Telegram"),
    ("telegram.me", "Telegram"),
]


def _split_username_parts(username: str) -> list[str]:
    """Split a username into meaningful parts using common separators."""
    # Split on non-alphanumeric characters including whitespace
    parts = re.split(r"[._\-\s]+", username)
    # Also try camelCase splitting
    camel_parts = re.sub(r"([a-z])([A-Z])", r"\1 \2", username).split()
    # Merge: use separator-split as primary, add camel parts if different
    all_parts = list(dict.fromkeys(parts + camel_parts))
    return [p for p in all_parts if p]


def _generate_leet_variations(word: str, max_variations: int = 4) -> list[str]:
    """Generate leet speak variations of a word.

    Uses at most max_variations substitutions to avoid explosion.
    """
    candidates = []
    # Find positions that have leet substitutions
    positions = [(i, ch) for i, ch in enumerate(word.lower()) if ch in _LEET_MAP]

    if not positions:
        return []

    # Generate substitutions for 1-2 positions (keep it small)
    for count in range(1, min(3, len(positions) + 1)):
        for combo in product(range(len(positions)), repeat=count):
            if len(set(combo)) != count:
                continue
            variation = list(word)
            for idx in combo:
                pos, char = positions[idx]
                variation[pos] = _LEET_MAP[char][0]
            candidates.append("".join(variation))

    return list(dict.fromkeys(candidates))[:max_variations]


def generate_username_variations(
    username: str,
    max_variations: int = 15,
) -> list[str]:
    """Generate plausible username variations for OSINT investigation.

    Produces a list of username variations by:
    1. Splitting the username into parts
    2. Trying different separators (., -, _, none)
    3. Adding common prefixes/suffixes
    4. Generating leet speak variations
    5. Generating partial/shortened versions

    The original username is always included as the first element.

    Args:
        username: The original username to generate variations for.
        max_variations: Maximum number of variations to return.

    Returns:
        List of username variations, starting with the original.
    """
    if not username or not username.strip():
        return [username]

    variations: list[str] = [username.lower()]
    parts = _split_username_parts(username)

    if len(parts) < 2:
        # Single word username — try separators between chars and with prefixes/suffixes
        # Try prefix variations
        for prefix in _PREFIXES[:2]:
            var = f"{prefix}{username.lower()}"
            if var not in variations:
                variations.append(var)

        # Try suffix variations
        for suffix in _SUFFIXES[:3]:
            var = f"{username.lower()}{suffix}"
            if var not in variations:
                variations.append(var)

        # Try leet variations
        for leet_var in _generate_leet_variations(username.lower()):
            if leet_var not in variations:
                variations.append(leet_var)

    else:
        # Multi-part username — try different separators
        for sep in _SEPARATORS:
            var = sep.join(parts)
            if var not in variations:
                variations.append(var)

        # Try without one part (shortened)
        if len(parts) > 2:
            for i in range(len(parts)):
                shortened = parts[:i] + parts[i + 1 :]
                for sep in _SEPARATORS[:2]:
                    var = sep.join(shortened)
                    if var not in variations and var:
                        variations.append(var)

        # Try prefix + joined
        joined = "".join(parts)
        for prefix in _PREFIXES[:2]:
            var = f"{prefix}{joined}"
            if var not in variations:
                variations.append(var)

        # Try suffix + joined
        for suffix in _SUFFIXES[:3]:
            var = f"{joined}{suffix}"
            if var not in variations:
                variations.append(var)

    # Deduplicate while preserving order
    seen = set()
    unique: list[str] = []
    for v in variations:
        if v not in seen and v != username.lower():
            seen.add(v)
            unique.append(v)

    result = [username.lower()] + unique[:max_variations]
    logger.info(
        "Generated %d variations for username '%s'",
        len(result) - 1,
        username,
    )
    return result


def generate_search_queries(
    username: str,
    real_name: str | None = None,
    max_queries: int = 20,
) -> list[dict[str, str]]:
    """Generate OSINT search queries for a username.

    Returns a list of dicts with 'query' and 'description' keys, each
    representing a DuckDuckGo search query to find the person online.

    Args:
        username: The target username.
        real_name: Optional real name discovered from previous searches.
        max_queries: Maximum number of queries to generate.

    Returns:
        List of search query dicts.
    """
    queries: list[dict[str, str]] = []

    # 1. Exact username on each platform
    for domain, platform in _PROFILE_PLATFORMS[:8]:
        queries.append({
            "query": f"site:{domain} \"{username}\"",
            "description": f"{platform} profile",
        })

    # 2. Username variations on key platforms
    variations = generate_username_variations(username, max_variations=5)
    for var in variations[1:4]:  # Skip original, take top 3
        queries.append({
            "query": f'"{var}" profile OR account OR user',
            "description": f'Profile for "{var}"',
        })

    # 3. Username without separators on social platforms
    no_sep = re.sub(r"[._\-\s]", "", username)
    if no_sep != username.lower():
        queries.append({
            "query": f'"{no_sep}" site:twitter.com OR site:instagram.com OR site:reddit.com',
            "description": f'Social media (no separators: {no_sep})',
        })

    # 4. General username search
    queries.append({
        "query": f'"{username}" about OR bio OR profile OR portfolio',
        "description": "General profile search",
    })

    # 5. If we found a real name, search for it
    if real_name:
        queries.append({
            "query": f'"{real_name}" site:linkedin.com',
            "description": f'LinkedIn for "{real_name}"',
        })
        queries.append({
            "query": f'"{real_name}" site:twitter.com OR site:x.com',
            "description": f'Twitter/X for "{real_name}"',
        })
        queries.append({
            "query": f'"{real_name}" site:github.com',
            "description": f'GitHub for "{real_name}"',
        })
        # Search for the name + username together
        queries.append({
            "query": f'"{real_name}" "{username}"',
            "description": f'Name + username correlation',
        })

    # 6. Reverse lookup: search for common patterns
    parts = _split_username_parts(username)
    if len(parts) > 1:
        # Try "firstname lastname" style
        queries.append({
            "query": " ".join(parts),
            "description": f'Search as name: {" ".join(parts)}',
        })

    return queries[:max_queries]


def extract_real_name_from_profile(profile_data: dict) -> str | None:
    """Extract a real name from collector profile data.

    Checks common profile fields for a usable real name.

    Args:
        profile_data: Profile dict from a collector.

    Returns:
        Real name string if found and valid, else None.
    """
    # Check common name fields
    for field in ("full_name", "name", "display_name", "real_name", "bio_name"):
        value = profile_data.get(field)
        if value and isinstance(value, str):
            value = value.strip()
            # Basic sanity: at least 2 chars, has a space (likely real name)
            if len(value) >= 2 and " " in value:
                return value

    return None
