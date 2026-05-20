"""
audio_builder.py — Audio processing module

Responsibilities:
1. MP4 -> MP3 extraction (FFmpeg, supports direct segment extraction to avoid full extraction)
2. Audio standardization (44100Hz / stereo / 16-bit)
3. Three trim modes (fixed / slice / manual)
4. Three-segment audio concatenation (intro + guide + song clip)
5. Fade-out at the end of the song clip
"""

import os
import subprocess
import sys
from pathlib import Path
from typing import Callable, Generator

_NO_WINDOW = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0

from pydub import AudioSegment
from pydub.generators import Sine

from utils.file_utils import get_resource_path, safe_path, cleanup_temp, get_temp_dir
import uuid


# ─── Audio Standardization ────────────────────────────────────────────────────

def standardize_audio(audio: AudioSegment) -> AudioSegment:
    """
    Force-unify audio parameters to eliminate concatenation conflicts.
    -> 44100Hz / stereo(2ch) / 16-bit
    """
    audio = audio.set_frame_rate(44100)
    audio = audio.set_channels(2)
    audio = audio.set_sample_width(2)
    return audio


def make_silence(duration_sec: float) -> AudioSegment:
    """Generate a silent audio segment of the specified duration (standardized)."""
    ms = int(duration_sec * 1000)
    silence = AudioSegment.silent(duration=ms, frame_rate=44100)
    return standardize_audio(silence)


# ─── FFmpeg Discovery and Audio Extraction ────────────────────────────────────

def _find_ffmpeg() -> str:
    """Find a usable FFmpeg executable path. Priority: bundled > imageio_ffmpeg > system PATH."""
    bundled = get_resource_path("ffmpeg/ffmpeg.exe")
    if Path(bundled).exists():
        return bundled

    try:
        import imageio_ffmpeg
        exe = imageio_ffmpeg.get_ffmpeg_exe()
        if Path(exe).exists():
            return exe
    except (ImportError, FileNotFoundError):
        pass

    return "ffmpeg"


def _setup_ffprobe() -> None:
    """Ensure pydub works correctly. When ffprobe is not available, patch pydub's probe logic."""
    import shutil
    import pydub.utils

    ffmpeg_exe = _find_ffmpeg()

    if not shutil.which("ffmpeg"):
        pydub.utils.get_encoder_name = lambda: ffmpeg_exe
        # from_file uses cls.converter instead of get_encoder_name()
        AudioSegment.converter = ffmpeg_exe

    if not shutil.which("ffprobe"):
        # imageio_ffmpeg's ffmpeg does not support ffprobe's -show_format/-show_streams
        # Patch mediainfo_json to return None, pydub will fall back to default conversion (no quality loss)
        _no_info = lambda *a, **kw: None
        pydub.utils.mediainfo_json = _no_info
        # The audio_segment module has its own reference, also needs patching
        import pydub.audio_segment
        pydub.audio_segment.mediainfo_json = _no_info


def extract_audio_from_mp4(
    mp4_path: str,
    start_sec: float = 0,
    duration_sec: float | None = None,
    progress_cb: Callable[[str], None] | None = None,
) -> str:
    """
    Extract audio track from an MP4 file and convert to MP3 using FFmpeg.

    Uses -ss/-t parameters to let FFmpeg directly extract the target segment,
    avoiding full extraction followed by in-Python trimming.

    Args:
        mp4_path:      Path to the MP4 file (must be a pure ASCII path)
        start_sec:     Start time in seconds, default 0
        duration_sec:  Extraction duration in seconds, None means extract all
        progress_cb:   Progress callback

    Returns:
        Path to the temporary MP3 file (caller must clean up via cleanup_temp)
    """
    ffmpeg_exe = _find_ffmpeg()
    temp_mp3 = str(get_temp_dir() / f"{uuid.uuid4().hex[:12]}.mp3")

    cmd = [ffmpeg_exe]

    # -ss before -i = input seek (fast jump, does not decode preceding content)
    if start_sec > 0:
        cmd.extend(["-ss", str(start_sec)])

    cmd.extend(["-i", mp4_path])

    if duration_sec is not None:
        cmd.extend(["-t", str(duration_sec)])

    cmd.extend([
        "-q:a", "0",    # Highest audio quality
        "-map", "a",     # Extract audio track only
        "-y",
        temp_mp3,
    ])

    if progress_cb:
        if start_sec > 0 or duration_sec:
            progress_cb("Extracting audio segment from MP4...")
        else:
            progress_cb("Extracting audio from MP4...")

    try:
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=600,
            creationflags=_NO_WINDOW,
        )
        if result.returncode != 0:
            err = result.stderr.decode("utf-8", errors="replace")
            raise RuntimeError(f"FFmpeg failed to extract audio: {err[-300:]}")
    except FileNotFoundError:
        raise RuntimeError("FFmpeg not found. Windows users: ensure ffmpeg.exe is in the application directory. macOS users: run brew install ffmpeg")
    except subprocess.TimeoutExpired:
        raise RuntimeError("FFmpeg audio extraction timed out (>600 seconds)")

    return temp_mp3


