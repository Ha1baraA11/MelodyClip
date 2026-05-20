"""
speech_analyzer.py — Voice Activity Detection + Speech-to-Text + Subtitle Timeline Generation

Workflow:
1. VAD detects speech segment start/end times (energy analysis)
2. Speech-to-text for each speech segment (Google free API)
3. Generate subtitle timeline with text

Results are cached in config; the same audio is not analyzed repeatedly.
"""

import hashlib
import io
import tempfile
from pathlib import Path
from typing import Callable

import numpy as np
from pydub import AudioSegment


def _audio_fingerprint(file_path: str) -> str:
    """Generate a fingerprint based on file path + size + modification time, used as a cache key."""
    p = Path(file_path)
    if not p.exists():
        return ""
    stat = p.stat()
    raw = f"{file_path}:{stat.st_size}:{stat.st_mtime_ns}"
    return hashlib.md5(raw.encode()).hexdigest()[:12]


def analyze_speech_segments(
    audio: AudioSegment,
    min_silence_ms: int = 300,
    silence_threshold_db: float = -35,
) -> list[tuple[float, float]]:
    """
    Detect voice activity segments in audio.

    Returns:
        [(start_sec, end_sec), ...] list of speech segments
    """
    mono = audio.set_channels(1)
    samples = np.array(mono.get_array_of_samples(), dtype=np.float32)

    frame_ms = 50
    frame_size = int(mono.frame_rate * frame_ms / 1000)
    total_frames = len(samples) // frame_size

    energies = []
    for i in range(total_frames):
        chunk = samples[i * frame_size : (i + 1) * frame_size]
        rms = np.sqrt(np.mean(chunk ** 2))
        if rms > 0:
            db = 20 * np.log10(rms / 32768.0)
        else:
            db = -100.0
        energies.append(db)

    is_speech = [e > silence_threshold_db for e in energies]

    segments = []
    in_speech = False
    seg_start = 0

    for i, speaking in enumerate(is_speech):
        if speaking and not in_speech:
            seg_start = i
            in_speech = True
        elif not speaking and in_speech:
            silence_duration = 0
            j = i
            while j < total_frames and not is_speech[j]:
                silence_duration += frame_ms
                j += 1
            if silence_duration >= min_silence_ms:
                segments.append((seg_start * frame_ms / 1000.0, i * frame_ms / 1000.0))
                in_speech = False

    if in_speech:
        segments.append((seg_start * frame_ms / 1000.0, total_frames * frame_ms / 1000.0))

    return segments


def _transcribe_segment(audio: AudioSegment, start_sec: float, end_sec: float) -> str:
    """Transcribe an audio segment using the Google free speech recognition API."""
    import speech_recognition as sr

    start_ms = int(start_sec * 1000)
    end_ms = int(end_sec * 1000)
    segment = audio[start_ms:end_ms]

    # Export as WAV (required by Google API)
    wav_data = io.BytesIO()
    segment.export(wav_data, format="wav")
    wav_data.seek(0)

    recognizer = sr.Recognizer()
    with sr.AudioFile(wav_data) as source:
        audio_data = recognizer.record(source)

    try:
        text = recognizer.recognize_google(audio_data, language="zh-CN")
        return text
    except (sr.UnknownValueError, sr.RequestError):
        return ""


