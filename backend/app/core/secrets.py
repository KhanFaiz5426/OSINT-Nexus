"""Secret management — Windows Credential Manager integration.

Provides secure storage and retrieval for API keys and tokens using the
OS-native keyring (Windows Credential Manager). Keys are stored under the
'osint-nexus' namespace.
"""

from __future__ import annotations

import logging
from typing import Any

import keyring
from keyring.errors import KeyringError

logger = logging.getLogger(__name__)

SERVICE_NAME = "osint-nexus"


def get_secret(key: str) -> str | None:
    """Retrieve a secret from the Credential Manager.

    Returns None if the secret does not exist or an error occurs.
    """
    try:
        return keyring.get_password(SERVICE_NAME, key)
    except KeyringError as exc:
        logger.error("Failed to retrieve secret %s: %s", key, exc)
        return None
    except Exception as exc:
        logger.error("Unexpected error retrieving secret %s: %s", key, exc)
        return None


def set_secret(key: str, value: str) -> bool:
    """Store a secret in the Credential Manager.

    Returns True if successful, False otherwise.
    """
    if not value:
        return delete_secret(key)
        
    try:
        keyring.set_password(SERVICE_NAME, key, value)
        return True
    except KeyringError as exc:
        logger.error("Failed to store secret %s: %s", key, exc)
        return False
    except Exception as exc:
        logger.error("Unexpected error storing secret %s: %s", key, exc)
        return False


def delete_secret(key: str) -> bool:
    """Remove a secret from the Credential Manager.

    Returns True if successful (or already absent), False on error.
    """
    try:
        keyring.delete_password(SERVICE_NAME, key)
        return True
    except keyring.errors.PasswordDeleteError:
        # Secret didn't exist, which is fine.
        return True
    except KeyringError as exc:
        logger.error("Failed to delete secret %s: %s", key, exc)
        return False
    except Exception as exc:
        logger.error("Unexpected error deleting secret %s: %s", key, exc)
        return False


def get_masked_api_keys() -> dict[str, bool]:
    """Check which API keys are configured (never return actual values)."""
    keys = [
        "github",
        "abuseipdb",
        "urlhaus",
        "youtube",
        "nvidia",
        "openai",
        "anthropic",
        "opencode",
    ]
    return {k: bool(get_secret(k)) for k in keys}
