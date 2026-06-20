"""TokenStore — OS keychain wrapper via keyring. Never writes tokens to disk."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Optional

import keyring

SERVICE_NAME = "supergh"


class TokenStore:
    """Stores and retrieves tokens from OS keychain."""

    def __init__(self, namespace: str = "default"):
        self._namespace = namespace

    def _key(self, name: str) -> str:
        return f"{self._namespace}_{name}"

    def set_token(self, name: str, token: str, expires_at: Optional[datetime] = None):
        """Store a token with optional expiry."""
        payload = {"token": token, "expires_at": expires_at.isoformat() if expires_at else None}
        keyring.set_password(SERVICE_NAME, self._key(name), json.dumps(payload))

    def get_token(self, name: str) -> Optional[str]:
        """Retrieve token if it exists and is not expired."""
        raw = keyring.get_password(SERVICE_NAME, self._key(name))
        if raw is None:
            return None
        payload = json.loads(raw)
        if payload.get("expires_at"):
            exp = datetime.fromisoformat(payload["expires_at"])
            if datetime.utcnow() >= exp:
                self.delete(name)
                return None
        return payload["token"]

    def get_expiry(self, name: str) -> Optional[datetime]:
        """Get token expiry time."""
        raw = keyring.get_password(SERVICE_NAME, self._key(name))
        if raw is None:
            return None
        payload = json.loads(raw)
        if payload.get("expires_at"):
            return datetime.fromisoformat(payload["expires_at"])
        return None

    def delete(self, name: str):
        """Remove a token from keychain."""
        try:
            keyring.delete_password(SERVICE_NAME, self._key(name))
        except keyring.errors.PasswordDeleteError:
            pass

    def clear_all(self):
        """Remove all tokens for this namespace."""
        for name in ("access_token", "refresh_token", "installation_token",
                     "username", "installed_org", "app_name", "app_slug", "permissions"):
            self.delete(name)