def stream_audio_segments(
    mp4_path: str,
    interval_sec: float,
    progress_cb: Callable[[str], None] | None = None,
) -> Generator[AudioSegment, None, None]:
    """
    Stream audio extraction from MP4 and slice by interval, yielding segments one by one.

    Pipes raw PCM output from FFmpeg stdout, reading and slicing on the fly to avoid
    loading the entire file into memory. Suitable for very long video files (e.g. 420 minutes)
    without triggering FFmpeg timeouts.

    Args:
        mp4_path:      Path to the MP4 file (pure ASCII path)
        interval_sec:  Slice interval in seconds
        progress_cb:   Progress callback
    """
    ffmpeg_exe = _find_ffmpeg()
    safe, is_temp = safe_path(mp4_path)

    cmd = [
        ffmpeg_exe,
        "-i", safe,
        "-f", "s16le",         # raw PCM 16-bit little-endian
        "-acodec", "pcm_s16le",
        "-ar", "44100",        # 44100Hz
        "-ac", "2",            # stereo
        "-v", "error",         # Reduce log output
        "-nostdin",
        "pipe:1",
    ]

    if progress_cb:
        progress_cb("Streaming audio from MP4...")

    proc = None
    try:
        si = subprocess.STARTUPINFO() if hasattr(subprocess, "STARTUPINFO") else None
        if si:
            si.dwFlags |= subprocess.STARTF_USESHOWWINDOW

        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            startupinfo=si,
            creationflags=_NO_WINDOW,
        )

        bytes_per_sec = 44100 * 2 * 2  # sample_rate * channels * bytes_per_sample
        chunk_bytes = int(interval_sec * bytes_per_sec)
        segment_idx = 0

        while True:
            raw = b""
            while len(raw) < chunk_bytes:
                needed = chunk_bytes - len(raw)
                data = proc.stdout.read(needed)
                if not data:
                    break
                raw += data

            if not raw:
                break

            segment_idx += 1
            if progress_cb:
                progress_cb(f"Processing segment {segment_idx}...")

            # Align to frame boundary (4 bytes = 1 frame of stereo 16-bit)
            frame_size = 4
            aligned = len(raw) - (len(raw) % frame_size)
            if aligned > 0:
                audio = AudioSegment(
                    data=raw[:aligned],
                    sample_width=2,
                    frame_rate=44100,
                    channels=2,
                )
                yield standardize_audio(audio)

    except FileNotFoundError:
        raise RuntimeError(
            "FFmpeg not found. Windows users: ensure ffmpeg.exe is in the application directory. "
            "macOS users: run brew install ffmpeg"
        )
    finally:
        if proc is not None:
            try:
                proc.stdout.close()
            except Exception:
                pass
            try:
                proc.wait(timeout=10)
            except Exception:
                proc.kill()
        if is_temp:
            cleanup_temp(safe)


# ─── Load Audio File ──────────────────────────────────────────────────────────

def load_audio(
    file_path: str,
    start_sec: float = 0,
    duration_sec: float | None = None,
    progress_cb: Callable[[str], None] | None = None,
) -> tuple[AudioSegment, list[str]]:
    """
    Load an audio file (MP3 / MP4) and return a standardized AudioSegment.

    For MP4 files, FFmpeg directly extracts the target segment (-ss/-t) without full extraction.
    For MP3 files, pydub loads the full file and trims in memory.

    Args:
        file_path:     Path to the audio/video file
        start_sec:     Start time in seconds, default 0
        duration_sec:  Trim duration in seconds, None means all
        progress_cb:   Progress callback

    Returns:
        (audio_segment, temp_files_to_cleanup)
    """
    temp_files: list[str] = []
    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    if path.suffix.lower() == ".mp4":
        # MP4: FFmpeg directly extracts the target segment
        safe_mp4, is_temp_mp4 = safe_path(file_path)
        if is_temp_mp4:
            temp_files.append(safe_mp4)
        actual_path = extract_audio_from_mp4(safe_mp4, start_sec, duration_sec, progress_cb)
        temp_files.append(actual_path)
        audio = AudioSegment.from_file(actual_path)
        audio = standardize_audio(audio)
    else:
        # MP3: load with pydub then trim
        safe_mp3, is_temp_mp3 = safe_path(file_path)
        if is_temp_mp3:
            temp_files.append(safe_mp3)
        audio = AudioSegment.from_file(safe_mp3)
        audio = standardize_audio(audio)
        if start_sec > 0 or duration_sec is not None:
            start_ms = int(start_sec * 1000)
            end_ms = start_ms + int(duration_sec * 1000) if duration_sec else len(audio)
            start_ms = min(start_ms, len(audio))
            end_ms = min(end_ms, len(audio))
            audio = audio[start_ms:end_ms]

    return audio, temp_files


