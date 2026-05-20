"""
config_manager.py — JSON configuration read/write manager

Config file is stored in the application directory as config.json (same level as exe).
Uses defaults on first run, auto-fills missing fields, backward compatible.
"""

import json
from pathlib import Path
from typing import Any

# ─── Default config (16:9 landscape) ──────────────────────────────────────────
DEFAULTS: dict[str, Any] = {
    # Audio settings
    "intro_audio": "",          # Intro audio path (empty = use built-in 开头.mp3)
    "guide_audio": "",          # Guide audio path (empty = no guide)
    "enable_guide": True,       # Enable guide voice
    "enable_guide_subtitles": True,  # Enable guide subtitles
    "outro_audio": "",          # Outro audio path
    "enable_intro": True,       # Enable intro voice
    "enable_outro": True,       # Enable outro voice
    "enable_intro_subtitles": True,   # Enable intro subtitles
    "enable_outro_subtitles": True,   # Enable outro subtitles
    "bottom_center_text": "Lyrics for appreciation only",  # Bottom center disclaimer
    "silence_gap": 0.3,         # Silence gap between segments (seconds)
    "fadeout_duration": 1.5,    # Song fadeout duration (seconds)

    # Subtitle timeline templates {audio filename: [subtitle list]}
    "timeline_templates": {
        "开头(含橱窗引导).mp3": [
            {"time": 0.5, "text": "This song is really amazing"},
            {"time": 2.3, "text": "I love it so much"},
            {"time": 3.8, "text": "Instantly brings back years of memories"},
            {"time": 5.8, "text": "Sharing it with you today"},
            {"time": 7.3, "text": "Whether you've heard it or not, stop and listen"},
            {"time": 9.5, "text": "While listening, check out my profile shop"},
            {"time": 11.3, "text": "There are great items to share"},
        ],
        "开头(不含橱窗引导).mp3": [
            {"time": 0.5, "text": "This song is really amazing"},
            {"time": 1.8, "text": "I love it so much"},
            {"time": 3.2, "text": "Instantly brings back years of memories"},
            {"time": 6.0, "text": "Sharing it with you today"},
            {"time": 7.5, "text": "Whether you've heard it or not, stop and listen"},
        ],
        "结尾(含橱窗引导).mp3": [
            {"time": 0.5, "text": "If you like the song"},
            {"time": 2.3, "text": "Give it a heart"},
            {"time": 3.8, "text": "Click my profile to visit the shop"},
            {"time": 5.8, "text": "There are helpful items to share"},
        ],
        "引导语.mp3": [
            {"time": 0.5, "text": "While listening to music"},
            {"time": 1.8, "text": "You can also browse my profile shop"},
            {"time": 3.0, "text": "There are great items to share"},
        ],
    },

    # Audio trimming
    "trim_mode": "fixed",       # fixed / slice / manual
    "trim_duration": 45,        # Fixed duration (seconds)
    "slice_interval": 45,       # Interval slicing (seconds)
    "manual_start": 0,          # Manual start time (seconds)
    "manual_duration": 45,      # Manual trim duration (seconds)

    # Background video
    "background_mode": "fixed",         # fixed / folder
    "background_file": "",              # Fixed background video path
    "background_folder": "",            # Asset folder path
    "background_select_strategy": "sequential",  # sequential / random

    # Output settings
    "output_folder": "",  # Empty = auto-set to ~/Downloads/SongShareTool/ on startup
    "output_filename_template": "MelodyClip_{song_name}",
    "output_resolution": [1080, 1920],  # 9:16 portrait (mobile/TikTok)
    "fps": 30,
    "bitrate": "4000k",

    # Text style — Top banner
    "top_text_template": "Song Share",
    "top_text_size": 72,
    "top_text_font": "msyh.ttc",
    "top_text_bold": True,
    "top_text_color": "#000000",            # Black text
    "top_text_stroke_color": "#000000",
    "top_text_stroke_width": 0,
    "top_text_bg_color": "#FFD700",          # Yellow background

    # Text style — Bottom disclaimer
    "bottom_text": "Songs for sharing, no harmful intent",
    "bottom_text_size": 36,
    "bottom_text_font": "msyh.ttc",
    "bottom_text_bold": False,
    "bottom_text_color": "#FFFFFF",
    "bottom_text_stroke_color": "#000000",
    "bottom_text_stroke_width": 2,

    # Text style — Subtitles
    "subtitle_size": 80,
    "subtitle_font": "msyh.ttc",
    "subtitle_bold": True,
    "subtitle_color": "#FFD700",            # Yellow bold
    "subtitle_stroke_color": "#000000",
    "subtitle_stroke_width": 3,
    "slide_in_duration": 0.3,
    "max_subtitle_lines": 3,

    # Default subtitles (fallback when timeline_templates has no match)
    "default_subtitles": [],
}


def _get_default_output_folder() -> str:
    """Default output folder: output/ in the application directory"""
    import sys
    if getattr(sys, "frozen", False):
        # Packaged: exe directory
        base = Path(sys.executable).parent
    else:
        # Development: project root directory
        base = Path(__file__).resolve().parent.parent
    folder = base / "output"
    return str(folder)


def _get_config_path() -> Path:
    """
    Get config.json path.
    - PyInstaller packaged: exe directory
    - Development: project root directory
    """
    import sys
    if getattr(sys, "frozen", False):
        base = Path(sys.executable).parent
    else:
        base = Path(__file__).resolve().parent.parent
    return base / "config.json"


class ConfigManager:
    """Singleton config manager, supports reading/writing config.json and hot-reload."""

    _instance: "ConfigManager | None" = None

    def __new__(cls) -> "ConfigManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._config: dict[str, Any] = {}
            cls._instance._loaded = False
        return cls._instance

    def load(self) -> None:
        """Load config from config.json, fill missing fields with defaults."""
        config_path = _get_config_path()
        self._config = dict(DEFAULTS)  # Fill with defaults first

        if config_path.exists():
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                # Only update known keys, ignore unknown keys (backward compatible)
                for key in DEFAULTS:
                    if key in saved:
                        self._config[key] = saved[key]
            except (json.JSONDecodeError, OSError):
                pass  # Config file corrupted, use defaults

        # Auto-set output folder to ~/Downloads/SongShareTool/ if empty
        if not self._config.get("output_folder"):
            default_out = _get_default_output_folder()
            Path(default_out).mkdir(parents=True, exist_ok=True)
            self._config["output_folder"] = default_out

        self._loaded = True

    def save(self) -> None:
        """Write current config to config.json (atomic write to prevent corruption on crash)."""
        config_path = _get_config_path()
        tmp_path = config_path.with_suffix(".json.tmp")
        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(self._config, f, ensure_ascii=False, indent=2)
            tmp_path.replace(config_path)  # Atomic replace
        except OSError as e:
            tmp_path.unlink(missing_ok=True)
            raise RuntimeError(f"Config save failed: {e}") from e

    def reset_to_defaults(self) -> None:
        """Reset all config to defaults (does not auto-save)."""
        self._config = dict(DEFAULTS)

    def get(self, key: str, default: Any = None) -> Any:
        """Get config value."""
        if not self._loaded:
            self.load()
        return self._config.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Set config value (in memory, call save() to persist)."""
        self._config[key] = value

    def get_all(self) -> dict[str, Any]:
        """Get a copy of the full config dict."""
        if not self._loaded:
            self.load()
        return dict(self._config)

    def update_many(self, updates: dict[str, Any]) -> None:
        """Batch update config (in memory, call save() to persist)."""
        self._config.update(updates)


# Module-level singleton for direct import across modules
config = ConfigManager()