def transcribe_audio(
    audio_path: str,
    cached_timelines: dict | None = None,
    progress_cb: Callable[[str], None] | None = None,
) -> list[dict]:
    """
    Complete workflow: VAD detection + speech-to-text -> subtitle timeline.

    1. Check cache
    2. VAD detects speech segments
    3. Speech-to-text for each segment
    4. Generate timeline and cache it

    Args:
        audio_path:       Path to the audio file
        cached_timelines: Cache dictionary {fingerprint: timeline}, updated in place
        progress_cb:      Progress callback

    Returns:
        [{"time": float, "text": str}, ...]
    """
    fingerprint = _audio_fingerprint(audio_path)
    if not fingerprint:
        return []

    # Check cache
    if cached_timelines and fingerprint in cached_timelines:
        if progress_cb:
            progress_cb("Using cached subtitle timeline")
        return cached_timelines[fingerprint]

    if progress_cb:
        progress_cb("Loading audio...")

    audio = AudioSegment.from_file(audio_path)

    if progress_cb:
        progress_cb("Detecting speech segments...")

    segments = analyze_speech_segments(audio)

    if not segments:
        return []

    # Transcribe each segment
    timeline = []
    for i, (start, end) in enumerate(segments):
        if progress_cb:
            progress_cb(f"Recognizing speech segment {i+1}/{len(segments)}...")

        text = _transcribe_segment(audio, start, end)
        if text:
            timeline.append({"time": round(start, 1), "text": text})

    # Write to cache
    if cached_timelines is not None:
        cached_timelines[fingerprint] = timeline

    if progress_cb:
        progress_cb(f"Generated {len(timeline)} subtitle(s)")

    return timeline


def align_timeline_to_text(
    audio_path: str,
    subtitle_lines: list[str],
    progress_cb: Callable[[str], None] | None = None,
) -> list[dict]:
    """
    Align user-provided subtitle text with VAD-detected speech segment timeline.

    Workflow:
    1. VAD detects speech segments
    2. Match subtitle line count with speech segment count
    3. If subtitle lines < speech segments, merge excess speech segments
    4. If subtitle lines > speech segments, distribute time proportionally
    5. Return the aligned timeline

    Args:
        audio_path:     Path to the audio file
        subtitle_lines: User-provided list of subtitle text lines
        progress_cb:    Progress callback

    Returns:
        [{"time": float, "text": str}, ...]
    """
    if not subtitle_lines:
        return []

    if progress_cb:
        progress_cb("Loading audio...")

    audio = AudioSegment.from_file(audio_path)

    if progress_cb:
        progress_cb("Detecting speech segments...")

    segments = analyze_speech_segments(audio)

    if not segments:
        # No speech segments detected, distribute evenly
        total_ms = len(audio)
        interval = total_ms / len(subtitle_lines)
        return [
            {"time": round(i * interval / 1000 + 0.3, 1), "text": line}
            for i, line in enumerate(subtitle_lines)
        ]

    if progress_cb:
        progress_cb(f"Detected {len(segments)} speech segment(s), aligning {len(subtitle_lines)} subtitle(s)...")

    # Subtitle lines == speech segments: direct one-to-one mapping
    if len(subtitle_lines) == len(segments):
        return [
            {"time": round(start + 0.2, 1), "text": line}
            for (start, _), line in zip(segments, subtitle_lines)
        ]

    # Subtitle lines < speech segments: merge excess speech segments into the last subtitle line
    if len(subtitle_lines) < len(segments):
        timeline = []
        for i, line in enumerate(subtitle_lines):
            if i < len(segments):
                start = segments[i][0]
                timeline.append({"time": round(start + 0.2, 1), "text": line})
        return timeline

    # Subtitle lines > speech segments: evenly distribute excess subtitles into the last speech segment
    timeline = []
    seg_idx = 0
    for i, line in enumerate(subtitle_lines):
        if seg_idx < len(segments) - 1:
            # Earlier speech segments map one-to-one
            start = segments[seg_idx][0]
            timeline.append({"time": round(start + 0.2, 1), "text": line})
            seg_idx += 1
        else:
            # Evenly distribute remaining subtitles within the last speech segment
            remaining = len(subtitle_lines) - i
            seg_start, seg_end = segments[-1]
            seg_duration = seg_end - seg_start
            interval = seg_duration / remaining
            offset = (i - seg_idx) * interval
            timeline.append({"time": round(seg_start + offset + 0.2, 1), "text": line})

    return timeline
