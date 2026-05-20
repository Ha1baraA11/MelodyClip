"""
main.py — PySide6 application entry point

Responsibilities:
1. Set FFmpeg environment variables (pointing to the bundled ffmpeg.exe)
2. Clean up leftover temporary files on startup
3. Load configuration
4. Launch QApplication + MainWindow
"""

import os
import sys
from pathlib import Path


def _setup_ffmpeg():
    """Set FFmpeg/FFprobe environment variables. Prefer bundled version, then fall back to imageio_ffmpeg."""
    from utils.file_utils import get_resource_path

    ffmpeg_exe = get_resource_path("ffmpeg/ffmpeg.exe")
    if not Path(ffmpeg_exe).exists():
        try:
            import imageio_ffmpeg
            ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
        except (ImportError, FileNotFoundError):
            ffmpeg_exe = ""

    if ffmpeg_exe and Path(ffmpeg_exe).exists():
        os.environ["IMAGEIO_FFMPEG_EXE"] = ffmpeg_exe
        os.environ["FFMPEG_BINARY"] = ffmpeg_exe
        # Add ffmpeg directory to PATH so pydub's which() can find it
        ffmpeg_dir = str(Path(ffmpeg_exe).parent)
        if ffmpeg_dir not in os.environ.get("PATH", ""):
            os.environ["PATH"] = ffmpeg_dir + os.pathsep + os.environ.get("PATH", "")

    # Ensure pydub can find ffprobe (fall back to ffmpeg if not found)
    from core.audio_builder import _setup_ffprobe
    _setup_ffprobe()


def _suppress_console_windows():
    """Globally hide subprocess console windows on Windows."""
    if sys.platform != "win32":
        return
    import subprocess
    _orig_popen = subprocess.Popen

    class _NoWindowPopen(_orig_popen):
        def __init__(self, *args, **kwargs):
            kwargs.setdefault("creationflags", subprocess.CREATE_NO_WINDOW)
            kwargs.setdefault("startupinfo", _startupinfo())
            super().__init__(*args, **kwargs)

    def _startupinfo():
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        return si

    subprocess.Popen = _NoWindowPopen


def main():
    # ── 0. Suppress Windows console windows ────────────────────────────────────
    _suppress_console_windows()

    # ── 1. Configure FFmpeg ─────────────────────────────────────────────────────
    _setup_ffmpeg()

    # ── 2. Clean up leftover temporary files from previous run ───────────────────
    from utils.file_utils import cleanup_all_temp
    cleanup_all_temp()

    # ── 3. Load configuration ────────────────────────────────────────────────────
    from utils.config_manager import config
    config.load()

    # ── 4. Launch GUI ────────────────────────────────────────────────────────────
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import Qt
    from gui.app import MainWindow

    app = QApplication(sys.argv)
    app.setApplicationName("SongShareTool")
    app.setApplicationDisplayName("Song Share Video Generator")

    # Show the window first, then load time-consuming resources (so users don't see a blank screen)
    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
