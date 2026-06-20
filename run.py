"""Run sgh directly: python run.py [args]"""

import os
import sys
from pathlib import Path

# Fix Windows encoding for unicode output
if sys.platform == "win32":
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Bootstrap vendor deps
vendor_dir = Path(__file__).resolve().parent / "vendor"
if vendor_dir.exists():
    sys.path.insert(0, str(vendor_dir))

import click

from supergh.cli import main
from supergh.utils.errors import handle_error

if __name__ == "__main__":
    try:
        # Check for --debug anywhere in args (click requires it before subcommand)
        debug = "--debug" in sys.argv
        if debug:
            sys.argv.remove("--debug")
            sys.argv.insert(1, "--debug")  # move to correct position

        main(prog_name="sgh", standalone_mode=False)
    except SystemExit as e:
        sys.exit(e.code if e.code else 0)
    except click.exceptions.ClickException as e:
        e.show()
        sys.exit(1)
    except Exception as e:
        handle_error(e, debug="--debug" in sys.argv)
        sys.exit(1)
