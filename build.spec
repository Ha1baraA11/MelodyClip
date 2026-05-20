# -*- mode: python ; coding: utf-8 -*-
"""
build.spec — PyInstaller 打包配置

打包命令：
    pyinstaller build.spec

输出目录：dist/SongShareTool/
"""

from pathlib import Path
from PyInstaller.utils.hooks import copy_metadata

block_cipher = None

# 数据文件：(源路径, 目标目录)
added_files = [
    ("assets/Logo.png",                "assets"),
    ("开头(含橱窗引导).mp3",           "."),
    ("开头(不含橱窗引导).mp3",         "."),
    ("结尾(含橱窗引导).mp3",           "."),
    ("引导语.mp3",                      "."),
    ("也字工厂润圆体.TTF",             "."),
]

# 添加包元数据（PyInstaller 不会自动收集 importlib.metadata 需要的数据）
added_files += copy_metadata('imageio')
added_files += copy_metadata('moviepy')
added_files += copy_metadata('proglog')

# 如果本地存在 ffmpeg 目录，也打包进去
ffmpeg_dir = Path("ffmpeg")
if ffmpeg_dir.exists():
    for exe in ffmpeg_dir.glob("*.exe"):
        added_files.append((str(exe), "ffmpeg"))

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=[],
    datas=added_files,
    hiddenimports=[
        "pydub",
        "PIL",
        "moviepy",
        "moviepy.video.fx",
        "moviepy.video.fx.all",
        "moviepy.audio.fx",
        "moviepy.audio.fx.all",
        "imageio",
        "imageio_ffmpeg",
        "speech_recognition",
        "PySide6.QtCore",
        "PySide6.QtWidgets",
        "PySide6.QtGui",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tkinter",
        "matplotlib",
        "scipy",
        "notebook",
        "jupyter",
        "IPython",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="SongShareTool",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,           # 无控制台窗口（GUI 模式）
    # icon="assets/icon.ico",  # TODO: 需要 .ico 格式文件
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="SongShareTool",
)
