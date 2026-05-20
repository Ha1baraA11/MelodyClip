"""
video_builder.py — Video composition orchestrator

Complete 9-step composition workflow:
1. Path safety handling
2. Pre-process audio (format conversion + trimming)
3. Load assets
4. Compose main audio
5. Process background video (landscape adaptation + loop to fill duration)
6. Generate subtitle clip list
7. Generate static text clips
8. CompositeVideoClip composition and export
9. Clean up temporary files

Output spec: 1920x1080 / H.264 / yuv420p / AAC
"""

import itertools
import os
import random
from pathlib import Path
from typing import Callable, Generator

from moviepy import (
    VideoFileClip,
    AudioFileClip,
    CompositeVideoClip,
    concatenate_videoclips,
)

from core.audio_builder import (
    load_audio,
    trim_audio_fixed,
    trim_audio_manual,
    slice_audio,
    stream_audio_segments,
    build_final_audio,
    export_audio_to_temp,
)
from core.subtitle_builder import build_subtitle_clips
from core.text_overlay import build_top_text_clip, build_bottom_text_clip, build_bottom_center_text_clip
from utils.file_utils import safe_path, cleanup_temp, get_temp_dir, safe_move
from utils.config_manager import config
import uuid


# ─── Timeline Template Matching ───────────────────────────────────────────────

def _resolve_timeline(audio_path: str, cfg: dict) -> list[dict]:
    """
    Match a timeline from timeline_templates based on the audio file path.
    Priority: exact full path match, then filename match, then built-in filename match.
    """
    templates = cfg.get("timeline_templates", {})
    if not audio_path:
        return []

    # Exact match on full path (local file)
    if audio_path in templates:
        return templates[audio_path]

    # Exact match on filename
    name = Path(audio_path).name
    if name in templates:
        return templates[name]

    # Match built-in filename (used when the user has not set a custom path)
    for key in templates:
        if key in audio_path:
            return templates[key]

    return []


# ─── Background Video Processing ──────────────────────────────────────────────

def _load_background_video(
    bg_path: str,
    target_w: int,
    target_h: int,
    total_duration: float,
) -> VideoFileClip:
    """
    Load a background video, adapt to the target resolution, and loop to fill the total duration.

    Adaptation strategy (16:9 landscape output):
    - Landscape source (width/height >= target_w/target_h ratio) -> scale proportionally so height=target_h, then crop width centered
    - Portrait source -> center crop: scale proportionally so width=target_w, then crop height centered

    Uses loop=True to avoid the memory overhead of manual concatenation.
    """
    safe_bg, is_temp = safe_path(bg_path)

    clip = VideoFileClip(safe_bg, audio=False)
    src_w, src_h = clip.size

    scale_by_w = target_w / src_w
    scale_by_h = target_h / src_h
    scale = max(scale_by_w, scale_by_h)

    new_w = int(src_w * scale)
    new_h = int(src_h * scale)
    clip = clip.resized((new_w, new_h))

    x1 = (new_w - target_w) // 2
    y1 = (new_h - target_h) // 2
    clip = clip.cropped(x1=x1, y1=y1, width=target_w, height=target_h)

    # Loop to fill total duration
    if clip.duration < total_duration:
        loops_needed = int(total_duration / clip.duration) + 2
        clip = concatenate_videoclips([clip] * loops_needed)

    clip = clip.subclipped(0, total_duration)
    clip = clip.without_audio()

    if is_temp:
        # Attach to the final clip so that finally can find and clean it up
        clip._safe_bg_temp = safe_bg

    return clip


