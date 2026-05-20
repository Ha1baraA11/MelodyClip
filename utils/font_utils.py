"""
font_utils.py — Safe font loading + text wrapping utilities

- Font priority: Microsoft YaHei -> SimHei -> Pillow built-in
- wrap_text(): Auto-wrap text by pixel width (using font.getbbox for precise calculation)
"""

import sys
from pathlib import Path
from PIL import ImageFont, ImageDraw, Image
from typing import Optional

# ─── Font priority list ────────────────────────────────────────────────────────
_FONT_SEARCH_PATHS: list[str] = [
    # User custom font (highest priority, same directory as exe/script)
    "也字工厂润圆体.TTF",
    # Windows system fonts
    "C:/Windows/Fonts/msyh.ttc",     # Microsoft YaHei
    "C:/Windows/Fonts/msyhbd.ttc",   # Microsoft YaHei Bold
    "C:/Windows/Fonts/simhei.ttf",   # SimHei
    # macOS system fonts
    "/System/Library/Fonts/PingFang.ttc",
    "/System/Library/Fonts/STHeiti Medium.ttc",
    "/System/Library/Fonts/Supplemental/Songti.ttc",
    # Linux system fonts
    "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
]

# Global cache to avoid repeated loading
_font_cache: dict[tuple[str, int, bool], ImageFont.FreeTypeFont] = {}
_available_font_path: Optional[str] = None
_font_missing_warned = False


def _find_system_font() -> Optional[str]:
    """Find the first available Chinese font path on the system."""
    global _available_font_path
    if _available_font_path is not None:
        return _available_font_path

    for path in _FONT_SEARCH_PATHS:
        # Relative path: resolve via get_resource_path (PyInstaller compatible)
        if not Path(path).is_absolute():
            from utils.file_utils import get_resource_path
            resolved = get_resource_path(path)
        else:
            resolved = path

        if Path(resolved).exists():
            _available_font_path = resolved
            return resolved

    return None


def get_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    """
    Get a font object of specified size (with cache).
    Fallback order: Microsoft YaHei -> SimHei -> Pillow built-in
    """
    global _font_missing_warned

    cache_key = (_available_font_path or "", size, bold)
    if cache_key in _font_cache:
        return _font_cache[cache_key]

    font_path = _find_system_font()

    font: ImageFont.FreeTypeFont
    if font_path:
        try:
            # msyh.ttc contains multiple fonts, index=1 is usually Bold
            index = 1 if bold and font_path.endswith(".ttc") else 0
            font = ImageFont.truetype(font_path, size, index=index)
        except (OSError, IOError):
            font = ImageFont.load_default()
    else:
        if not _font_missing_warned:
            _font_missing_warned = True
            print("[Warning] No Chinese font detected, subtitles may display incorrectly")
        font = ImageFont.load_default()

    _font_cache[cache_key] = font
    return font


def is_font_available() -> bool:
    """Check if a Chinese font is available."""
    return _find_system_font() is not None


def get_font_warning() -> Optional[str]:
    """Return warning text if font is unavailable; otherwise return None."""
    if not is_font_available():
        return "No Chinese font detected (Microsoft YaHei/SimHei). Subtitles and titles may appear as boxes or garbled text."
    return None


# ─── Text wrapping utilities ──────────────────────────────────────────────────

def wrap_text(text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    """
    Auto-wrap text by pixel width.

    Args:
        text:      Original text
        font:      Pillow font object
        max_width: Maximum allowed pixel width per line

    Returns:
        List of wrapped lines, each no wider than max_width pixels
    """
    if not text:
        return []

    lines: list[str] = []
    current_line = ""

    for char in text:
        test_line = current_line + char
        bbox = font.getbbox(test_line)
        line_width = bbox[2] - bbox[0]

        if line_width > max_width:
            if current_line:
                lines.append(current_line)
            current_line = char
        else:
            current_line = test_line

    if current_line:
        lines.append(current_line)

    return lines


def measure_text(text: str, font: ImageFont.FreeTypeFont) -> tuple[int, int]:
    """
    Measure pixel width and height of text.

    Returns:
        (width, height)
    """
    bbox = font.getbbox(text)
    return bbox[2] - bbox[0], bbox[3] - bbox[1]


def hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    """Convert #RRGGBB color string to (R, G, B) tuple."""
    hex_color = hex_color.strip().lstrip("#")
    if len(hex_color) < 6:
        return (255, 255, 255)  # Invalid input falls back to white
    try:
        r = int(hex_color[0:2], 16)
        g = int(hex_color[2:4], 16)
        b = int(hex_color[4:6], 16)
    except ValueError:
        return (255, 255, 255)
    return r, g, b


def draw_text_with_stroke(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int],
    text: str,
    font: ImageFont.FreeTypeFont,
    fill: tuple[int, ...],
    stroke_fill: tuple[int, ...],
    stroke_width: int,
) -> None:
    """Draw text with stroke outline. Uses Pillow's native stroke_width parameter, more efficient and better quality than offset method."""
    draw.text(
        xy,
        text,
        font=font,
        fill=fill,
        stroke_width=stroke_width,
        stroke_fill=stroke_fill,
    )
