"""Setup script — auto-detects OS, adds sgh to PATH. Run once: python setup_path.py"""

import os
import platform
import subprocess
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent


def setup_windows():
    """Add project dir to User PATH on Windows."""
    result = subprocess.run(
        ["reg", "query", "HKCU\\Environment", "/v", "Path"],
        capture_output=True, text=True
    )
    current_path = ""
    if result.returncode == 0:
        for line in result.stdout.splitlines():
            if "Path" in line or "PATH" in line:
                current_path = line.split("REG_EXPAND_SZ")[-1].strip().split("REG_SZ")[-1].strip()

    project_str = str(PROJECT_DIR)
    if project_str.lower() in current_path.lower():
        print(f"[OK] Already in PATH: {project_str}")
        return

    new_path = f"{current_path};{project_str}" if current_path else project_str
    subprocess.run(
        ["setx", "Path", new_path],
        capture_output=True, text=True
    )
    print(f"[OK] Added to User PATH: {project_str}")
    print("  Restart your terminal for changes to take effect.")


def setup_unix():
    """Add project dir to PATH via shell rc file on Linux/Mac."""
    project_str = str(PROJECT_DIR)
    sgh_script = PROJECT_DIR / "sgh"

    # Make sgh executable
    sgh_script.chmod(0o755)

    # Detect shell rc file
    shell = os.environ.get("SHELL", "/bin/bash")
    if "zsh" in shell:
        rc_file = Path.home() / ".zshrc"
    elif "fish" in shell:
        rc_file = Path.home() / ".config" / "fish" / "config.fish"
    else:
        rc_file = Path.home() / ".bashrc"

    # Check if already added
    export_line = f'export PATH="$PATH:{project_str}"'
    if "fish" in shell:
        export_line = f'set -gx PATH $PATH {project_str}'

    if rc_file.exists():
        content = rc_file.read_text()
        if project_str in content:
            print(f"[OK] Already in PATH ({rc_file.name}): {project_str}")
            return

    with open(rc_file, "a") as f:
        f.write(f"\n# supergh (sgh) CLI\n{export_line}\n")

    print(f"[OK] Added to {rc_file}: {export_line}")
    print(f"  Run: source {rc_file}  (or restart your terminal)")


def main():
    system = platform.system()
    print(f"Detected OS: {system}")
    print(f"Project dir: {PROJECT_DIR}\n")

    if system == "Windows":
        setup_windows()
    elif system in ("Linux", "Darwin"):
        setup_unix()
    else:
        print(f"[FAIL] Unsupported OS: {system}")
        print(f"  Manually add this to your PATH: {PROJECT_DIR}")
        sys.exit(1)

    print("\nDone! After restarting your terminal, just type: sgh --help")


if __name__ == "__main__":
    main()
