"""Build script — generates standalone sgh binary using PyInstaller."""

import subprocess
import sys
import platform
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent


def build():
    suffix = ".exe" if platform.system() == "Windows" else ""
    binary_name = f"sgh{suffix}"

    print(f"Building {binary_name} for {platform.system()} {platform.machine()}...")
    print(f"Project: {PROJECT_DIR}\n")

    try:
        import PyInstaller
    except ImportError:
        print("PyInstaller not found. Installing...")
        subprocess.run([sys.executable, "-m", "pip", "install", "pyinstaller"], check=True)

    spec_file = PROJECT_DIR / "sgh.spec"
    subprocess.run(
        [sys.executable, "-m", "PyInstaller", str(spec_file), "--clean", "--noconfirm"],
        cwd=str(PROJECT_DIR),
        check=True,
    )

    exe_path = PROJECT_DIR / "dist" / binary_name
    if exe_path.exists():
        size_mb = exe_path.stat().st_size / 1024 / 1024
        print(f"\n[OK] Built: {exe_path}")
        print(f"     Size: {size_mb:.1f} MB")
        print(f"     Platform: {platform.system()} {platform.machine()}")
    else:
        print("\n[FAIL] Build failed. Check output above.")
        sys.exit(1)


if __name__ == "__main__":
    build()
