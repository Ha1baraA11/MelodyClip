"""
text_overlay.py — Static text overlay module

Responsibilities:
Generate static text ImageClips displayed throughout the video:
- Top title (supports {song_name} template variable, optional background color)
- Bottom disclaimer text
"""

import numpy as np
from PIL import Image, ImageDraw

from utils.font_utils import get_font, wrap_text, hex_to_rgb, draw_text_with_stroke


def _draw_text_image(
    text: str,
    font_size: int,
    bold: bool,
    text_color: str,
    stroke_color: str,
    stroke_width: int,
    max_width: int,
    max_lines: int = 2,
    bg_color: str | None = None,
    padding: int = 12,
) -> Image.Image:
    """
    Draw a text image with stroke (RGBA).

    Args:
        bg_color: Background color (#RRGGBB), None=transparent background
        padding:  Padding between text and background edge (pixels)
    """
    font = get_font(font_size, bold)
    fg = hex_to_rgb(text_color)
    stroke = hex_to_rgb(stroke_color)

    lines = wrap_text(text, font, max_width)[:max_lines]
    if not lines:
        lines = [""]

    sample_bbox = font.getbbox("Ag")
    line_height = sample_bbox[3] - sample_bbox[1] + stroke_width * 2 + 6
    total_height = line_height * len(lines)

    img_width = 0
    for line in lines:
        bbox = font.getbbox(line)
        w = bbox[2] - bbox[0] + stroke_width * 2 + 8
        img_width = max(img_width, w)
    img_width = max(img_width, 1)

    # When background color is set: image width = text width + left/right padding, height = text height + top/bottom padding
    if bg_color is not None:
        img_width += padding * 2
        total_height += padding * 2

    bg = hex_to_rgb(bg_color) if bg_color else None
    bg_alpha = 255 if bg_color else 0
    img = Image.new("RGBA", (img_width, total_height), (*bg, bg_alpha) if bg else (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    y = padding if bg_color else 0
    x = padding + stroke_width + 4 if bg_color else stroke_width + 4
    for line in lines:
        draw_text_with_stroke(
            draw, (x, y), line, font,
            fill=(*fg, 255), stroke_fill=(*stroke, 255), stroke_width=stroke_width,
        )
        y += line_height

    return img


# ─── Top Title Clip ───────────────────────────────────────────────────────────

def build_top_text_clip(
    template: str,
    song_name: str,
    video_width: int,
    video_height: int,
    video_duration: float,
    font_size: int = 72,
    bold: bool = True,
    text_color: str = "#000000",
    stroke_color: str = "#000000",
    stroke_width: int = 0,
    bg_color: str | None = "#FFD700",
):
    """
    Generate a top title ImageClip, displayed throughout the video, horizontally centered, about 5% from the top.
    Supports background color (e.g. yellow background with black text).
    """
    from moviepy import ImageClip

    text = template.replace("{song_name}", song_name)
    # Near full width: 3% margin on each side
    max_width = int(video_width * 0.94)

    pil_img = _draw_text_image(
        text=text,
        font_size=font_size,
        bold=bold,
        text_color=text_color,
        stroke_color=stroke_color,
        stroke_width=stroke_width,
        max_width=max_width,
        max_lines=1,
        bg_color=bg_color,
        padding=16,
    )

    img_array = np.array(pil_img)

    # Horizontally centered, 5% from top
    x = (video_width - pil_img.width) // 2
    y = int(video_height * 0.05)

    clip = (
        ImageClip(img_array, is_mask=False)
        .with_start(0)
        .with_duration(video_duration)
        .with_position((x, y))
    )
    return clip


# ─── Bottom Disclaimer Text Clip ──────────────────────────────────────────────

def build_bottom_text_clip(
    text: str,
    video_width: int,
    video_height: int,
    video_duration: float,
    font_size: int = 36,
    bold: bool = False,
    text_color: str = "#FFFFFF",
    stroke_color: str = "#000000",
    stroke_width: int = 2,
):
    """Generate a bottom disclaimer text ImageClip, displayed throughout the video, horizontally centered, about 5% from the bottom."""
    from moviepy import ImageClip

    max_width = int(video_width * 0.85)

    pil_img = _draw_text_image(
        text=text,
        font_size=font_size,
        bold=bold,
        text_color=text_color,
        stroke_color=stroke_color,
        stroke_width=stroke_width,
        max_width=max_width,
        max_lines=2,
    )

    img_array = np.array(pil_img)

    x = (video_width - pil_img.width) // 2
    y = int(video_height * 0.92) - pil_img.height

    clip = (
        ImageClip(img_array, is_mask=False)
        .with_start(0)
        .with_duration(video_duration)
        .with_position((x, y))
    )
    return clip


# ─── Bottom-Center Disclaimer Text Clip ───────────────────────────────────────

def build_bottom_center_text_clip(
    text: str,
    video_width: int,
    video_height: int,
    video_duration: float,
    font_size: int = 32,
    bold: bool = False,
    text_color: str = "#FFFFFF",
    stroke_color: str = "#000000",
    stroke_width: int = 2,
):
    """Generate a bottom-center disclaimer text ImageClip (centered at the very bottom of the video, 3% from the bottom)."""
    from moviepy import ImageClip

    max_width = int(video_width * 0.90)

    pil_img = _draw_text_image(
        text=text,
        font_size=font_size,
        bold=bold,
        text_color=text_color,
        stroke_color=stroke_color,
        stroke_width=stroke_width,
        max_width=max_width,
        max_lines=1,
    )

    img_array = np.array(pil_img)

    x = (video_width - pil_img.width) // 2
    y = video_height - pil_img.height - int(video_height * 0.03)

    clip = (
        ImageClip(img_array, is_mask=False)
        .with_start(0)
        .with_duration(video_duration)
        .with_position((x, y))
    )
    return clip
