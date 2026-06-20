"""Entry point that bootstraps vendor/ dependencies before running the CLI."""

import sys
from pathlib import Path

# Prepend vendor/ to sys.path so bundled deps are found first
_vendor_dir = Path(__file__).resolve().parent.parent / "vendor"
if _vendor_dir.exists():
    sys.path.insert(0, str(_vendor_dir))

from supergh.cli import main  # noqa: E402

if __name__ == "__main__":
    main()