def _pick_background_file(
    bg_mode: str,
    bg_file: str,
    bg_folder: str,
    bg_strategy: str,
    bg_counter: itertools.count,
) -> str:
    """
    Select a background video file path based on the background video mode.

    Args:
        bg_counter: itertools.count object, auto-incremented for sequential cycling
    """
    if bg_mode == "fixed":
        if not bg_file or not Path(bg_file).exists():
            raise FileNotFoundError(f"Background video file does not exist: {bg_file}")
        return bg_file

    # Folder mode
    folder = Path(bg_folder)
    if not folder.exists():
        raise FileNotFoundError(f"Background video folder does not exist: {bg_folder}")

    video_exts = {".mp4", ".avi", ".mov", ".mkv", ".flv"}
    files = sorted([f for f in folder.iterdir() if f.suffix.lower() in video_exts])
    if not files:
        raise FileNotFoundError(f"No video files found in the background video folder: {bg_folder}")

    if bg_strategy == "random":
        return str(random.choice(files))
    else:  # sequential
        idx = next(bg_counter) % len(files)
        return str(files[idx])


# ─── Single Video Composition ─────────────────────────────────────────────────

def generate_one_video(
    song_name: str,
    song_audio_segment,       # pydub AudioSegment (pre-trimmed segment)
    output_path: str,
    cfg: dict,
    bg_counter: itertools.count,
    progress_cb: Callable[[str], None] | None = None,
) -> None:
    """
    Compose and export a single video (receives a pre-trimmed song audio segment).

    Args:
        song_name:         Song name (used for title template substitution)
        song_audio_segment: Pre-trimmed pydub AudioSegment
        output_path:       Final output path (supports non-ASCII characters)
        cfg:               Configuration dictionary (from config.get_all())
        bg_counter:        Background video sequential index ([int], mutable)
        progress_cb:       Progress callback
    """
    temp_files: list[str] = []
    bg_clip = None
    composite = None
    audio_clip = None

    try:
        # ── Step 4: Compose main audio ───────────────────────────────────────────
        if progress_cb:
            progress_cb("Compositing audio...")

        # Intro audio: user can enable/disable
        from utils.file_utils import get_resource_path
        intro_path = ""
        if cfg.get("enable_intro", True):
            intro_path = cfg.get("intro_audio", "")
            if intro_path:
                resolved = get_resource_path(intro_path)
                if Path(resolved).exists():
                    intro_path = resolved
                elif not Path(intro_path).exists():
                    intro_path = ""
            if not intro_path:
                default_intro = get_resource_path("开头(含橱窗引导).mp3")
                if Path(default_intro).exists():
                    intro_path = default_intro

        guide_path = ""
        if cfg.get("enable_guide", True):
            guide_path = cfg.get("guide_audio", "")
            if guide_path:
                resolved = get_resource_path(guide_path)
                if Path(resolved).exists():
                    guide_path = resolved
                elif not Path(guide_path).exists():
                    guide_path = ""
            if not guide_path:
                default_guide = get_resource_path("引导语.mp3")
                if Path(default_guide).exists():
                    guide_path = default_guide

        # Outro audio: user can enable/disable
        outro_path = ""
        if cfg.get("enable_outro", True):
            outro_path = cfg.get("outro_audio", "")
            if outro_path:
                resolved = get_resource_path(outro_path)
                if Path(resolved).exists():
                    outro_path = resolved
                elif not Path(outro_path).exists():
                    outro_path = ""
            if not outro_path:
                default_outro = get_resource_path("结尾(含橱窗引导).mp3")
                if Path(default_outro).exists():
                    outro_path = default_outro

        final_audio, audio_temps = build_final_audio(
            intro_path=intro_path,
            guide_path=guide_path,
            song_segment=song_audio_segment,
            outro_path=outro_path,
            silence_gap_sec=cfg.get("silence_gap", 0.3),
            fadeout_sec=cfg.get("fadeout_duration", 1.5),
            progress_cb=progress_cb,
        )
        temp_files.extend(audio_temps)

        # Export to temporary WAV (for MoviePy to use)
        temp_wav = export_audio_to_temp(final_audio)
        temp_files.append(temp_wav)
        video_duration = len(final_audio) / 1000.0  # Total duration in seconds

        # ── Step 5: Process background video ─────────────────────────────────────
        if progress_cb:
            progress_cb("Loading background video...")

        res = cfg.get("output_resolution", [1920, 1080])
        target_w, target_h = res[0], res[1]

        bg_file_path = _pick_background_file(
            bg_mode=cfg.get("background_mode", "fixed"),
            bg_file=cfg.get("background_file", ""),
            bg_folder=cfg.get("background_folder", ""),
            bg_strategy=cfg.get("background_select_strategy", "sequential"),
            bg_counter=bg_counter,
        )
        bg_clip = _load_background_video(bg_file_path, target_w, target_h, video_duration)

        # ── Step 6: Generate subtitle clips (optional) ───────────────────────────
        subtitle_clips = []
        sub_common = dict(
            video_duration=video_duration,
            video_width=target_w,
            video_height=target_h,
            font_size=cfg.get("subtitle_size", 56),
            bold=cfg.get("subtitle_bold", True),
            text_color=cfg.get("subtitle_color", "#FFD700"),
            stroke_color=cfg.get("subtitle_stroke_color", "#000000"),
            stroke_width=cfg.get("subtitle_stroke_width", 3),
            slide_in_duration=cfg.get("slide_in_duration", 0.3),
            max_lines=cfg.get("max_subtitle_lines", 3),
            progress_cb=progress_cb,
        )

        if cfg.get("enable_intro_subtitles", True):
            intro_subs = _resolve_timeline(intro_path, cfg)
            if not intro_subs:
                intro_subs = cfg.get("default_subtitles", [])
            if intro_subs:
                # Append a blank subtitle at the end of intro subtitles to signal "song starts here",
                # causing previous subtitles to disappear.
                # Calculate song start time = outro offset - song duration - silence gap
                # Simpler approach: derive from total duration
                if outro_path and Path(outro_path).exists():
                    from pydub import AudioSegment as _AS
                    outro_len = len(_AS.from_file(outro_path)) / 1000.0
                else:
                    outro_len = 0
                song_len = len(song_audio_segment) / 1000.0
                song_start = video_duration - outro_len - song_len - cfg.get("silence_gap", 0.3)
                if outro_len > 0:
                    song_start -= cfg.get("silence_gap", 0.3)

                # Append blank clearing subtitle
                intro_subs_with_clear = list(intro_subs) + [{"time": song_start, "text": ""}]

                if progress_cb:
                    progress_cb("Generating intro subtitles...")
                subtitle_clips += build_subtitle_clips(
                    subtitles=intro_subs_with_clear,
                    **sub_common,
                )

        # Guide subtitles: auto-match + time offset
        if cfg.get("enable_guide_subtitles", True) and cfg.get("enable_guide", True) and guide_path:
            guide_subs = _resolve_timeline(guide_path, cfg)
            if guide_subs:
                # Calculate guide audio start offset in the total audio = intro length + silence gap
                if intro_path and Path(intro_path).exists():
                    from pydub import AudioSegment as _AS
                    _intro_len = len(_AS.from_file(intro_path)) / 1000.0
                    guide_offset = _intro_len + cfg.get("silence_gap", 0.3)
                else:
                    guide_offset = 0

                offset_guide_subs = [
                    {"time": s["time"] + guide_offset, "text": s["text"]}
                    for s in guide_subs
                ]
                if progress_cb:
                    progress_cb("Generating guide subtitles...")
                subtitle_clips += build_subtitle_clips(
                    subtitles=offset_guide_subs,
                    **sub_common,
                )

        # Outro subtitles: auto-match + time offset
        if cfg.get("enable_outro_subtitles", True) and cfg.get("enable_outro", True):
            outro_subs = _resolve_timeline(outro_path, cfg)
            if not outro_subs:
                outro_subs = cfg.get("outro_subtitles", [])  # fallback
            if outro_subs:
                # Calculate outro audio start offset in the total audio
                if outro_path and Path(outro_path).exists():
                    from pydub import AudioSegment as _AS
                    _outro_len = len(_AS.from_file(outro_path)) / 1000.0
                    outro_offset = video_duration - _outro_len
                else:
                    outro_offset = video_duration - 7.5

                offset_subs = [
                    {"time": s["time"] + outro_offset, "text": s["text"]}
                    for s in outro_subs
                ]
                if progress_cb:
                    progress_cb("Generating outro subtitles...")
                subtitle_clips += build_subtitle_clips(
                    subtitles=offset_subs,
                    **sub_common,
                )

        # ── Step 7: Generate static text clips ───────────────────────────────────
        if progress_cb:
            progress_cb("Generating text overlays...")

        top_clip = build_top_text_clip(
            template=cfg.get("top_text_template", "{song_name}分享"),
            song_name=song_name,
            video_width=target_w,
            video_height=target_h,
            video_duration=video_duration,
            font_size=cfg.get("top_text_size", 72),
            bold=cfg.get("top_text_bold", True),
            text_color=cfg.get("top_text_color", "#000000"),
            stroke_color=cfg.get("top_text_stroke_color", "#000000"),
            stroke_width=cfg.get("top_text_stroke_width", 0),
            bg_color=cfg.get("top_text_bg_color", "#FFD700"),
        )

        bottom_clip = build_bottom_text_clip(
            text=cfg.get("bottom_text", "歌曲分享，无不良引导"),
            video_width=target_w,
            video_height=target_h,
            video_duration=video_duration,
            font_size=cfg.get("bottom_text_size", 36),
            bold=cfg.get("bottom_text_bold", False),
            text_color=cfg.get("bottom_text_color", "#FFFFFF"),
            stroke_color=cfg.get("bottom_text_stroke_color", "#000000"),
            stroke_width=cfg.get("bottom_text_stroke_width", 2),
        )

        # Bottom-center disclaimer text
        bottom_center_clip = build_bottom_center_text_clip(
            text=cfg.get("bottom_center_text", "歌曲歌词，请勿过度解读"),
            video_width=target_w,
            video_height=target_h,
            video_duration=video_duration,
            font_size=28,
        )

        # ── Step 8: Compose and export ───────────────────────────────────────────
        if progress_cb:
            progress_cb("Compositing video (this may take a while)...")

        all_clips = [bg_clip] + subtitle_clips + [top_clip, bottom_clip, bottom_center_clip]
        composite = CompositeVideoClip(all_clips, size=(target_w, target_h))

        # Load audio
        audio_clip = AudioFileClip(temp_wav)
        composite = composite.with_audio(audio_clip)

        # Write to temp directory first (pure ASCII path), then move to final output path
        temp_output = str(get_temp_dir() / f"{uuid.uuid4().hex[:12]}.mp4")
        temp_files.append(temp_output)

        fps = cfg.get("fps", 30)
        bitrate = cfg.get("bitrate", "4000k")

        composite.write_videofile(
            temp_output,
            fps=fps,
            codec="libx264",
            audio_codec="aac",
            bitrate=bitrate,
            ffmpeg_params=["-pix_fmt", "yuv420p", "-profile:v", "main"],
            logger=None,  # Disable MoviePy progress bar (handled by our own callback)
        )

        if progress_cb:
            progress_cb("Saving video file...")

        # Ensure output directory exists
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        safe_move(temp_output, output_path)
        temp_files.remove(temp_output)  # Already moved, no need to delete

        if progress_cb:
            progress_cb(f"Done! Saved to {output_path}")

    finally:
        # ── Step 9: Release resources + clean up temporary files ──────────────────
        if audio_clip is not None:
            try:
                audio_clip.close()
            except Exception:
                pass
        if composite is not None:
            try:
                composite.close()
            except Exception:
                pass
        if bg_clip is not None:
            bg_temp = getattr(bg_clip, "_safe_bg_temp", None)
            try:
                bg_clip.close()
            except Exception:
                pass
            if bg_temp:
                cleanup_temp(bg_temp)

        for t in temp_files:
            cleanup_temp(t)


