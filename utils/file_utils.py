"""
file_utils.py — File path safe handling utilities

Includes:
- get_resource_path()   PyInstaller-compatible resource path
- safe_path()           Convert non-ASCII paths to ASCII temp paths
- cleanup_temp()        Clean up a single temp file
- cleanup_all_temp()    Clean up all leftover temp files on startup
- safe_move()           Cross-drive safe file move
"""

import os
import sys
import shutil
import tempfile
import uuid
from pathlib import Path


# ─── Temp directory identifier ─────────────────────────────────────────────────
_TEMP_SUBDIR = "SongShareTool"


def get_temp_dir() -> Path:
    """Return the dedicated temp directory for this tool (auto-created)."""
    temp_dir = Path(tempfile.gettempdir()) / _TEMP_SUBDIR
    temp_dir.mkdir(exist_ok=True)
    return temp_dir


# ─── PyInstaller-compatible path ────────────────────────────────────────────────

def get_resource_path(relative_path: str) -> str:
    """
    Get absolute path that works regardless of packaging.

    - Development: relative to project root
    - PyInstaller packaged: relative to sys._MEIPASS temp extraction directory
    """
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        base_path = Path(sys._MEIPASS)
    else:
        # Parent of utils/ is the project root
        base_path = Path(__file__).resolve().parent.parent
    return str(base_path / relative_path)


# ─── Non-ASCII path safe handling ───────────────────────────────────────────────

def safe_path(original_path: str) -> tuple[str, bool]:
    """
    Convert paths with non-ASCII/special characters to pure ASCII temp paths.

    Returns:
        (safe_path_str, is_temp)
        - is_temp=False means the original path is ASCII, use directly
        - is_temp=True  means it was copied to temp directory, call cleanup_temp() when done
    """
    p = Path(original_path)

    # Check if pure ASCII
    try:
        original_path.encode("ascii")
        return original_path, False
    except UnicodeEncodeError:
        pass  # Contains non-ASCII characters, needs conversion

    # Use UUID naming, preserve original extension
    temp_name = f"{uuid.uuid4().hex[:12]}{p.suffix}"
    temp_path = get_temp_dir() / temp_name
    shutil.copy2(original_path, temp_path)
    return str(temp_path), True


def cleanup_temp(temp_path: str) -> None:
    """Clean up a single temp file (ignores non-existent files)."""
    try:
        Path(temp_path).unlink(missing_ok=True)
    except OSError:
        pass


def cleanup_all_temp() -> None:
    """
    Clean up all files in the dedicated temp directory.
    Should be called on startup to clean up leftovers from previous abnormal exits.
    """
    temp_dir = Path(tempfile.gettempdir()) / _TEMP_SUBDIR
    if not temp_dir.exists():
        return
    for f in temp_dir.glob("*"):
        try:
            if f.is_file():
                f.unlink()
        except OSError:
            pass


# ─── Cross-drive safe move ─────────────────────────────────────────────────────

def safe_move(src: str, dst: str) -> None:
    """
    Cross-drive safe file move.

    shutil.move() on Windows across drives (e.g. C: -> D:) raises
    OSError: [Errno 18] Invalid cross-device link.
    This function tries move first, falls back to copy2 + remove.
    """
    try:
        shutil.move(src, dst)
    except OSError:
        shutil.copy2(src, dst)
        os.remove(src)