# ─── Audio Trimming ───────────────────────────────────────────────────────────

def trim_audio_fixed(audio: AudioSegment, duration_sec: float) -> AudioSegment:
    """
    Fixed-duration trim: cut the specified number of seconds from the beginning.
    If the original audio is shorter than or equal to the target duration, return the full audio.
    """
    target_ms = int(duration_sec * 1000)
    if len(audio) <= target_ms:
        return audio
    return audio[:target_ms]


def trim_audio_manual(audio: AudioSegment, start_sec: float, duration_sec: float) -> AudioSegment:
    """
    Manual trim: cut duration_sec seconds starting from start_sec.
    """
    start_ms = int(start_sec * 1000)
    end_ms = start_ms + int(duration_sec * 1000)
    start_ms = min(start_ms, len(audio))
    end_ms = min(end_ms, len(audio))
    segment = audio[start_ms:end_ms]
    if len(segment) < 100:
        raise ValueError(f"Audio too short after trimming ({len(segment)}ms), please check trim parameters")
    return segment


def slice_audio(audio: AudioSegment, interval_sec: float) -> Generator[AudioSegment, None, None]:
    """
    Slice by interval: split audio into segments of interval_sec seconds each.
    Each segment is yielded individually for the caller to generate videos one by one.
    """
    interval_ms = int(interval_sec * 1000)
    total_ms = len(audio)
    start = 0
    while start < total_ms:
        end = min(start + interval_ms, total_ms)
        yield audio[start:end]
        start += interval_ms


# ─── Audio Concatenation ──────────────────────────────────────────────────────

def build_final_audio(
    intro_path: str,
    guide_path: str,
    song_segment: AudioSegment,
    outro_path: str = "",
    silence_gap_sec: float = 0.3,
    fadeout_sec: float = 1.5,
    progress_cb: Callable[[str], None] | None = None,
) -> tuple[AudioSegment, list[str]]:
    """
    Concatenate final audio: [Intro] + [Guide] + Song (fade out) + [Outro]

    Returns:
        (final_audio, temp_files_to_cleanup)
    """
    temp_files: list[str] = []
    segments: list[AudioSegment] = []
    silence = make_silence(silence_gap_sec)

    # ── Intro audio ────────────────────────────────────────────────────────────
    if intro_path and Path(intro_path).exists():
        if progress_cb:
            progress_cb("Loading intro audio...")
        intro_audio, t1 = load_audio(intro_path, progress_cb=progress_cb)
        temp_files.extend(t1)
        segments.append(intro_audio)
        segments.append(silence)

    # ── Guide audio ────────────────────────────────────────────────────────────
    if guide_path and Path(guide_path).exists():
        if progress_cb:
            progress_cb("Loading guide audio...")
        guide_audio, t2 = load_audio(guide_path, progress_cb=progress_cb)
        temp_files.extend(t2)
        segments.append(guide_audio)
        segments.append(silence)

    # ── Song clip (fade out) ────────────────────────────────────────────────────
    if fadeout_sec > 0:
        fade_ms = min(int(fadeout_sec * 1000), len(song_segment))
        if fade_ms > 0:
            song_segment = song_segment.fade_out(fade_ms)
    segments.append(song_segment)

    # ── Outro audio ────────────────────────────────────────────────────────────
    if outro_path and Path(outro_path).exists():
        if progress_cb:
            progress_cb("Loading outro audio...")
        outro_audio, t3 = load_audio(outro_path, progress_cb=progress_cb)
        temp_files.extend(t3)
        segments.append(silence)
        segments.append(outro_audio)

    # ── Concatenation ───────────────────────────────────────────────────────────
    final = segments[0]
    for seg in segments[1:]:
        final = final + seg

    final = standardize_audio(final)
    return final, temp_files


def export_audio_to_temp(audio: AudioSegment) -> str:
    """
    Export AudioSegment to a temporary WAV file for MoviePy to use.

    Returns:
        Path to the temporary WAV file (caller must clean up via cleanup_temp)
    """
    temp_wav = str(get_temp_dir() / f"{uuid.uuid4().hex[:12]}.wav")
    audio.export(temp_wav, format="wav")
    return temp_wav
