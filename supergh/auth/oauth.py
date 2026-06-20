"""GitHub OAuth Device Flow auth provider."""

from __future__ import annotations

import time
import webbrowser
from datetime import datetime, timedelta
from typing import Optional

import requests
from rich.console import Console

from supergh.auth.base import AuthProvider, AuthStatus
from supergh.auth.store import TokenStore

GITHUB_DEVICE_CODE_URL = "https://github.com/login/device/code"
GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
GITHUB_API = "https://api.github.com"

# No built-in client ID — user must register via: sgh auth setup-oauth
CLIENT_ID = ""

console = Console()


class GitHubOAuthAuth(AuthProvider):
    """Auth via GitHub OAuth Device Flow."""

    def __init__(self, org: str = ""):
        self._org = org
        self._store = TokenStore(namespace="oauth")
        self._cached_token: Optional[str] = None

    def login(self, client_id: str = ""):
        """Run the full device flow interactively."""
        from supergh.config import get_config
        cid = client_id or get_config().get("oauth.client_id", "") or CLIENT_ID
        if not cid:
            console.print("[red]No OAuth Client ID configured.[/red]")
            console.print("Set it with: sgh config set oauth.client_id <your_client_id>")
            console.print("Or login with a PAT: sgh auth login --pat")
            raise SystemExit(1)

        # Step 1: request device code
        resp = requests.post(
            GITHUB_DEVICE_CODE_URL,
            data={"client_id": cid, "scope": "repo read:org admin:org"},
            headers={"Accept": "application/json"},
            timeout=30,
        )
        if resp.status_code == 404:
            console.print("[red]OAuth App not found. Check your client_id.[/red]")
            raise SystemExit(1)
        resp.raise_for_status()
        data = resp.json()

        device_code = data["device_code"]
        user_code = data["user_code"]
        verification_uri = data["verification_uri"]
        interval = data.get("interval", 5)

        # Step 2: display code and open browser
        console.print(f"\n[bold]Open this URL:[/bold] {verification_uri}")
        console.print(f"[bold]Enter this code:[/bold] [green]{user_code}[/green]\n")
        try:
            webbrowser.open(verification_uri)
        except Exception:
            pass

        # Step 3: poll for token
        console.print("Waiting for authorization...", style="dim")
        while True:
            time.sleep(interval)
            token_resp = requests.post(
                GITHUB_TOKEN_URL,
                data={
                    "client_id": cid,
                    "device_code": device_code,
                    "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                },
                headers={"Accept": "application/json"},
                timeout=30,
            )
            token_data = token_resp.json()

            if "access_token" in token_data:
                self._save_tokens(token_data)
                username = self._fetch_username(token_data["access_token"])
                console.print(f"[green]Logged in as {username}[/green]")
                return
            elif token_data.get("error") == "authorization_pending":
                continue
            elif token_data.get("error") == "slow_down":
                interval += 5
            elif token_data.get("error") == "expired_token":
                console.print("[red]Device code expired. Please try again.[/red]")
                raise SystemExit(1)
            else:
                console.print(f"[red]Error: {token_data.get('error_description', 'Unknown')}[/red]")
                raise SystemExit(1)

    def _save_tokens(self, data: dict):
        expires_in = data.get("expires_in", 28800)  # default 8h
        expires_at = datetime.utcnow() + timedelta(seconds=expires_in)
        self._store.set_token("access_token", data["access_token"], expires_at)
        if "refresh_token" in data:
            refresh_expiry = datetime.utcnow() + timedelta(days=180)
            self._store.set_token("refresh_token", data["refresh_token"], refresh_expiry)

    def _fetch_username(self, token: str) -> str:
        resp = requests.get(
            f"{GITHUB_API}/user",
            headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"},
            timeout=30,
        )
        resp.raise_for_status()
        username = resp.json()["login"]
        self._store.set_token("username", username)
        return username

    def get_token(self) -> str:
        if self._cached_token:
            return self._cached_token

        token = self._store.get_token("access_token")
        if token:
            self._cached_token = token
            return token

        # Try refresh
        refresh = self._store.get_token("refresh_token")
        if refresh:
            return self._refresh(refresh)

        raise RuntimeError("Not authenticated. Run: sgh auth login")

    def _resolve_client_id(self) -> str:
        """Resolve client ID: keychain > config > built-in default."""
        app_store = TokenStore(namespace="oauth_app")
        cid = app_store.get_token("client_id")
        if cid:
            return cid
        from supergh.config import get_config
        cid = get_config().get("oauth.client_id", "")
        if cid:
            return cid
        return CLIENT_ID

    def _refresh(self, refresh_token: str) -> str:
        cid = self._resolve_client_id()
        resp = requests.post(
            GITHUB_TOKEN_URL,
            data={
                "client_id": cid,
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
            },
            headers={"Accept": "application/json"},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        if "access_token" not in data:
            raise RuntimeError("Token refresh failed. Run: sgh auth login")
        self._save_tokens(data)
        self._cached_token = data["access_token"]
        return data["access_token"]

    def is_authenticated(self) -> bool:
        return self._store.get_token("access_token") is not None or self._store.get_token("refresh_token") is not None

    def logout(self):
        self._store.clear_all()
        self._cached_token = None

    def status(self) -> AuthStatus:
        username_raw = self._store.get_token("username")
        expiry = self._store.get_expiry("access_token")
        return AuthStatus(
            authenticated=self.is_authenticated(),
            auth_type="oauth",
            username=username_raw,
            org=self._org,
            expires_at=expiry,
        )
