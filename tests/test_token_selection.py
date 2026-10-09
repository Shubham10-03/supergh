"""Tests for GitHubClient token selection (JWT vs installation token)."""

from unittest.mock import patch

import pytest

from supergh.api import client as client_mod
from supergh.api.client import GitHubClient


class FakeAppProvider:
    """Mimics GitHubAppAuth: has both get_jwt and get_token."""

    def get_jwt(self, force_refresh: bool = False) -> str:
        return "JWT_TOKEN"

    def get_token(self, force_refresh: bool = False) -> str:
        return "INSTALL_TOKEN"


class FakePATProvider:
    """Mimics a PAT/OAuth provider: only get_token, no JWT."""

    def get_token(self, force_refresh: bool = False) -> str:
        return "PAT_TOKEN"


def _auth_header(provider, path, force_jwt=None):
    c = GitHubClient()
    with patch.object(client_mod, "get_auth_provider", return_value=provider):
        c._inject_auth(path, force_jwt=force_jwt)
    return c._session.headers["Authorization"]


# --- App provider: auto-detection ---

def test_app_provider_uses_jwt_for_app_endpoint():
    assert _auth_header(FakeAppProvider(), "/app/installations") == "Bearer JWT_TOKEN"


def test_app_provider_uses_install_token_for_repo_endpoint():
    assert _auth_header(FakeAppProvider(), "/repos/o/r/issues") == "token INSTALL_TOKEN"


# --- Manual overrides ---

def test_force_jwt_true_on_non_app_endpoint():
    assert _auth_header(FakeAppProvider(), "/repos/o/r", force_jwt=True) == "Bearer JWT_TOKEN"


def test_force_jwt_false_on_app_endpoint():
    # Explicit --no-jwt must override auto-detection even for app routes.
    assert _auth_header(FakeAppProvider(), "/app", force_jwt=False) == "token INSTALL_TOKEN"


# --- Non-JWT providers fall back gracefully ---

def test_pat_provider_never_uses_jwt_even_on_app_endpoint():
    assert _auth_header(FakePATProvider(), "/app/installations") == "token PAT_TOKEN"


def test_pat_provider_force_jwt_falls_back_to_token():
    # --jwt requested but provider has no JWT -> must still produce a usable token.
    assert _auth_header(FakePATProvider(), "/repos/o/r", force_jwt=True) == "token PAT_TOKEN"
