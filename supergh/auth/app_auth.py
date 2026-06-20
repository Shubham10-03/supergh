"""GitHub App auth — JWT signing from PEM, installation token retrieval."""

from __future__ import annotations

import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import jwt
import requests

from supergh.auth.base import AuthProvider, AuthStatus
from supergh.auth.store import TokenStore

GITHUB_API = "https://api.github.com"


class GitHubAppAuth(AuthProvider):
    """Auth via GitHub App: PEM → JWT → installation token."""

    def __init__(self, app_id: str, pem_path: str, org: str):
        self._app_id = app_id
        self._pem_path = Path(pem_path)
        self._org = org
        self._store = TokenStore(namespace=f"app_{app_id}_{org}")
        self._cached_token: Optional[str] = None
        self._cached_expiry: Optional[datetime] = None

    def get_token(self, force_refresh: bool = False) -> str:
        if not force_refresh:
            # In-memory cache first
            if self._cached_token and self._cached_expiry:
                if datetime.utcnow() < self._cached_expiry - timedelta(minutes=5):
                    return self._cached_token

            # Keyring cache — check both keys
            token = self._store.get_token("installation_token") or self._store.get_token("access_token")
            if token:
                self._cached_token = token
                self._cached_expiry = self._store.get_expiry("installation_token")
                return token

        # Generate fresh
        return self._generate_installation_token()

    def _generate_installation_token(self) -> str:
        jwt_token = self._create_jwt()
        self._fetch_app_info(jwt_token)
        installation_id = self._get_installation_id(jwt_token)
        token, expires_at = self._create_installation_token(jwt_token, installation_id)

        self._store.set_token("installation_token", token, expires_at)
        self._cached_token = token
        self._cached_expiry = expires_at
        return token

    def _fetch_app_info(self, jwt_token: str):
        """Fetch app name, slug, and installation org, store for status display."""
        try:
            resp = requests.get(
                f"{GITHUB_API}/app",
                headers={"Authorization": f"Bearer {jwt_token}", "Accept": "application/vnd.github+json"},
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
            app_name = data.get("name", "")
            app_slug = data.get("slug", "")
            if app_name:
                self._store.set_token("app_name", app_name)
            if app_slug:
                self._store.set_token("app_slug", app_slug)
        except Exception:
            pass

        # Fetch actual installed org from installations
        try:
            resp = requests.get(
                f"{GITHUB_API}/app/installations",
                headers={"Authorization": f"Bearer {jwt_token}", "Accept": "application/vnd.github+json"},
                timeout=30,
            )
            resp.raise_for_status()
            for inst in resp.json():
                account = inst.get("account", {})
                if account.get("login", "").lower() == self._org.lower():
                    self._store.set_token("installed_org", account["login"])
                    break
        except Exception:
            pass

    def _create_jwt(self) -> str:
        """Read PEM, sign JWT, immediately discard PEM bytes."""
        pem_bytes = self._pem_path.read_bytes()
        now = int(time.time())
        payload = {
            "iat": now - 60,
            "exp": now + 600,  # 10 min max
            "iss": self._app_id,
        }
        token = jwt.encode(payload, pem_bytes, algorithm="RS256")
        # Explicitly clear PEM from memory
        pem_bytes = b"\x00" * len(pem_bytes)  # noqa: F841
        del pem_bytes
        return token

    def _get_installation_id(self, jwt_token: str) -> int:
        resp = requests.get(
            f"{GITHUB_API}/app/installations",
            headers={"Authorization": f"Bearer {jwt_token}", "Accept": "application/vnd.github+json"},
            timeout=30,
        )
        resp.raise_for_status()
        for inst in resp.json():
            if inst.get("account", {}).get("login", "").lower() == self._org.lower():
                return inst["id"]
        raise RuntimeError(f"No installation found for org '{self._org}'")

    def _create_installation_token(self, jwt_token: str, installation_id: int) -> tuple[str, datetime]:
        resp = requests.post(
            f"{GITHUB_API}/app/installations/{installation_id}/access_tokens",
            headers={"Authorization": f"Bearer {jwt_token}", "Accept": "application/vnd.github+json"},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        expires_at = datetime.fromisoformat(data["expires_at"].replace("Z", "+00:00")).replace(tzinfo=None)
        return data["token"], expires_at

    def is_authenticated(self) -> bool:
        return bool(self._store.get_token("installation_token") or self._store.get_token("access_token"))

    def logout(self):
        self._store.clear_all()
        self._cached_token = None
        self._cached_expiry = None

    def status(self) -> AuthStatus:
        expiry = self._store.get_expiry("installation_token")
        app_slug = self._store.get_token("app_slug") or ""
        app_name = self._store.get_token("app_name") or ""
        installed_org = self._store.get_token("installed_org") or self._org
        username = f"{app_slug}[bot]" if app_slug else (f"{app_name}[bot]" if app_name else f"app/{self._app_id}")
        return AuthStatus(
            authenticated=self.is_authenticated(),
            auth_type="app",
            username=username,
            org=installed_org,
            expires_at=expiry,
            app_name=app_name,
            app_id=self._app_id,
        )
