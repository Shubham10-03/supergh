"""Auth middleware — resolves the correct auth provider from config."""

from __future__ import annotations

from supergh.auth.base import AuthProvider
from supergh.config import get_config


def get_auth_provider() -> AuthProvider:
    """Return the appropriate auth provider based on active profile config."""
    cfg = get_config()
    auth_type = cfg.auth_type

    if auth_type == "app":
        from supergh.auth.app_auth import GitHubAppAuth

        profile = cfg.active_profile
        app_id = profile.get("app_id", "")
        pem_path = profile.get("pem_path", "")
        org = cfg.org
        if not app_id or not pem_path:
            raise RuntimeError("GitHub App auth requires app_id and pem_path in config.")
        return GitHubAppAuth(app_id=app_id, pem_path=pem_path, org=org)

    else:
        from supergh.auth.oauth import GitHubOAuthAuth

        return GitHubOAuthAuth(org=cfg.org)
