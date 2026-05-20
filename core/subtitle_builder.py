"""
subtitle_builder.py — Subtitle rendering module

Responsibilities:
1. Draw subtitle images with white text and black stroke using Pillow (transparent background)
2. Automatic text wrapping (wraps when exceeding single-line width)
3. Three-slot instant jump method (1920x1080 widescreen layout)
4. Subtitle slide-in animation clip (slides in from off-screen left)
"""

import numpy as np
from PIL import Image, ImageDraw
from typing import Callable

from utils.font_utils import get_font, wrap_text, hex_to_rgb, draw_text_with_stroke


# ─── Subtitle Image Drawing ───────────────────────────────────────────────────

def draw_subtitle_image(
    text: str,
    font_size: int = 44,
    bold: bool = True,
    text_color: str = "#FFFFFF",
    stroke_color: str = "#000000",
    stroke_width: int = 2,
    max_width: int = 900,   # ~84% of video width (8% margin on each side)
    max_lines: int = 3,
) -> Image.Image:
    """
    Draw a single subtitle image using Pillow (transparent RGBA background).

    Returns:
        RGBA PIL Image with transparent background
    """
    font = get_font(font_size, bold)
    fg = hex_to_rgb(text_color)
    stroke = hex_to_rgb(stroke_color)

    lines = wrap_text(text, font, max_width)[:max_lines]
    if not lines:
        lines = [""]

    sample_bbox = font.getbbox("Ag")
    line_height = sample_bbox[3] - sample_bbox[1] + stroke_width * 2 + 4
    total_height = line_height * len(lines)

    img_width = 0
    for line in lines:
        bbox = font.getbbox(line)
        w = bbox[2] - bbox[0] + stroke_width * 2 + 4
        img_width = max(img_width, w)
    img_width = max(img_width, 1)

    img = Image.new("RGBA", (img_width, total_height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    y = 0
    for line in lines:
        draw_text_with_stroke(
            draw, (stroke_width + 2, y), line, font,
            fill=(*fg, 255), stroke_fill=(*stroke, 255), stroke_width=stroke_width,
        )
        y += line_height

    return img


# ─── Three-Slot Subtitle Clip Generation ──────────────────────────────────────

def _slot_x(video_width: int) -> int:
    """Subtitle starting X position (8% safe margin on the left)."""
    return int(video_width * 0.08)


def _slot_y(slot_index: int, video_height: int, max_lines: int = 3) -> int:
    """
    Calculate slot Y coordinate (percentage-based positioning, adapts to any resolution).
    The bottom slot is at 60% of video height, with 6% of video height spacing between slots.
    slot_index: 0=topmost, max_lines-1=bottommost
    """
    base_y = int(video_height * 0.60)  # Bottom slot Y
    spacing = int(video_height * 0.06)  # Slot spacing
    return base_y - (spacing * (max_lines - 1 - slot_index))


def build_subtitle_clips(
    subtitles: list[dict],
    video_duration: float,
    video_width: int = 1080,
    video_height: int = 1920,
    font_size: int = 44,
    bold: bool = True,
    text_color: str = "#FFFFFF",
    stroke_color: str = "#000000",
    stroke_width: int = 2,
    slide_in_duration: float = 0.3,
    max_lines: int = 3,
    progress_cb: Callable[[str], None] | None = None,
) -> list:
    """
    Generate a list of MoviePy clips for all subtitles.

    Three-slot logic:
    - At most max_lines subtitles are displayed on screen at any time
    - New subtitles always appear in the bottommost slot (with slide-in animation)
    - When active subtitles exceed max_lines, the earliest one is pushed out (no longer displayed)

    Args:
        subtitles: [{"time": float, "text": str}, ...]
        video_duration: Total video duration in seconds

    Returns:
        List of MoviePy ImageClip objects
    """
    from moviepy import ImageClip

    if not subtitles:
        return []

    subtitles = sorted(subtitles, key=lambda s: s["time"])

    if progress_cb:
        progress_cb("Generating subtitles...")

    clips = []

    for i, sub in enumerate(subtitles):
        start_time = sub["time"]
        end_time = subtitles[i + 1]["time"] if i + 1 < len(subtitles) else video_duration

        if start_time >= end_time:
            continue

        # Blank subtitle = clear signal: no clip generated, but the previous subtitle's end_time is already set to this one's start_time
        if not sub.get("text", "").strip():
            continue

        duration = end_time - start_time

        # Max subtitle width: video width minus 8% margin on each side
        sub_max_width = int(video_width * 0.84)

        pil_img = draw_subtitle_image(
            text=sub["text"],
            font_size=font_size,
            bold=bold,
            text_color=text_color,
            stroke_color=stroke_color,
            stroke_width=stroke_width,
            max_width=sub_max_width,
            max_lines=max_lines,
        )

        img_array = np.array(pil_img)

        # Calculate the current subtitle's slot in the active window
        # Look backwards from the current subtitle to find coexisting subtitles on screen (i.e. end_time > start_time)
        # These subtitles are sorted by start_time in descending order, current subtitle is at position 0 (bottommost)
        active_count = 0
        for j in range(i - 1, -1, -1):
            prev_end = subtitles[j + 1]["time"] if j + 1 < len(subtitles) else video_duration
            if prev_end > start_time:
                active_count += 1
            if active_count >= max_lines - 1:
                break

        # active_count = number of subtitles already on screen (excluding current)
        # Current subtitle goes to the bottommost position, existing ones shift up
        # If there are already >= max_lines-1, the earliest one is pushed out, rest shift up
        slot_in_window = min(active_count, max_lines - 1)  # 0=topmost, max_lines-1=bottommost
        # Current new subtitle is always in the bottommost slot, so its position in the window is from the end
        # But we need its slot index on the Y axis
        # When active subtitle count < max_lines-1: current subtitle at bottom, slot = active count
        # When active subtitle count >= max_lines-1: full, current subtitle at bottom = max_lines-1
        target_slot = min(active_count, max_lines - 1)

        target_y = _slot_y(target_slot, video_height, max_lines)
        target_x = _slot_x(video_width)
        clip_w = pil_img.width

        clip = (
            ImageClip(img_array, is_mask=False)
            .with_start(start_time)
            .with_duration(duration)
        )

        # Slide-in animation
        _sx, _sy, _sw, _sd = target_x, target_y, clip_w, slide_in_duration
        def make_position_func(sx, sy, sw, sd):
            def position_func(t: float):
                if t < sd and sd > 0:
                    progress = t / sd
                    x = sx - (1.0 - progress) * (sx + sw)
                else:
                    x = float(sx)
                return (x, float(sy))
            return position_func

        clip = clip.with_position(make_position_func(_sx, _sy, _sw, _sd))
        clips.append(clip)

    return clips