# ─── Public entry point: single song generation ──────────────────────────────

def generate_single(
    song_file: str,
    song_name: str,
    cfg: dict,
    progress_cb: Callable[[str], None] | None = None,
) -> None:
    """
    Single song generation entry point.

    Args:
        song_file:  Path to the song file (MP3/MP4)
        song_name:  Song name (used for title template + output filename)
        cfg:        Full configuration dictionary
        progress_cb: Progress callback
    """
    temp_song_files: list[str] = []

    try:
        trim_mode = cfg.get("trim_mode", "fixed")

        output_dir = cfg.get("output_folder", "")
        if not output_dir:
            raise ValueError("Output directory not set. Please configure the output directory in settings.")
        output_dir = Path(output_dir)

        template = cfg.get("output_filename_template", "歌曲分享_{song_name}")
        bg_counter = itertools.count()

        if trim_mode == "slice":
            # Slice mode
            interval = cfg.get("slice_interval", 45)
            if Path(song_file).suffix.lower() == ".mp4":
                # MP4 streaming extraction: read and slice on the fly, avoid full loading and timeouts
                safe_mp4, is_temp = safe_path(song_file)
                if is_temp:
                    temp_song_files.append(safe_mp4)
                for part_idx, segment in enumerate(
                    stream_audio_segments(safe_mp4, interval, progress_cb), start=1
                ):
                    fname = template.replace("{song_name}", song_name) + f"_Part{part_idx}.mp4"
                    out_path = str(output_dir / fname)
                    if progress_cb:
                        progress_cb(f"Generating part {part_idx}...")
                    generate_one_video(song_name, segment, out_path, cfg, bg_counter, progress_cb)
            else:
                # MP3: load fully then slice
                if progress_cb:
                    progress_cb("Loading song audio...")
                song_audio, temp_song_files = load_audio(song_file, progress_cb=progress_cb)
                for part_idx, segment in enumerate(slice_audio(song_audio, interval), start=1):
                    fname = template.replace("{song_name}", song_name) + f"_Part{part_idx}.mp4"
                    out_path = str(output_dir / fname)
                    if progress_cb:
                        progress_cb(f"Generating part {part_idx}...")
                    generate_one_video(song_name, segment, out_path, cfg, bg_counter, progress_cb)
        else:
            # Fixed/manual mode: let FFmpeg directly extract the target segment (MP4 no longer fully extracted)
            if trim_mode == "fixed":
                start_sec = 0
                duration_sec = cfg.get("trim_duration", 45)
            else:  # manual
                start_sec = cfg.get("manual_start", 0)
                duration_sec = cfg.get("manual_duration", 45)

            if progress_cb:
                progress_cb("Loading song audio...")
            song_audio, temp_song_files = load_audio(
                song_file,
                start_sec=start_sec,
                duration_sec=duration_sec,
                progress_cb=progress_cb,
            )

            fname = template.replace("{song_name}", song_name) + ".mp4"
            out_path = str(output_dir / fname)
            generate_one_video(song_name, song_audio, out_path, cfg, bg_counter, progress_cb)

    finally:
        for t in temp_song_files:
            cleanup_temp(t)


