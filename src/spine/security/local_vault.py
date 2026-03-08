"""
Local Vault — Local data encryption and secrets management.

Encrypts sensitive data at rest and manages secrets locally.
"""

from __future__ import annotations

import base64
import logging
import secrets
from typing import Any, Optional

logger = logging.getLogger(__name__)

__all__ = ["LocalVault"]


class LocalVault:
    """
    Local encryption vault for sensitive data.

    Encrypts secrets and sensitive config at rest.
    Uses simple XOR encryption for basic protection (for production,
    consider cryptography library).
    """

    def __init__(self, vault_key: Optional[bytes] = None) -> None:
        self.vault_key = vault_key or self._generate_key()
        self.secrets: dict[str, tuple[str, str]] = {}

    def _generate_key(self) -> bytes:
        """Generate a random vault key."""
        return secrets.token_bytes(32)

    def _encrypt(self, data: str) -> str:
        """Simple encryption (XOR with key)."""
        if not data:
            return ""

        key = self.vault_key
        encrypted = bytearray()

        for i, byte in enumerate(data.encode("utf-8")):
            key_byte = key[i % len(key)]
            encrypted.append(byte ^ key_byte)

        return base64.b64encode(encrypted).decode("ascii")

    def _decrypt(self, encrypted: str) -> str:
        """Simple decryption (XOR with key)."""
        if not encrypted:
            return ""

        try:
            key = self.vault_key
            encrypted_bytes = base64.b64decode(encrypted)
            decrypted = bytearray()

            for i, byte in enumerate(encrypted_bytes):
                key_byte = key[i % len(key)]
                decrypted.append(byte ^ key_byte)

            return decrypted.decode("utf-8")
        except Exception as e:
            logger.error(f"Decryption failed: {e}")
            return ""

    def put_secret(self, key: str, value: str, description: str = "") -> None:
        """Store an encrypted secret."""
        encrypted = self._encrypt(value)
        self.secrets[key] = (encrypted, description)
        logger.debug(f"Stored secret: {key}")

    def get_secret(self, key: str) -> Optional[str]:
        """Retrieve and decrypt a secret."""
        if key not in self.secrets:
            logger.warning(f"Secret not found: {key}")
            return None

        encrypted, _ = self.secrets[key]
        return self._decrypt(encrypted)

    def remove_secret(self, key: str) -> bool:
        """Remove a secret."""
        if key in self.secrets:
            del self.secrets[key]
            logger.debug(f"Removed secret: {key}")
            return True
        return False

    def list_secrets(self) -> dict[str, str]:
        """List secret keys and descriptions (without values)."""
        return {key: desc for key, (_, desc) in self.secrets.items()}

    def encrypt_config(self, config: dict[str, Any]) -> dict[str, Any]:
        """Encrypt sensitive fields in a config dict."""
        sensitive_fields = {
            "openai_api_key",
            "api_key",
            "secret",
            "password",
            "token",
        }

        encrypted = {}
        for key, value in config.items():
            if key.lower() in sensitive_fields and isinstance(value, str):
                encrypted[key] = self._encrypt(value)
            else:
                encrypted[key] = value

        return encrypted

    def decrypt_config(self, config: dict[str, Any]) -> dict[str, Any]:
        """Decrypt sensitive fields in a config dict."""
        decrypted = {}
        for key, value in config.items():
            if isinstance(value, str) and len(value) > 0 and value.startswith("__ENCRYPTED__"):
                try:
                    decrypted[key] = self._decrypt(value.replace("__ENCRYPTED__", ""))
                except Exception:
                    decrypted[key] = value
            else:
                decrypted[key] = value

        return decrypted

    def get_vault_status(self) -> dict[str, Any]:
        """Get vault status."""
        return {
            "secrets_count": len(self.secrets),
            "secrets_list": self.list_secrets(),
        }
