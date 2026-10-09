"""GitHub App registry.

Manages a secure, local registry of GitHub Apps under ``~/.supergh/apps/``:

  * PEM private keys are *copied* into the apps directory on first registration
    (dir ``0700``, key files ``0600``) so the app always has them.
  * A JSON manifest (``registry.json``) maps a friendly app *name* to its
    ``pem_file`` (basename inside the apps dir), ``app_id`` and ``org``.
    The manifest contains **no secrets** — only names, app IDs and org slugs.

This lets supergh always know which apps are available without re-prompting for
the App ID / PEM path on every login.
"""

from __future__ import annotations

import json
import os
import shutil
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, Optional

CONFIG_DIR = Path.home() / ".supergh"
APPS_DIR = CONFIG_DIR / "apps"
REGISTRY_FILE = APPS_DIR / "registry.json"

# Permission constants
_DIR_MODE = 0o700
_FILE_MODE = 0o600


@dataclass
class AppEntry:
    """A single registered GitHub App (no secrets)."""

    name: str
    app_id: str
    pem_file: str          # basename of the PEM inside APPS_DIR
    org: str = ""

    def to_dict(self) -> dict:
        d = asdict(self)
        d.pop("name", None)  # name is the registry key, not stored in the value
        return d


class AppRegistry:
    """CRUD for the on-disk GitHub App registry."""

    def __init__(self, apps_dir: Optional[Path] = None):
        self.apps_dir = Path(apps_dir) if apps_dir else APPS_DIR
        self.registry_file = self.apps_dir / "registry.json"
        self._ensure_dir()

    # --- directory / file helpers ---

    def _ensure_dir(self) -> None:
        self.apps_dir.mkdir(parents=True, exist_ok=True)
        try:
            os.chmod(self.apps_dir, _DIR_MODE)
        except OSError:
            # Best-effort on platforms without POSIX perms (e.g. Windows).
            pass

    def _load(self) -> dict:
        if not self.registry_file.exists():
            return {"apps": {}}
        try:
            data = json.loads(self.registry_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {"apps": {}}
        if "apps" not in data or not isinstance(data["apps"], dict):
            data["apps"] = {}
        return data

    def _save(self, data: dict) -> None:
        self._ensure_dir()
        self.registry_file.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        try:
            os.chmod(self.registry_file, _FILE_MODE)
        except OSError:
            pass

    def pem_path(self, entry: AppEntry) -> Path:
        """Absolute path to the copied PEM for an entry."""
        return self.apps_dir / entry.pem_file

    # --- queries ---

    def list_apps(self) -> Dict[str, AppEntry]:
        data = self._load()
        out: Dict[str, AppEntry] = {}
        for name, val in data["apps"].items():
            out[name] = AppEntry(
                name=name,
                app_id=str(val.get("app_id", "")),
                pem_file=val.get("pem_file", ""),
                org=val.get("org", ""),
            )
        return out

    def get(self, name: str) -> Optional[AppEntry]:
        return self.list_apps().get(name)

    def exists(self, name: str) -> bool:
        return name in self._load()["apps"]

    def pem_present(self, entry: AppEntry) -> bool:
        return self.pem_path(entry).is_file()

    # --- mutations ---

    def register(
        self,
        name: str,
        app_id: str,
        pem_source: str | os.PathLike,
        org: str = "",
        overwrite: bool = False,
    ) -> AppEntry:
        """Register an app, copying its PEM into the apps dir.

        ``pem_source`` is the user-supplied path given on first registration.
        It is copied to ``APPS_DIR/<name>.pem`` with ``0600`` perms. If the
        source already lives inside the apps dir, it is reused in place.
        """
        if not name:
            raise ValueError("App name is required.")
        if self.exists(name) and not overwrite:
            raise ValueError(f"App '{name}' is already registered. Use overwrite=True to replace.")

        src = Path(pem_source).expanduser()
        if not src.is_file():
            raise FileNotFoundError(f"PEM file not found: {src}")

        self._ensure_dir()
        dest = self.apps_dir / f"{name}.pem"

        # Copy in unless the source is already the destination.
        if src.resolve() != dest.resolve():
            shutil.copyfile(src, dest)
        try:
            os.chmod(dest, _FILE_MODE)
        except OSError:
            pass

        entry = AppEntry(name=name, app_id=str(app_id), pem_file=dest.name, org=org)
        data = self._load()
        data["apps"][name] = entry.to_dict()
        self._save(data)
        return entry

    def set_org(self, name: str, org: str) -> None:
        data = self._load()
        if name in data["apps"]:
            data["apps"][name]["org"] = org
            self._save(data)

    def remove(self, name: str, delete_pem: bool = True) -> bool:
        """Remove an app from the registry. Optionally delete its PEM file."""
        data = self._load()
        entry_val = data["apps"].pop(name, None)
        if entry_val is None:
            return False
        self._save(data)
        if delete_pem:
            pem_file = entry_val.get("pem_file", "")
            if pem_file:
                p = self.apps_dir / pem_file
                try:
                    if p.is_file():
                        p.unlink()
                except OSError:
                    pass
        return True


# Module-level singleton
_registry: Optional[AppRegistry] = None


def get_registry() -> AppRegistry:
    global _registry
    if _registry is None:
        _registry = AppRegistry()
    return _registry
