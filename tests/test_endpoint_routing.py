"""Tests for app-level endpoint detection (JWT vs installation token routing)."""

import pytest

from supergh.api.client import _endpoint_needs_jwt


@pytest.mark.parametrize(
    "path",
    [
        "/app",
        "/app/",
        "/app/installations",
        "/app/installations/123",
        "/app/installations/123/access_tokens",
        "/app/hook/config",
        "/orgs/my-org/installation",
        "/users/some-user/installation",
        "/repos/owner/repo/installation",
        "/marketplace_listing/plans",
        "/app-manifests/abc123/conversions",
        # full URL form + query string must still match
        "https://api.github.com/app/installations?per_page=100",
        "app/installations",  # missing leading slash
    ],
)
def test_app_level_endpoints_need_jwt(path):
    assert _endpoint_needs_jwt(path) is True


@pytest.mark.parametrize(
    "path",
    [
        "/repos/owner/repo",
        "/repos/owner/repo/issues",
        "/repos/owner/repo/pulls/1",
        "/orgs/my-org",
        "/orgs/my-org/repos",
        "/orgs/my-org/members",
        "/user",
        "/users/some-user",
        "/installation/repositories",  # uses installation token, not JWT
        "/rate_limit",
        "/search/repositories?q=test",
        "",
        None,
    ],
)
def test_non_app_endpoints_do_not_need_jwt(path):
    assert _endpoint_needs_jwt(path) is False


def test_installation_repositories_is_not_jwt():
    # Easy to confuse with /app routes, but this one uses the installation token.
    assert _endpoint_needs_jwt("/installation/repositories") is False


def test_app_prefix_does_not_overmatch():
    # A repo literally named "app" under an org must NOT be treated as app-level.
    assert _endpoint_needs_jwt("/repos/owner/app") is False
    assert _endpoint_needs_jwt("/orgs/app") is False
