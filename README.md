<p align="center">
  <img src="assets/Logo.png" alt="MelodyClip Logo" width="200">
</p>

<h1 align="center">MelodyClip</h1>

<p align="center">
  <strong>Automated Short Video Generator for Music Sharing</strong><br>
  Batch-generate song-sharing clips for Douyin, TikTok, and other short-video platforms — no editing skills required
</p>

<p align="center">
  <a href="README_zh-CN.md">简体中文</a> · <a href="README_zh-TW.md">繁體中文</a>
</p>

---

## Table of Contents

- [Introduction](#introduction)
- [Key Features](#key-features)
- [Video Structure](#video-structure)
- [Project Structure](#project-structure)
- [Requirements](#requirements)
- [Installation](#installation)
- [Usage](#usage)
- [Configuration](#configuration)
- [Building a Standalone Executable](#building-a-standalone-executable)
- [FAQ](#faq)
- [License](#license)

## Introduction

**MelodyClip** is a desktop application that automates the creation of short music-sharing videos. It is designed for content creators who need to produce consistent, high-quality "classic song sharing" videos at scale for platforms like Douyin (抖音), TikTok, WeChat Video Channels (视频号), and similar short-video services.

With MelodyClip, you simply provide your song files, choose a background video, and click **Generate**. The tool handles everything else: audio stitching, subtitle generation via speech recognition, text overlays, background video looping, and final rendering — all in one automated pipeline.

**One video in under 60 seconds. Batch processing for an entire folder. Zero video-editing knowledge needed.**

## Key Features

- **One-Click Generation** — Fill in parameters, select files, and hit generate. Three steps for a single video; two steps for batch mode.
- **Batch Processing** — Point to a folder of audio files and generate all videos in one run.
- **Auto Subtitles** — Built-in speech recognition automatically generates timed subtitles for intro and outro segments.
- **Flexible Background** — Use a single fixed video or a folder of clips with sequential or random selection.
- **Customizable Text Overlays** — Top banner text, bottom disclaimer text, and centered subtitles with full control over font, size, color, and stroke.
- **Multi-Resolution Support** — 9:16 vertical (1080×1920, default), 16:9 horizontal (1920×1080), and 1:1 square (1080×1080).
- **Configurable Audio Segments** — Enable/disable intro, guide, and outro audio independently. Each has its own subtitle timeline.
- **Cross-Platform Packaging** — Build a standalone Windows executable with PyInstaller for distribution without Python.
- **PySide6 GUI** — Clean, native-looking desktop interface with real-time preview of settings.

## Video Structure

Each generated video follows a layered timeline:

```
[0s ──────────── ~18s ──────────────────── ~55s ── ~60s]
  |← Intro (voice + subtitles) →|←  Main Song  →|← Outro →|
```

| Segment | Duration | Description |
|---------|----------|-------------|
| **Background** | Full duration | Looping background video (muted), covers entire timeline |
| **Intro Audio** | ~15–20s | Pre-recorded voice intro + optional shop/subscription CTA |
| **Guide Audio** | ~3–5s | Optional secondary CTA ("check out my other videos") |
| **Main Song** | ~40–45s | The featured song, extracted from MP3 or MP4 |
| **Outro Audio** | ~5–8s | Optional closing voice with engagement CTA |

All segments except the background are independently toggleable. Subtitles for each segment are driven by timestamp templates in `config.json`.

## Project Structure

```
MelodyClip/
├── main.py              # PySide6 application entry point
├── run.py               # Dependency checker + launcher
├── config.json          # All user-configurable settings
├── requirements.txt     # Python dependencies
├── build.spec           # PyInstaller build specification
├── installer.iss        # Inno Setup script for Windows installer
├── start.bat            # Windows quick-start batch file
├── core/                # Video/audio processing engine
│   ├── audio_builder.py     # Audio stitching (intro + guide + song + outro)
│   ├── video_builder.py     # Video composition and final rendering
│   ├── subtitle_builder.py  # Auto-subtitle generation via speech recognition
│   ├── speech_analyzer.py   # Speech-to-text analysis
│   └── text_overlay.py      # Text rendering (top/bottom banners, subtitles)
├── gui/                 # PySide6 GUI layer
│   ├── app.py               # Main window
│   ├── settings_dialog.py   # Settings dialog (all config options)
│   └── widgets.py           # Custom UI widgets
├── utils/               # Shared utilities
│   ├── config_manager.py    # Config read/write manager
│   ├── file_utils.py        # File paths, temp cleanup, resource resolution
│   └── font_utils.py        # Font discovery and loading
├── ffmpeg/              # Bundled FFmpeg binaries (for packaging)
└── assets/              # Static assets (logo, etc.)
```

## Requirements

- **Python** 3.10+
- **FFmpeg** — bundled in the `ffmpeg/` directory for Windows packaging, or installable via system package manager on macOS/Linux
- **OS** — Windows 10/11 (primary), macOS (development), Linux (untested)

## Installation

### From Source

```bash
# Clone the repository
git clone https://github.com/your-username/MelodyClip.git
cd MelodyClip

# Create a virtual environment
python -m venv .venv
source .venv/bin/activate  # macOS/Linux
# .venv\Scripts\activate   # Windows

# Install dependencies
pip install -r requirements.txt
```

### Quick Start (Windows)

Double-click `start.bat` — it will auto-install missing dependencies and launch the GUI.

## Usage

### Single Video Generation

1. Launch the application: `python run.py`
2. Click **Select Song** and choose an MP3 or MP4 file
3. Configure background, text, and audio settings in the **Settings** dialog
4. Click **Generate** — the video will be saved to the configured output folder

### Batch Generation

1. Click **Select Folder** and choose a directory containing audio files
2. Click **Generate All** — MelodyClip will process every audio file in the folder
3. Output files are named using the template in `config.json` (default: `歌曲分享_{song_name}`)

### Via Command Line

```python
from main import main
main()
```

## Configuration

All settings are stored in `config.json`. Key options:

| Section | Options |
|---------|---------|
| **Audio** | `intro_audio`, `guide_audio`, `outro_audio`, `enable_intro`, `enable_guide`, `enable_outro` |
| **Subtitles** | `enable_intro_subtitles`, `enable_outro_subtitles`, `enable_guide_subtitles`, `subtitle_size`, `subtitle_font`, `subtitle_color` |
| **Background** | `background_mode` (fixed/folder), `background_file`, `background_folder`, `background_select_strategy` (sequential/random) |
| **Text Overlay** | `top_text_template`, `bottom_text`, font/color/stroke settings for each |
| **Video Output** | `output_resolution`, `fps`, `bitrate`, `output_folder`, `output_filename_template` |
| **Song Trim** | `trim_mode` (fixed/manual), `trim_duration`, `slice_interval`, `manual_start` |
| **Subtitle Timelines** | `timeline_templates` — per-audio-file timestamp arrays mapping time → subtitle text |

### Subtitle Timeline Format

Each audio file can have its own subtitle timeline in `config.json`:

```json
{
  "timeline_templates": {
    "intro.mp3": [
      { "time": 0.5, "text": "This song is amazing" },
      { "time": 2.3, "text": "I love it so much" }
    ]
  }
}
```

## Building a Standalone Executable

```bash
# Install PyInstaller
pip install pyinstaller

# Build using the provided spec file
pyinstaller build.spec
```

The output executable will be in the `dist/` directory. For a full Windows installer, use the provided `installer.iss` with [Inno Setup](https://jrsoftware.org/isinfo.php).

## FAQ

**Q: What audio formats are supported?**
A: MP3 and MP4. If you provide an MP4 file, MelodyClip automatically extracts the audio track.

**Q: Can I use my own fonts?**
A: Yes. Place your `.ttf` or `.ttc` font file in the project directory and update the font name in `config.json`.

**Q: How long does it take to generate one video?**
A: Typically under 60 seconds on a modern machine, depending on video resolution and length.

**Q: Does it work on macOS?**
A: Yes, the application runs on macOS for development. The primary target platform is Windows.

**Q: Can I customize the video resolution?**
A: Yes. Set `output_resolution` in `config.json` to any `[width, height]` pair. Common presets: `[1080, 1920]` (vertical), `[1920, 1080]` (horizontal), `[1080, 1080]` (square).

## License

This project is open source. See the [LICENSE](LICENSE) file for details.
