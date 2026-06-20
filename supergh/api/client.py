"""Base GitHub API client — pagination, rate limiting, retries, auth injection."""

from __future__ import annotations

import time
from typing import Any, Generator, Optional
from urllib.parse import parse_qs, urlparse

import requests
from rich.console import Console

from supergh.auth.middleware import get_auth_provider

console = Console()
GITHUB_API = "https://api.github.com"
MAX_RETRIES = 3
TIMEOUT = 30


class GitHubClient:
    """GitHub REST (and GraphQL) client with automatic auth, pagination, and rate limiting."""

    def __init__(self, debug: bool = False):
        self._debug = debug
        self._session = requests.Session()
        self._session.headers.update({"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"})

    def _inject_auth(self):
        provider = get_auth_provider()
        token = provider.get_token()
        # Use 'token' prefix — works for all token types (PAT, OAuth, fine-grained)
        self._session.headers["Authorization"] = f"token {token}"

    def _handle_rate_limit(self, resp: requests.Response):
        remaining = int(resp.headers.get("X-RateLimit-Remaining", 999))
        if remaining < 10:
            console.print(f"[yellow]⚠ Rate limit: {remaining} requests remaining[/yellow]", style="dim")
        if remaining == 0:
            reset_time = int(resp.headers.get("X-RateLimit-Reset", 0))
            wait = max(0, reset_time - int(time.time())) + 1
            console.print(f"[red]Rate limit hit. Waiting {wait}s...[/red]")
            time.sleep(wait)

    def request(self, method: str, path: str, **kwargs) -> requests.Response:
        """Make a single API request with retries."""
        self._inject_auth()
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

    def paginate(self, path: str, **kwargs) -> Generator[Any, None, None]:
        """Auto-paginate a GET endpoint, yielding items."""
        self._inject_auth()
        url = f"{GITHUB_API}{path}" if path.startswith("/") else path
        params = kwargs.pop("params", {})
        params.setdefault("per_page", 100)

        while url:
            resp = self.request("GET", url, params=params, **kwargs)
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
