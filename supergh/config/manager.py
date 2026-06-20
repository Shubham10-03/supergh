"""Config manager — handles ~/.supergh/config.toml and profiles."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Optional

import toml

CONFIG_DIR = Path.home() / ".supergh"
CONFIG_FILE = CONFIG_DIR / "config.toml"
PROFILES_DIR = CONFIG_DIR / "profiles"
CACHE_DIR = CONFIG_DIR / "cache"

DEFAULT_CONFIG = {
    "core": {
        "default_profile": "default",
        "default_org": "",
        "output_format": "table",
        "pager": True,
        "color": True,
    },
    "profiles": {
        "default": {
            "auth_type": "oauth",
            "org": "",
            "app_id": "",
            "pem_path": "",
        }
    },
    "cache": {
        "enabled": True,
        "ttl_seconds": 300,
    },
}


class ConfigManager:
    """Manages reading and writing of supergh configuration."""

    def __init__(self, config_path: Optional[Path] = None):
        self.config_path = config_path or CONFIG_FILE
        self._data: dict = {}
        self._ensure_dirs()
        self._load()

    def _ensure_dirs(self):
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        PROFILES_DIR.mkdir(parents=True, exist_ok=True)
        CACHE_DIR.mkdir(parents=True, exist_ok=True)

    def _load(self):
        if self.config_path.exists():
            self._data = toml.loads(self.config_path.read_text(encoding="utf-8"))
        else:
            self._data = DEFAULT_CONFIG.copy()
            self._save()

    def _save(self):
        self.config_path.write_text(toml.dumps(self._data), encoding="utf-8")

    def get(self, key: str, default: Any = None) -> Any:
        """Get a config value using dotted key notation (e.g. 'core.default_org')."""
        parts = key.split(".")
        node = self._data
        for part in parts:
            if isinstance(node, dict) and part in node:
                node = node[part]
            else:
                return default
        return node

    def set(self, key: str, value: Any):
        """Set a config value using dotted key notation."""
        parts = key.split(".")
        node = self._data
        for part in parts[:-1]:
            node = node.setdefault(part, {})
        node[parts[-1]] = value
        self._save()

    def list_all(self) -> dict:
        """Return the full config dict."""
        return self._data

    @property
    def active_profile_name(self) -> str:
        return self.get("core.default_profile", "default")

    @property
    def active_profile(self) -> dict:
        return self.get(f"profiles.{self.active_profile_name}", {})

    @property
    def org(self) -> str:
        """Resolve org: app installation org > profile org > default org."""
        # If using app auth, check for installed org from API
        if self.auth_type == "app":
            from supergh.auth.store import TokenStore
            app_id = self.active_profile.get("app_id", "")
            config_org = self.active_profile.get("org", "") or self.get("core.default_org", "")
            if app_id:
                store = TokenStore(namespace=f"app_{app_id}_{config_org}")
                installed_org = store.get_token("installed_org")
                if installed_org:
                    return installed_org
        return self.active_profile.get("org", "") or self.get("core.default_org", "")

    @property
    def auth_type(self) -> str:
        return self.active_profile.get("auth_type", "oauth")

    @property
    def output_format(self) -> str:
        return self.get("core.output_format", "table")


# Module-level singleton
_config: Optional[ConfigManager] = None


def get_config() -> ConfigManager:
    """Get or create the global ConfigManager instance."""
    global _config
    if _config is None:
        _config = ConfigManager()
    return _config
