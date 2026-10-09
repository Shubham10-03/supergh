"""Base GitHub API client — pagination, rate limiting, retries, auth injection."""

from __future__ import annotations

import time
import re
from typing import Any, Generator, Optional
from urllib.parse import parse_qs, urlparse

import requests
from rich.console import Console

from supergh.auth.middleware import get_auth_provider

console = Console()
GITHUB_API = "https://api.github.com"
MAX_RETRIES = 3
TIMEOUT = 30

# App-level endpoints that must be called with the app JWT (Bearer), NOT the
# installation access token. These authenticate "as the GitHub App itself".
# See: https://docs.github.com/rest/apps
_JWT_ENDPOINT_PATTERNS = (
    re.compile(r"^/app$"),
    re.compile(r"^/app/.*"),                        # /app/installations, /app/hook/*, etc.
    re.compile(r"^/orgs/[^/]+/installation$"),      # get an org installation
    re.compile(r"^/users/[^/]+/installation$"),     # get a user installation
    re.compile(r"^/repos/[^/]+/[^/]+/installation$"),  # get a repo installation
    re.compile(r"^/marketplace_listing/.*"),        # marketplace (app JWT)
    re.compile(r"^/app-manifests/[^/]+/conversions$"),
)


def _endpoint_needs_jwt(path: str) -> bool:
    """Return True if an endpoint must be authenticated with the app JWT.

    ``path`` may be a full URL or an absolute API path. Query string and host
    are stripped before matching.
    """
    if not path:
        return False
    # Normalize: accept full URLs and strip query/fragment.
    if path.startswith("http"):
        path = urlparse(path).path
    else:
        path = path.split("?", 1)[0].split("#", 1)[0]
    if not path.startswith("/"):
        path = "/" + path
    path = path.rstrip("/") or "/"
    return any(p.match(path) for p in _JWT_ENDPOINT_PATTERNS)


class GitHubClient:
    """GitHub REST (and GraphQL) client with automatic auth, pagination, and rate limiting."""

    def __init__(self, debug: bool = False):
        self._debug = debug
        self._session = requests.Session()
        self._session.headers.update({"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"})

    def _inject_auth(self, path: str = "", force_jwt: Optional[bool] = None):
        """Set the Authorization header for the upcoming request.

        Token selection:
          * ``force_jwt is True``  -> use the app JWT (Bearer)
          * ``force_jwt is False`` -> use the installation/standard token (token)
          * ``force_jwt is None``  -> auto-detect from the endpoint path:
                app-level routes use the JWT, everything else the installation token.

        JWT selection only applies to GitHub App auth. For PAT/OAuth providers
        (which have no JWT), we always fall back to the standard token.
        """
        provider = get_auth_provider()

        use_jwt = force_jwt if force_jwt is not None else _endpoint_needs_jwt(path)
        if use_jwt and hasattr(provider, "get_jwt"):
            jwt_token = provider.get_jwt()
            self._session.headers["Authorization"] = f"Bearer {jwt_token}"
            if self._debug:
                console.print("[dim]auth: app JWT (Bearer)[/dim]")
            return

        token = provider.get_token()
        # Use 'token' prefix — works for all token types (PAT, OAuth, installation)
        self._session.headers["Authorization"] = f"token {token}"
        if self._debug and force_jwt is True:
            console.print("[yellow]auth: --jwt requested but active provider has no JWT; using token[/yellow]")

    def _handle_rate_limit(self, resp: requests.Response):
        remaining = int(resp.headers.get("X-RateLimit-Remaining", 999))
        if remaining < 10:
            console.print(f"[yellow]⚠ Rate limit: {remaining} requests remaining[/yellow]", style="dim")
        if remaining == 0:
            reset_time = int(resp.headers.get("X-RateLimit-Reset", 0))
            wait = max(0, reset_time - int(time.time())) + 1
            console.print(f"[red]Rate limit hit. Waiting {wait}s...[/red]")
            time.sleep(wait)

    def request(self, method: str, path: str, force_jwt: Optional[bool] = None, **kwargs) -> requests.Response:
        """Make a single API request with retries.

        ``force_jwt`` overrides automatic token selection:
          * True  -> force the app JWT, * False -> force the installation token,
          * None  -> auto-detect from the endpoint path.
        """
        self._inject_auth(path, force_jwt=force_jwt)
        url = f"{GITHUB_API}{path}" if path.startswith("/") else path

        if self._debug:
            console.print(f"[dim]{method} {url}[/dim]")

        for attempt in range(MAX_RETRIES):
            resp = self._session.request(method, url, timeout=TIMEOUT, **kwargs)
            self._handle_rate_limit(resp)

            if resp.status_code < 500:
                resp.raise_for_status()
                return resp

            # Retry on 5xx
            backoff = 2**attempt
            if self._debug:
                console.print(f"[dim]Retry {attempt + 1}/{MAX_RETRIES} in {backoff}s[/dim]")
            time.sleep(backoff)

        resp.raise_for_status()
        return resp  # unreachable but satisfies type checker

    def get(self, path: str, **kwargs) -> Any:
        """GET request, return JSON."""
        return self.request("GET", path, **kwargs).json()

    def post(self, path: str, **kwargs) -> Any:
        """POST request, return JSON."""
        return self.request("POST", path, **kwargs).json()

    def patch(self, path: str, **kwargs) -> Any:
        """PATCH request, return JSON."""
        return self.request("PATCH", path, **kwargs).json()

    def put(self, path: str, **kwargs) -> Any:
        """PUT request, return JSON."""
        return self.request("PUT", path, **kwargs).json()

    def delete(self, path: str, **kwargs) -> int:
        """DELETE request, return status code."""
        return self.request("DELETE", path, **kwargs).status_code

    def paginate(self, path: str, force_jwt: Optional[bool] = None, **kwargs) -> Generator[Any, None, None]:
        """Auto-paginate a GET endpoint, yielding items."""
        self._inject_auth(path, force_jwt=force_jwt)
        url = f"{GITHUB_API}{path}" if path.startswith("/") else path
        params = kwargs.pop("params", {})
        params.setdefault("per_page", 100)

        while url:
            resp = self.request("GET", url, force_jwt=force_jwt, params=params, **kwargs)
            data = resp.json()
            if isinstance(data, list):
                yield from data
            else:
                yield data

            # Follow Link header for next page
            url = self._next_link(resp)
            params = {}  # params are embedded in the next URL

    def _next_link(self, resp: requests.Response) -> Optional[str]:
        link_header = resp.headers.get("Link", "")
        for part in link_header.split(","):
            if 'rel="next"' in part:
                return part.split(";")[0].strip().strip("<>")
        return None

    def graphql(self, query: str, variables: Optional[dict] = None) -> Any:
        """Execute a GraphQL query."""
        payload = {"query": query}
        if variables:
            payload["variables"] = variables
        return self.post("/graphql", json=payload)
