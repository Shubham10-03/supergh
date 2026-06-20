"""supergh — a superset GitHub CLI for enterprise workflows."""

from pathlib import Path

_version_file = Path(__file__).resolve().parent.parent / "VERSION"
if _version_file.exists():
    __version__ = _version_file.read_text().strip()
else:
    __version__ = "1.0.0"
