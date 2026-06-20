"""Permission resolution and caching.

Permissions are resolved once at auth time and stored in keychain.
UI and CLI read from this cache — zero extra API calls at runtime.
On logout, permissions are cleared automatically.
"""

from __future__ import annotations

import json
from typing import Optional

from supergh.auth.store import TokenStore
from supergh.config import get_config


# Standard permission set
DEFAULT_PERMS = {
    "repos": {"read": False, "write": False},
    "issues": {"read": False, "write": False},
    "pulls": {"read": False, "write": False},
    "actions": {"read": False, "write": False},
    "secrets": {"read": False, "write": False},
    "teams": {"read": False, "write": False},
    "members": {"read": False, "write": False},
}


def resolve_permissions_from_app_install(install_permissions: dict) -> dict:
    """Map GitHub App installation permissions to our permission model.

    GitHub returns: {"contents": "write", "issues": "read", ...}
    We map to: {"repos": {"read": True, "write": True}, ...}
    """
    perms = _empty_perms()

    gh_to_scope = {
        "contents": "repos",
        "issues": "issues",
        "pull_requests": "pulls",
        "actions": "actions",
        "secrets": "secrets",
        "organization_administration": "teams",
        "members": "members",
    }

    for gh_perm, level in install_permissions.items():
        scope = gh_to_scope.get(gh_perm)
        if scope and scope in perms:
            perms[scope]["read"] = True
            if level == "write" or level == "admin":
                perms[scope]["write"] = True

    return perms


def resolve_permissions_from_scopes(scopes_header: str) -> dict:
    """Map PAT/OAuth scopes to our permission model.

    GitHub returns X-OAuth-Scopes: "repo, read:org, admin:org"
    """
    perms = _empty_perms()
    scopes = [s.strip() for s in scopes_header.split(",") if s.strip()]

    if "repo" in scopes:
        perms["repos"] = {"read": True, "write": True}
        perms["issues"] = {"read": True, "write": True}
        perms["pulls"] = {"read": True, "write": True}
        perms["actions"] = {"read": True, "write": True}
        perms["secrets"] = {"read": True, "write": True}

    if "public_repo" in scopes and not perms["repos"]["read"]:
        perms["repos"] = {"read": True, "write": True}
        perms["issues"] = {"read": True, "write": True}
        perms["pulls"] = {"read": True, "write": True}

    if "read:org" in scopes or "admin:org" in scopes:
        perms["teams"] = {"read": True, "write": "admin:org" in scopes}
        perms["members"] = {"read": True, "write": "admin:org" in scopes}

    if "admin:org" in scopes:
        perms["teams"]["write"] = True
        perms["members"]["write"] = True

    return perms


def store_permissions(perms: dict, namespace: str = None):
    """Store resolved permissions in keychain."""
    ns = namespace or _active_namespace()
    store = TokenStore(namespace=ns)
    store.set_token("permissions", json.dumps(perms))


def get_cached_permissions() -> Optional[dict]:
    """Read permissions from keychain. Returns None if not cached."""
    ns = _active_namespace()
    store = TokenStore(namespace=ns)
    raw = store.get_token("permissions")
    if raw:
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return None
    return None


def clear_permissions():
    """Remove cached permissions."""
    ns = _active_namespace()
    store = TokenStore(namespace=ns)
    store.delete("permissions")


def _active_namespace() -> str:
    """Determine the keychain namespace for the active auth."""
    cfg = get_config()
    if cfg.auth_type == "app":
        profile = cfg.active_profile
        app_id = profile.get("app_id", "")
        org = cfg.org
        return f"app_{app_id}_{org}"
    return "oauth"


def _empty_perms() -> dict:
    return {k: {"read": False, "write": False} for k in DEFAULT_PERMS}
