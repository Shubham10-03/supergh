"""Tests for GitHubAppAuth.get_jwt caching."""

from unittest.mock import patch

from supergh.auth.app_auth import GitHubAppAuth


def _make_auth():
    # TokenStore is constructed in __init__ but not touched by get_jwt, so this
    # is safe without keyring access.
    return GitHubAppAuth(app_id="123", pem_path="/nonexistent.pem", org="my-org")


def test_get_jwt_signs_and_caches():
    auth = _make_auth()
    with patch.object(auth, "_create_jwt", return_value="SIGNED") as m:
        first = auth.get_jwt()
        second = auth.get_jwt()
    assert first == "SIGNED"
    assert second == "SIGNED"
    # Cached: _create_jwt called only once across two get_jwt() calls.
    assert m.call_count == 1


def test_get_jwt_force_refresh_resigns():
    auth = _make_auth()
    with patch.object(auth, "_create_jwt", side_effect=["A", "B"]) as m:
        first = auth.get_jwt()
        second = auth.get_jwt(force_refresh=True)
    assert first == "A"
    assert second == "B"
    assert m.call_count == 2


def test_get_jwt_resigns_when_cache_expired():
    import datetime as dt

    auth = _make_auth()
    with patch.object(auth, "_create_jwt", side_effect=["A", "B"]) as m:
        first = auth.get_jwt()
        # Force the cached JWT to look expired.
        auth._cached_jwt_expiry = dt.datetime.utcnow() - dt.timedelta(minutes=1)
        second = auth.get_jwt()
    assert first == "A"
    assert second == "B"
    assert m.call_count == 2
