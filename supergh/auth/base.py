"""Abstract base for auth providers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class AuthStatus:
    authenticated: bool
    auth_type: str
    username: Optional[str] = None
    org: Optional[str] = None
    expires_at: Optional[datetime] = None
    app_name: Optional[str] = None
    app_id: Optional[str] = None

    @property
    def expires_in_seconds(self) -> Optional[int]:
        if self.expires_at is None:
            return None
        delta = (self.expires_at - datetime.utcnow()).total_seconds()
        return max(0, int(delta))


class AuthProvider(ABC):
    """Interface that all auth providers must implement."""

    @abstractmethod
    def get_token(self) -> str:
        """Return a valid token, refreshing if needed."""

    @abstractmethod
    def is_authenticated(self) -> bool:
        """Check if currently authenticated."""

    @abstractmethod
    def logout(self) -> None:
        """Clear all stored credentials."""

    @abstractmethod
    def status(self) -> AuthStatus:
        """Return current auth status."""
