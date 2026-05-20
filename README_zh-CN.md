<p align="center">
  <img src="assets/Logo.png" alt="MelodyClip Logo" width="200">
</p>

<h1 align="center">MelodyClip</h1>

<p align="center">
  <strong>自动化歌曲分享短视频生成工具</strong><br>
  批量生成抖音、视频号等平台的歌曲分享视频 — 无需任何剪辑技能
</p>

<p align="center">
  <a href="README.md">English</a> · <a href="README_zh-TW.md">繁體中文</a>
</p>

---

## 目录

- [项目简介](#项目简介)
- [核心功能](#核心功能)
- [视频结构](#视频结构)
- [项目结构](#项目结构)
- [环境要求](#环境要求)
- [安装方式](#安装方式)
- [使用方法](#使用方法)
- [配置说明](#配置说明)
- [打包为独立程序](#打包为独立程序)
- [常见问题](#常见问题)
- [许可证](#许可证)

## 项目简介

**MelodyClip** 是一款桌面应用，专为需要在短视频平台（抖音、视频号、快手等）持续发布"经典老歌分享"类内容的创作者设计。它将音频拼接、语音识别字幕生成、文字叠加、背景视频循环和最终渲染整合到一条自动化流水线中。

你只需提供歌曲文件、选择背景视频，点击**生成**按钮即可。单个视频生成耗时不超过 60 秒，支持整个文件夹批量处理，零视频剪辑经验即可上手。

## 核心功能

- **一键生成** — 填参数、选文件、点生成，三步完成单个视频；批量模式两步搞定
- **批量处理** — 选择一个音频文件夹，一次性生成所有视频
- **自动字幕** — 内置语音识别，自动生成开头语和结尾语的同步字幕
- **灵活背景** — 支持固定视频或素材文件夹（顺序循环 / 随机选取）
- **自定义文字叠加** — 顶部横幅、底部声明、居中字幕，字体、大小、颜色、描边全部可调
- **多分辨率支持** — 9:16 竖屏（1080×1920，默认）、16:9 横屏（1920×1080）、1:1 方形（1080×1080）
- **独立控制各音频段** — 开头语、引导语、结尾语均可独立开关，各有独立字幕时间线
- **跨平台打包** — 使用 PyInstaller 打包为 Windows 独立可执行文件，无需安装 Python
- **PySide6 图形界面** — 原生风格桌面界面，设置项实时预览

## 视频结构

每个生成的视频遵循以下时间轴分层结构：

```
[0s ──────────── ~18s ──────────────────── ~55s ── ~60s]
  |←   开头段（语音+字幕）  →|←   歌曲播放段   →|← 结尾语 →|
```

| 分段 | 时长 | 说明 |
|------|------|------|
| **背景层** | 全程 | 循环播放的背景视频（静音），覆盖整个时间轴 |
| **开头语音** | ~15–20秒 | 预录制的开头语 + 可选的橱窗/关注引导 |
| **引导语音** | ~3–5秒 | 可选的二次引导语（"逛逛我的其他视频"） |
| **歌曲播放** | ~40–45秒 | 当期分享的歌曲，从 MP3 或 MP4 中提取 |
| **结尾语音** | ~5–8秒 | 可选的结束语，含互动引导 |

除背景层外，所有分段均可独立开关。每个分段的字幕由 `config.json` 中的时间戳模板驱动。

## 项目结构

```
MelodyClip/
├── main.py              # PySide6 程序主入口
├── run.py               # 依赖检测 + 启动器
├── config.json          # 所有用户可配置项
├── requirements.txt     # Python 依赖列表
├── build.spec           # PyInstaller 打包配置
├── installer.iss        # Inno Setup 安装包脚本
├── start.bat            # Windows 快速启动批处理
├── core/                # 视频/音频处理引擎
│   ├── audio_builder.py     # 音频拼接（开头语+引导语+歌曲+结尾语）
│   ├── video_builder.py     # 视频合成与最终渲染
│   ├── subtitle_builder.py  # 语音识别自动生成字幕
│   ├── speech_analyzer.py   # 语音转文字分析
│   └── text_overlay.py      # 文字渲染（顶部/底部横幅、字幕）
├── gui/                 # PySide6 界面层
│   ├── app.py               # 主窗口
│   ├── settings_dialog.py   # 设置对话框（全部配置项）
│   └── widgets.py           # 自定义界面组件
├── utils/               # 通用工具
│   ├── config_manager.py    # 配置读写管理器
│   ├── file_utils.py        # 文件路径、临时文件清理、资源定位
│   └── font_utils.py        # 字体发现与加载
├── ffmpeg/              # 内置 FFmpeg 二进制（打包用）
└── assets/              # 静态资源（Logo 等）
```

## 环境要求

- **Python** 3.10+
- **FFmpeg** — Windows 打包时内置在 `ffmpeg/` 目录中；macOS/Linux 需通过系统包管理器安装
- **操作系统** — Windows 10/11（主要目标），macOS（开发环境），Linux（未测试）

## 安装方式

### 从源码安装

```bash
# 克隆仓库
git clone https://github.com/your-username/MelodyClip.git
cd MelodyClip

# 创建虚拟环境
python -m venv .venv
source .venv/bin/activate  # macOS/Linux
# .venv\Scripts\activate   # Windows

# 安装依赖
pip install -r requirements.txt
```

### Windows 快速启动

双击 `start.bat`，它会自动安装缺失的依赖并启动图形界面。

## 使用方法

### 单个视频生成

1. 启动程序：`python run.py`
2. 点击 **选择歌曲**，选择一个 MP3 或 MP4 文件
3. 在 **设置** 对话框中配置背景、文字和音频选项
4. 点击 **生成** — 视频将保存到配置的输出文件夹

### 批量生成

1. 点击 **选择文件夹**，选择包含音频文件的目录
2. 点击 **全部生成** — MelodyClip 将处理该文件夹中的所有音频文件
3. 输出文件按 `config.json` 中的模板命名（默认：`歌曲分享_{song_name}`）

### 命令行调用

```python
from main import main
main()
```

## 配置说明

所有设置存储在 `config.json` 中，主要配置项：

| 分类 | 配置项 |
|------|--------|
| **音频** | `intro_audio`、`guide_audio`、`outro_audio`、`enable_intro`、`enable_guide`、`enable_outro` |
| **字幕** | `enable_intro_subtitles`、`enable_outro_subtitles`、`enable_guide_subtitles`、`subtitle_size`、`subtitle_font`、`subtitle_color` |
| **背景** | `background_mode`（fixed/folder）、`background_file`、`background_folder`、`background_select_strategy`（sequential/random） |
| **文字叠加** | `top_text_template`、`bottom_text`、各处字体/颜色/描边设置 |
| **视频输出** | `output_resolution`、`fps`、`bitrate`、`output_folder`、`output_filename_template` |
| **歌曲裁剪** | `trim_mode`（fixed/manual）、`trim_duration`、`slice_interval`、`manual_start` |
| **字幕时间线** | `timeline_templates` — 每个音频文件对应的时间戳数组，格式为 time → text |

### 字幕时间线格式

每个音频文件可在 `config.json` 中配置独立的字幕时间线：

```json
{
  "timeline_templates": {
    "开头.mp3": [
      { "time": 0.5, "text": "这首歌真的太好听了" },
      { "time": 2.3, "text": "我非常喜欢" }
    ]
  }
}
```

## 打包为独立程序

```bash
# 安装 PyInstaller
pip install pyinstaller

# 使用提供的 spec 文件打包
pyinstaller build.spec
```

输出的可执行文件位于 `dist/` 目录。如需制作完整的 Windows 安装包，可使用 `installer.iss` 配合 [Inno Setup](https://jrsoftware.org/isinfo.php)。

## 常见问题

**Q: 支持哪些音频格式？**
A: MP3 和 MP4。如果提供 MP4 文件，MelodyClip 会自动提取音频轨。

**Q: 可以使用自定义字体吗？**
A: 可以。将 `.ttf` 或 `.ttc` 字体文件放在项目目录中，然后在 `config.json` 中更新字体名称即可。

**Q: 生成一个视频需要多长时间？**
A: 在现代硬件上通常不超过 60 秒，具体取决于视频分辨率和时长。

**Q: 支持 macOS 吗？**
A: 支持，程序可在 macOS 上运行开发。主要目标平台为 Windows。

**Q: 可以自定义视频分辨率吗？**
A: 可以。在 `config.json` 中设置 `output_resolution` 为任意 `[宽, 高]` 组合。常用预设：`[1080, 1920]`（竖屏）、`[1920, 1080]`（横屏）、`[1080, 1080]`（方形）。

## 许可证

本项目为开源项目。详见 [LICENSE](LICENSE) 文件。