# ─── Public entry point: batch generation ─────────────────────────────────────

def generate_batch(
    songs_path: str,
    cfg: dict,
    progress_cb: Callable[[str], None] | None = None,
    total_progress_cb: Callable[[int, int, str], None] | None = None,
) -> list[tuple[str, str]]:
    """
    Batch generation entry point.

    Args:
        songs_path:        Path to a song folder, or a single audio/video file path
                           - Folder: processes all MP3/MP4 files within
                           - Single file: automatically slices by slice_interval to generate multiple videos
        cfg:               Full configuration dictionary
        progress_cb:       Current step progress callback (str)
        total_progress_cb: Overall progress callback (current index, total count, filename)

    Returns:
        List of failures [(filename, error reason), ...]
    """
    target = Path(songs_path)
    if not target.exists():
        raise FileNotFoundError(f"Path does not exist: {songs_path}")

    audio_exts = {".mp3", ".mp4"}

    if target.is_file():
        # Single file mode: auto-slice
        if target.suffix.lower() not in audio_exts:
            raise ValueError(f"Unsupported file format: {target.suffix}. Please select an MP3 or MP4 file.")
        song_files = [target]
    else:
        # Folder mode
        song_files = sorted([f for f in target.iterdir() if f.suffix.lower() in audio_exts])

    if not song_files:
        raise ValueError(f"No MP3/MP4 files found: {songs_path}")

    failed: list[tuple[str, str]] = []
    bg_counter = itertools.count()

    output_dir = Path(cfg.get("output_folder", ""))
    if not str(output_dir):
        raise ValueError("Output directory not set. Please configure the output directory in settings.")
    template = cfg.get("output_filename_template", "歌曲分享_{song_name}")

    # Single-file batch mode forces slicing; multi-file mode uses user configuration
    force_slice = target.is_file()
    trim_mode = "slice" if force_slice else cfg.get("trim_mode", "fixed")

    for i, song_file in enumerate(song_files):
        song_name = song_file.stem  # Filename without extension used as song name

        if total_progress_cb:
            total_progress_cb(i + 1, len(song_files), song_file.name)

        temp_song_files: list[str] = []
        try:
            if progress_cb:
                progress_cb(f"Processing {i+1}/{len(song_files)}: {song_file.name}")

            if trim_mode == "slice":
                # Slice mode
                interval = cfg.get("slice_interval", 45)
                if song_file.suffix.lower() == ".mp4":
                    # MP4 streaming extraction: read and slice on the fly, no full loading
                    safe_mp4, is_temp = safe_path(str(song_file))
                    if is_temp:
                        temp_song_files.append(safe_mp4)
                    for part_idx, segment in enumerate(
                        stream_audio_segments(safe_mp4, interval, progress_cb), start=1
                    ):
                        fname = template.replace("{song_name}", song_name) + f"_Part{part_idx}.mp4"
                        out_path = str(output_dir / fname)
                        generate_one_video(song_name, segment, out_path, cfg, bg_counter, progress_cb)
                else:
                    # MP3: load fully then slice
                    song_audio, temp_song_files = load_audio(str(song_file), progress_cb=progress_cb)
                    for part_idx, segment in enumerate(slice_audio(song_audio, interval), start=1):
                        fname = template.replace("{song_name}", song_name) + f"_Part{part_idx}.mp4"
                        out_path = str(output_dir / fname)
                        generate_one_video(song_name, segment, out_path, cfg, bg_counter, progress_cb)
            else:
                # Fixed/manual: directly extract the target segment
                if trim_mode == "fixed":
                    start_sec = 0
                    duration_sec = cfg.get("trim_duration", 45)
                else:
                    start_sec = cfg.get("manual_start", 0)
                    duration_sec = cfg.get("manual_duration", 45)

                song_audio, temp_song_files = load_audio(
                    str(song_file),
                    start_sec=start_sec,
                    duration_sec=duration_sec,
                    progress_cb=progress_cb,
                )
                fname = template.replace("{song_name}", song_name) + ".mp4"
                out_path = str(output_dir / fname)
                generate_one_video(song_name, song_audio, out_path, cfg, bg_counter, progress_cb)

        except Exception as e:
            failed.append((song_file.name, str(e)))
            if progress_cb:
                progress_cb(f"[Skipped] {song_file.name} failed: {e}")
        finally:
            for t in temp_song_files:
                cleanup_temp(t)

    return failed
