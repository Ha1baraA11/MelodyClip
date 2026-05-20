<p align="center">
  <img src="assets/Logo.png" alt="MelodyClip Logo" width="200">
</p>

<h1 align="center">MelodyClip</h1>

<p align="center">
  <strong>自動化歌曲分享短影片生成工具</strong><br>
  批次生成抖音、視頻號等平台的歌曲分享影片 — 無需任何剪輯技能
</p>

<p align="center">
  <a href="README.md">English</a> · <a href="README_zh-CN.md">简体中文</a>
</p>

---

## 目錄

- [專案簡介](#專案簡介)
- [核心功能](#核心功能)
- [影片結構](#影片結構)
- [專案結構](#專案結構)
- [環境需求](#環境需求)
- [安裝方式](#安裝方式)
- [使用方法](#使用方法)
- [設定說明](#設定說明)
- [打包為獨立程式](#打包為獨立程式)
- [常見問題](#常見問題)
- [授權條款](#授權條款)

## 專案簡介

**MelodyClip** 是一款桌面應用程式，專為需要在短影片平台（抖音、視頻號、快手等）持續發布「經典老歌分享」類內容的創作者設計。它將音訊拼接、語音辨識字幕生成、文字疊加、背景影片循環和最終渲染整合到一條自動化流水線中。

你只需提供歌曲檔案、選擇背景影片，點擊**生成**按鈕即可。單個影片生成耗時不超過 60 秒，支援整個資料夾批次處理，零影片剪輯經驗即可上手。

## 核心功能

- **一鍵生成** — 填參數、選檔案、點生成，三步完成單個影片；批次模式兩步搞定
- **批次處理** — 選擇一個音訊資料夾，一次生成所有影片
- **自動字幕** — 內建語音辨識，自動生成開頭語和結尾語的同步字幕
- **靈活背景** — 支援固定影片或素材資料夾（順序循環 / 隨機選取）
- **自訂文字疊加** — 頂部橫幅、底部聲明、置中字幕，字型、大小、顏色、描邊全部可調
- **多解析度支援** — 9:16 直式（1080×1920，預設）、16:9 橫式（1920×1080）、1:1 方形（1080×1080）
- **獨立控制各音訊段** — 開頭語、引導語、結尾語均可獨立開關，各有獨立字幕時間軸
- **跨平台打包** — 使用 PyInstaller 打包為 Windows 獨立可執行檔，無需安裝 Python
- **PySide6 圖形介面** — 原生風格桌面介面，設定項即時預覽

## 影片結構

每個生成的影片遵循以下時間軸分層結構：

```
[0s ──────────── ~18s ──────────────────── ~55s ── ~60s]
  |←   開頭段（語音+字幕）  →|←   歌曲播放段   →|← 結尾語 →|
```

| 分段 | 時長 | 說明 |
|------|------|------|
| **背景層** | 全程 | 循環播放的背景影片（靜音），覆蓋整個時間軸 |
| **開頭語音** | ~15–20秒 | 預錄製的開頭語 + 可選的櫥窗/關注引導 |
| **引導語音** | ~3–5秒 | 可選的二次引導語（「逛逛我的其他影片」） |
| **歌曲播放** | ~40–45秒 | 當期分享的歌曲，從 MP3 或 MP4 中提取 |
| **結尾語音** | ~5–8秒 | 可選的結束語，含互動引導 |

除背景層外，所有分段均可獨立開關。每個分段的字幕由 `config.json` 中的時間戳範本驅動。

## 專案結構

```
MelodyClip/
├── main.py              # PySide6 程式主入口
├── run.py               # 相依性偵測 + 啟動器
├── config.json          # 所有使用者可設定項
├── requirements.txt     # Python 相依套件清單
├── build.spec           # PyInstaller 打包設定
├── installer.iss        # Inno Setup 安裝包腳本
├── start.bat            # Windows 快速啟動批次檔
├── core/                # 影片/音訊處理引擎
│   ├── audio_builder.py     # 音訊拼接（開頭語+引導語+歌曲+結尾語）
│   ├── video_builder.py     # 影片合成與最終渲染
│   ├── subtitle_builder.py  # 語音辨識自動生成字幕
│   ├── speech_analyzer.py   # 語音轉文字分析
│   └── text_overlay.py      # 文字渲染（頂部/底部橫幅、字幕）
├── gui/                 # PySide6 介面層
│   ├── app.py               # 主視窗
│   ├── settings_dialog.py   # 設定對話框（全部設定項）
│   └── widgets.py           # 自訂介面元件
├── utils/               # 通用工具
│   ├── config_manager.py    # 設定讀寫管理器
│   ├── file_utils.py        # 檔案路徑、暫存檔清理、資源定位
│   └── font_utils.py        # 字型發現與載入
├── ffmpeg/              # 內建 FFmpeg 二進位檔（打包用）
└── assets/              # 靜態資源（Logo 等）
```

## 環境需求

- **Python** 3.10+
- **FFmpeg** — Windows 打包時內建在 `ffmpeg/` 目錄中；macOS/Linux 需透過系統套件管理器安裝
- **作業系統** — Windows 10/11（主要目標），macOS（開發環境），Linux（未測試）

## 安裝方式

### 從原始碼安裝

```bash
# 複製倉庫
git clone https://github.com/your-username/MelodyClip.git
cd MelodyClip

# 建立虛擬環境
python -m venv .venv
source .venv/bin/activate  # macOS/Linux
# .venv\Scripts\activate   # Windows

# 安裝相依套件
pip install -r requirements.txt
```

### Windows 快速啟動

雙擊 `start.bat`，它會自動安裝缺失的相依套件並啟動圖形介面。

## 使用方法

### 單個影片生成

1. 啟動程式：`python run.py`
2. 點擊 **選擇歌曲**，選擇一個 MP3 或 MP4 檔案
3. 在 **設定** 對話框中配置背景、文字和音訊選項
4. 點擊 **生成** — 影片將儲存到設定的輸出資料夾

### 批次生成

1. 點擊 **選擇資料夾**，選擇包含音訊檔案的目錄
2. 點擊 **全部生成** — MelodyClip 將處理該資料夾中的所有音訊檔案
3. 輸出檔案按 `config.json` 中的範本命名（預設：`歌曲分享_{song_name}`）

### 命令列呼叫

```python
from main import main
main()
```

## 設定說明

所有設定儲存在 `config.json` 中，主要設定項：

| 分類 | 設定項 |
|------|--------|
| **音訊** | `intro_audio`、`guide_audio`、`outro_audio`、`enable_intro`、`enable_guide`、`enable_outro` |
| **字幕** | `enable_intro_subtitles`、`enable_outro_subtitles`、`enable_guide_subtitles`、`subtitle_size`、`subtitle_font`、`subtitle_color` |
| **背景** | `background_mode`（fixed/folder）、`background_file`、`background_folder`、`background_select_strategy`（sequential/random） |
| **文字疊加** | `top_text_template`、`bottom_text`、各處字型/顏色/描邊設定 |
| **影片輸出** | `output_resolution`、`fps`、`bitrate`、`output_folder`、`output_filename_template` |
| **歌曲裁剪** | `trim_mode`（fixed/manual）、`trim_duration`、`slice_interval`、`manual_start` |
| **字幕時間軸** | `timeline_templates` — 每個音訊檔案對應的時間戳陣列，格式為 time → text |

### 字幕時間軸格式

每個音訊檔案可在 `config.json` 中配置獨立的字幕時間軸：

```json
{
  "timeline_templates": {
    "開頭.mp3": [
      { "time": 0.5, "text": "這首歌真的太好聽了" },
      { "time": 2.3, "text": "我非常喜歡" }
    ]
  }
}
```

## 打包為獨立程式

```bash
# 安裝 PyInstaller
pip install pyinstaller

# 使用提供的 spec 檔案打包
pyinstaller build.spec
```

輸出的可執行檔位於 `dist/` 目錄。如需製作完整的 Windows 安裝包，可使用 `installer.iss` 配合 [Inno Setup](https://jrsoftware.org/isinfo.php)。

## 常見問題

**Q: 支援哪些音訊格式？**
A: MP3 和 MP4。如果提供 MP4 檔案，MelodyClip 會自動提取音訊軌。

**Q: 可以使用自訂字型嗎？**
A: 可以。將 `.ttf` 或 `.ttc` 字型檔案放在專案目錄中，然後在 `config.json` 中更新字型名稱即可。

**Q: 生成一個影片需要多長時間？**
A: 在現代硬體上通常不超過 60 秒，具體取決於影片解析度和時長。

**Q: 支援 macOS 嗎？**
A: 支援，程式可在 macOS 上執行開發。主要目標平台為 Windows。

**Q: 可以自訂影片解析度嗎？**
A: 可以。在 `config.json` 中設定 `output_resolution` 為任意 `[寬, 高]` 組合。常用預設：`[1080, 1920]`（直式）、`[1920, 1080]`（橫式）、`[1080, 1080]`（方形）。

## 授權條款

本專案為開源專案。詳見 [LICENSE](LICENSE) 檔案。
