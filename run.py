"""
run.py — Startup entry point: check dependencies -> launch GUI

Automatically installs missing Python dependencies on first run,
no manual pip install required.
"""

import subprocess
import sys
import importlib

# Module name -> pip package name mapping
REQUIRED_PACKAGES: dict[str, str] = {
    "moviepy": "moviepy>=2.0.0",
    "PySide6": "PySide6>=6.7.0",
    "pydub": "pydub>=0.25.0",
    "PIL": "Pillow>=10.0.0",
}

if sys.version_info >= (3, 13):
    REQUIRED_PACKAGES["audioop"] = "audioop-lts"


def check_and_install():
    missing: list[str] = []
    for module, package in REQUIRED_PACKAGES.items():
        try:
            importlib.import_module(module)
        except ImportError:
            missing.append(package)

    if missing:
        print(f"[Info] Installing missing dependencies: {', '.join(missing)}")
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", *missing, "-q"]
        )
        print("[Info] Dependencies installed. Launching application...")


if __name__ == "__main__":
    check_and_install()
    from main import main
    main()
