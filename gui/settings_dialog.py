"""
settings_dialog.py — Settings dialog

6 QGroupBox sections:
1. Audio Settings (intro/guide voice, silence gap, fadeout)
2. Audio Trimming (three modes + parameters)
3. Background Video (fixed/folder + strategy + asset list)
4. Output Settings (folder/filename template/resolution/fps/bitrate)
5. Text Style (top banner/bottom disclaimer/subtitle style)
6. Default Subtitles (QTableWidget editor)

Bottom: [Reset to Defaults] [Cancel] [Save]
"""

from pathlib import Path

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QScrollArea, QWidget,
    QGroupBox, QLabel, QLineEdit, QPushButton, QRadioButton,
    QButtonGroup, QSpinBox, QDoubleSpinBox, QCheckBox,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QMessageBox, QAbstractItemView, QSizePolicy,
    QStackedWidget, QFrame, QFileDialog, QComboBox,
    QTextEdit,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

from gui.widgets import FileSelectWidget, ColorButton
from utils.config_manager import config, DEFAULTS
from utils.font_utils import get_font_warning


class SubtitleInputDialog(QDialog):
    """Subtitle text input dialog for timeline alignment of local audio files."""

    def __init__(self, audio_filename: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Enter Subtitle Text")
        self.setMinimumWidth(400)
        self.setModal(True)

        layout = QVBoxLayout(self)

        label = QLabel(f"Enter subtitle content for \"{audio_filename}\":\nOne subtitle per line. The system will automatically align the timeline.")
        label.setWordWrap(True)
        layout.addWidget(label)

        self.text_edit = QTextEdit()
        self.text_edit.setPlaceholderText("One subtitle per line\nExample:\nListening to music\nYou can also browse my profile page\nThere are great items to share")
        self.text_edit.setMinimumHeight(150)
        layout.addWidget(self.text_edit)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_cancel = QPushButton("Cancel")
        btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(btn_cancel)
        btn_ok = QPushButton("OK")
        btn_ok.setDefault(True)
        btn_ok.clicked.connect(self._on_ok)
        btn_row.addWidget(btn_ok)
        layout.addLayout(btn_row)

    def _on_ok(self):
        if not self.get_lines():
            QMessageBox.warning(self, "Notice", "Please enter at least one subtitle.")
            return
        self.accept()

    def get_lines(self) -> list[str]:
        return [line.strip() for line in self.text_edit.toPlainText().strip().splitlines() if line.strip()]


class SettingsDialog(QDialog):
    """
    Settings dialog (modal).
    Loads current config on open;
    writes back to config and calls config.save() on "Save".
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setFixedWidth(580)
        self.setMinimumHeight(500)
        self.setMaximumHeight(800)
        self.setModal(True)

        self._build_ui()
        self._load_from_config()

        # Font warning
        warning = get_font_warning()
        if warning:
            QMessageBox.warning(self, "Font Notice", warning)

    # ─── UI construction ──────────────────────────────────────────────────────

    def _build_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(12, 12, 12, 12)
        root_layout.setSpacing(8)

        # ── Scroll area ─────────────────────────────────────────────────────
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        root_layout.addWidget(scroll)

        content = QWidget()
        scroll.setWidget(content)
        content_layout = QVBoxLayout(content)
        content_layout.setSpacing(10)
        content_layout.setContentsMargins(4, 4, 4, 4)

        content_layout.addWidget(self._build_group1_audio())
        content_layout.addWidget(self._build_group2_trim())
        content_layout.addWidget(self._build_group3_background())
        content_layout.addWidget(self._build_group4_output())
        content_layout.addWidget(self._build_group5_style())
        content_layout.addWidget(self._build_group6_subtitles())
        content_layout.addStretch()

        # ── Bottom buttons ────────────────────────────────────────────────────
        btn_layout = QHBoxLayout()
        btn_layout.setContentsMargins(0, 4, 0, 0)

        self.btn_reset = QPushButton("Reset to Defaults")
        self.btn_reset.clicked.connect(self._on_reset)
        btn_layout.addWidget(self.btn_reset)

        btn_layout.addStretch()

        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(self.btn_cancel)

        self.btn_save = QPushButton("Save")
        self.btn_save.setDefault(True)
        self.btn_save.clicked.connect(self._on_save)
        btn_layout.addWidget(self.btn_save)

        root_layout.addLayout(btn_layout)

    # ─── Group 1: Audio Settings ─────────────────────────────────────────────

    def _scan_project_mp3s(self) -> list[str]:
        """Scan all MP3 files in the project directory."""
        from utils.file_utils import get_resource_path
        base = Path(get_resource_path("."))
        return sorted([f.name for f in base.glob("*.mp3")])

    _LOCAL_FILE_TAG = "__local_file__"

    def _build_group1_audio(self) -> QGroupBox:
        box = QGroupBox("Audio Settings")
        layout = QVBoxLayout(box)
        layout.setSpacing(6)

        mp3_files = self._scan_project_mp3s()

        # Intro voice
        row1 = QHBoxLayout()
        self.enable_intro = QCheckBox("Intro Voice")
        self.enable_intro.setChecked(True)
        row1.addWidget(self.enable_intro)
        self.intro_audio = QComboBox()
        self.intro_audio.addItem("(Default: 开头(含橱窗引导).mp3)", "")
        for f in mp3_files:
            if "开头" in f:
                self.intro_audio.addItem(f, f)
        self.intro_audio.addItem("Browse local file...", self._LOCAL_FILE_TAG)
        self.intro_audio.currentIndexChanged.connect(
            lambda idx: self._on_audio_combo_changed(self.intro_audio, idx, "intro")
        )
        row1.addWidget(self.intro_audio)
        layout.addLayout(row1)

        # Guide voice
        row_guide = QHBoxLayout()
        self.enable_guide = QCheckBox("Guide Voice")
        self.enable_guide.setChecked(True)
        row_guide.addWidget(self.enable_guide)
        self.guide_audio = QComboBox()
        self.guide_audio.addItem("(Default: 引导语.mp3)", "")
        for f in mp3_files:
            if "引导" in f:
                self.guide_audio.addItem(f, f)
        self.guide_audio.addItem("Browse local file...", self._LOCAL_FILE_TAG)
        self.guide_audio.currentIndexChanged.connect(
            lambda idx: self._on_audio_combo_changed(self.guide_audio, idx, "guide")
        )
        row_guide.addWidget(self.guide_audio)
        layout.addLayout(row_guide)

        # Outro voice
        row_outro = QHBoxLayout()
        self.enable_outro = QCheckBox("Outro Voice")
        self.enable_outro.setChecked(True)
        row_outro.addWidget(self.enable_outro)
        self.outro_audio = QComboBox()
        self.outro_audio.addItem("(Default: 结尾(含橱窗引导).mp3)", "")
        for f in mp3_files:
            if "结尾" in f:
                self.outro_audio.addItem(f, f)
        self.outro_audio.addItem("Browse local file...", self._LOCAL_FILE_TAG)
        self.outro_audio.currentIndexChanged.connect(
            lambda idx: self._on_audio_combo_changed(self.outro_audio, idx, "outro")
        )
        row_outro.addWidget(self.outro_audio)
        layout.addLayout(row_outro)

        # Silence gap + fadeout
        row3 = QHBoxLayout()
        row3.addWidget(QLabel("Silence gap:"))
        self.silence_gap = QDoubleSpinBox()
        self.silence_gap.setRange(0.0, 2.0)
        self.silence_gap.setSingleStep(0.1)
        self.silence_gap.setSuffix(" s")
        self.silence_gap.setFixedWidth(90)
        row3.addWidget(self.silence_gap)
        row3.addSpacing(20)
        row3.addWidget(QLabel("Fadeout:"))
        self.fadeout_duration = QDoubleSpinBox()
        self.fadeout_duration.setRange(0.0, 5.0)
        self.fadeout_duration.setSingleStep(0.5)
        self.fadeout_duration.setSuffix(" s")
        self.fadeout_duration.setFixedWidth(90)
        row3.addWidget(self.fadeout_duration)
        row3.addStretch()
        layout.addLayout(row3)

        return box

    def _on_audio_combo_changed(self, combo: QComboBox, index: int, audio_type: str):
        """Handle audio combo box selection change, triggered when 'Browse local file...' is selected."""
        if combo.currentData() != self._LOCAL_FILE_TAG:
            return

        path, _ = QFileDialog.getOpenFileName(
            self, f"Select {audio_type} audio file", "",
            "Audio Files (*.mp3 *.wav *.ogg *.flac);;All Files (*)"
        )
        if not path:
            combo.setCurrentIndex(0)
            return

        filename = Path(path).name
        # Check if already in the list
        for i in range(combo.count()):
            if combo.itemData(i) == path:
                combo.setCurrentIndex(i)
                return

        # Insert new option before "Browse local file..."
        insert_pos = combo.count() - 1
        combo.insertItem(insert_pos, f"[Local] {filename}", path)
        combo.setCurrentIndex(insert_pos)

        # Check if timeline template already exists (full path or filename)
        templates = config.get("timeline_templates", {})
        if path not in templates and filename not in templates:
            self._auto_align_timeline(path, filename)

    def _auto_align_timeline(self, audio_path: str, filename: str):
        """Auto-align timeline: prompt user for subtitles -> VAD alignment -> save to config."""
        reply = QMessageBox.question(
            self, "Timeline Alignment",
            f"\"{filename}\" does not have a subtitle timeline yet.\nWould you like to enter subtitles and auto-align now?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        dlg = SubtitleInputDialog(filename, self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        lines = dlg.get_lines()
        if not lines:
            return

        from core.speech_analyzer import align_timeline_to_text

        # Progress indicator
        progress = QMessageBox(self)
        progress.setWindowTitle("Aligning")
        progress.setText("Analyzing audio and aligning timeline...")
        progress.setStandardButtons(QMessageBox.StandardButton.NoButton)
        progress.show()

        try:
            timeline = align_timeline_to_text(audio_path, lines)
        except Exception as e:
            progress.close()
            QMessageBox.warning(self, "Alignment Failed", f"Timeline alignment failed: {e}")
            return

        progress.close()

        if timeline:
            # Save to config's timeline_templates (use full path as key)
            templates = config.get("timeline_templates", {})
            templates[audio_path] = timeline
            config.set("timeline_templates", templates)
            config.save()

            # Show result
            result_text = "\n".join(
                f"  {item['time']:.1f}s → {item['text']}" for item in timeline
            )
            QMessageBox.information(
                self, "Alignment Complete",
                f"Generated {len(timeline)} subtitles and saved:\n\n{result_text}"
            )
        else:
            QMessageBox.warning(self, "Alignment Failed", "No speech segments detected. Please check the audio file.")

    # ─── Group 2: Audio Trimming ─────────────────────────────────────────────

    def _build_group2_trim(self) -> QGroupBox:
        box = QGroupBox("Audio Trimming")
        layout = QVBoxLayout(box)
        layout.setSpacing(6)

        # Mode radio buttons
        mode_layout = QHBoxLayout()
        self.trim_group = QButtonGroup(self)
        self.rb_trim_fixed = QRadioButton("Fixed Duration")
        self.rb_trim_slice = QRadioButton("Interval Slicing")
        self.rb_trim_manual = QRadioButton("Manual")
        self.trim_group.addButton(self.rb_trim_fixed, 0)
        self.trim_group.addButton(self.rb_trim_slice, 1)
        self.trim_group.addButton(self.rb_trim_manual, 2)
        mode_layout.addWidget(self.rb_trim_fixed)
        mode_layout.addWidget(self.rb_trim_slice)
        mode_layout.addWidget(self.rb_trim_manual)
        mode_layout.addStretch()
        layout.addLayout(mode_layout)

        # Parameter stack
        self.trim_stack = QStackedWidget()
        layout.addWidget(self.trim_stack)

        # Page 0: Fixed duration
        p0 = QWidget()
        l0 = QHBoxLayout(p0)
        l0.setContentsMargins(0, 0, 0, 0)
        l0.addWidget(QLabel("Duration:"))
        self.trim_duration = QSpinBox()
        self.trim_duration.setRange(10, 300)
        self.trim_duration.setSuffix(" s")
        self.trim_duration.setFixedWidth(90)
        l0.addWidget(self.trim_duration)
        l0.addStretch()
        self.trim_stack.addWidget(p0)

        # Page 1: Interval slicing
        p1 = QWidget()
        l1 = QHBoxLayout(p1)
        l1.setContentsMargins(0, 0, 0, 0)
        l1.addWidget(QLabel("Interval:"))
        self.slice_interval = QSpinBox()
        self.slice_interval.setRange(10, 300)
        self.slice_interval.setSuffix(" s")
        self.slice_interval.setFixedWidth(90)
        l1.addWidget(self.slice_interval)
        l1.addStretch()
        self.trim_stack.addWidget(p1)

        # Page 2: Manual
        p2 = QWidget()
        l2 = QHBoxLayout(p2)
        l2.setContentsMargins(0, 0, 0, 0)
        l2.addWidget(QLabel("Start time:"))
        self.manual_start = QSpinBox()
        self.manual_start.setRange(0, 9999)
        self.manual_start.setSuffix(" s")
        self.manual_start.setFixedWidth(90)
        l2.addWidget(self.manual_start)
        l2.addSpacing(16)
        l2.addWidget(QLabel("Duration:"))
        self.manual_duration = QSpinBox()
        self.manual_duration.setRange(10, 300)
        self.manual_duration.setSuffix(" s")
        self.manual_duration.setFixedWidth(90)
        l2.addWidget(self.manual_duration)
        l2.addStretch()
        self.trim_stack.addWidget(p2)

        # Linking
        self.trim_group.idClicked.connect(self.trim_stack.setCurrentIndex)

        return box

    # ─── Group 3: Background Video ───────────────────────────────────────────

    def _build_group3_background(self) -> QGroupBox:
        box = QGroupBox("Background Video")
        layout = QVBoxLayout(box)
        layout.setSpacing(6)

        # Source mode
        src_layout = QHBoxLayout()
        self.bg_mode_group = QButtonGroup(self)
        self.rb_bg_fixed = QRadioButton("Fixed Video")
        self.rb_bg_folder = QRadioButton("Folder")
        self.bg_mode_group.addButton(self.rb_bg_fixed, 0)
        self.bg_mode_group.addButton(self.rb_bg_folder, 1)
        src_layout.addWidget(self.rb_bg_fixed)
        src_layout.addWidget(self.rb_bg_folder)
        src_layout.addStretch()
        layout.addLayout(src_layout)

        self.bg_stack = QStackedWidget()
        layout.addWidget(self.bg_stack)

        # Page 0: Fixed video
        p0 = QWidget()
        l0 = QHBoxLayout(p0)
        l0.setContentsMargins(0, 0, 0, 0)
        l0.addWidget(QLabel("Video file:"))
        self.bg_file = FileSelectWidget(
            mode="file",
            file_filter="Video Files (*.mp4 *.avi *.mov *.mkv)",
            placeholder="Select background video file",
        )
        l0.addWidget(self.bg_file)
        self.bg_stack.addWidget(p0)

        # Page 1: Folder
        p1 = QWidget()
        l1 = QVBoxLayout(p1)
        l1.setContentsMargins(0, 0, 0, 0)
        l1.setSpacing(6)

        folder_row = QHBoxLayout()
        folder_row.addWidget(QLabel("Folder:"))
        self.bg_folder = FileSelectWidget(
            mode="folder",
            placeholder="Select asset folder",
        )
        self.bg_folder.path_changed.connect(self._refresh_bg_list)
        folder_row.addWidget(self.bg_folder)
        l1.addLayout(folder_row)

        strategy_row = QHBoxLayout()
        strategy_row.addWidget(QLabel("Selection strategy:"))
        self.bg_strategy_group = QButtonGroup(self)
        self.rb_bg_seq = QRadioButton("Sequential")
        self.rb_bg_rand = QRadioButton("Random")
        self.bg_strategy_group.addButton(self.rb_bg_seq, 0)
        self.bg_strategy_group.addButton(self.rb_bg_rand, 1)
        strategy_row.addWidget(self.rb_bg_seq)
        strategy_row.addWidget(self.rb_bg_rand)
        strategy_row.addStretch()
        l1.addLayout(strategy_row)

        self.bg_list_table = QTableWidget(0, 3)
        self.bg_list_table.setHorizontalHeaderLabels(["#", "Filename", "Path"])
        self.bg_list_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.bg_list_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.bg_list_table.setMaximumHeight(120)
        l1.addWidget(self.bg_list_table)

        btn_refresh = QPushButton("Refresh List")
        btn_refresh.setFixedWidth(80)
        btn_refresh.clicked.connect(lambda: self._refresh_bg_list(self.bg_folder.get_path()))
        l1.addWidget(btn_refresh)
        self.bg_stack.addWidget(p1)

        self.bg_mode_group.idClicked.connect(self.bg_stack.setCurrentIndex)

        return box

    def _refresh_bg_list(self, folder_path: str):
        self.bg_list_table.setRowCount(0)
        if not folder_path:
            return
        folder = Path(folder_path)
        if not folder.exists():
            return
        exts = {".mp4", ".avi", ".mov", ".mkv"}
        files = sorted([f for f in folder.iterdir() if f.suffix.lower() in exts])
        for i, f in enumerate(files):
            self.bg_list_table.insertRow(i)
            self.bg_list_table.setItem(i, 0, QTableWidgetItem(str(i + 1)))
            self.bg_list_table.setItem(i, 1, QTableWidgetItem(f.name))
            self.bg_list_table.setItem(i, 2, QTableWidgetItem(str(f)))

    # ─── Group 4: Output Settings ───────────────────────────────────────────

    def _build_group4_output(self) -> QGroupBox:
        box = QGroupBox("Output Settings")
        layout = QVBoxLayout(box)
        layout.setSpacing(6)

        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Output folder:"))
        self.output_folder = FileSelectWidget(mode="folder", placeholder="Select output folder")
        row1.addWidget(self.output_folder)
        layout.addLayout(row1)

        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Filename template:"))
        self.output_template = QLineEdit()
        self.output_template.setPlaceholderText("MelodyClip_{song_name}")
        row2.addWidget(self.output_template)
        layout.addLayout(row2)

        row3 = QHBoxLayout()
        # Resolution
        self.res_group = QButtonGroup(self)
        self.rb_res_1080x1920 = QRadioButton("1080x1920 (Portrait, recommended)")
        self.rb_res_1920x1080 = QRadioButton("1920x1080 (Landscape)")
        self.rb_res_1080s = QRadioButton("1080x1080 (Square)")
        self.res_group.addButton(self.rb_res_1080x1920, 0)
        self.res_group.addButton(self.rb_res_1920x1080, 1)
        self.res_group.addButton(self.rb_res_1080s, 2)
        row3.addWidget(QLabel("Resolution:"))
        row3.addWidget(self.rb_res_1080x1920)
        row3.addWidget(self.rb_res_1920x1080)
        row3.addWidget(self.rb_res_1080s)
        row3.addStretch()
        layout.addLayout(row3)

        row4 = QHBoxLayout()
        self.fps_group = QButtonGroup(self)
        self.rb_fps30 = QRadioButton("30fps (recommended)")
        self.rb_fps24 = QRadioButton("24fps")
        self.fps_group.addButton(self.rb_fps30, 0)
        self.fps_group.addButton(self.rb_fps24, 1)
        row4.addWidget(QLabel("Frame Rate:"))
        row4.addWidget(self.rb_fps30)
        row4.addWidget(self.rb_fps24)
        row4.addSpacing(20)
        row4.addWidget(QLabel("Bitrate:"))
        self.bitrate = QSpinBox()
        self.bitrate.setRange(1000, 10000)
        self.bitrate.setSuffix(" kbps")
        self.bitrate.setFixedWidth(110)
        row4.addWidget(self.bitrate)
        row4.addStretch()
        layout.addLayout(row4)

        return box

    # ─── Group 5: Text Style ───────────────────────────────────────────────────

    def _build_group5_style(self) -> QGroupBox:
        box = QGroupBox("Text Style")
        layout = QVBoxLayout(box)
        layout.setSpacing(8)

        def style_row(label_text, size_spin, bold_cb, color_btn, stroke_btn, stroke_spin):
            h = QHBoxLayout()
            h.addWidget(QLabel(label_text))
            h.addWidget(QLabel("Size"))
            h.addWidget(size_spin)
            h.addWidget(bold_cb)
            h.addWidget(QLabel("Color"))
            h.addWidget(color_btn)
            h.addWidget(QLabel("Stroke"))
            h.addWidget(stroke_btn)
            h.addWidget(stroke_spin)
            h.addStretch()
            return h

        # Top banner
        layout.addWidget(QLabel("[Top Banner]"))
        title_row1 = QHBoxLayout()
        title_row1.addWidget(QLabel("Content template:"))
        self.top_text_template = QLineEdit()
        title_row1.addWidget(self.top_text_template)
        layout.addLayout(title_row1)

        self.top_text_size = QSpinBox()
        self.top_text_size.setRange(24, 120)
        self.top_text_size.setFixedWidth(70)
        self.top_text_bold = QCheckBox("Bold")
        self.top_text_color = ColorButton()
        self.top_text_stroke_color = ColorButton()
        self.top_text_stroke_width = QSpinBox()
        self.top_text_stroke_width.setRange(0, 5)
        self.top_text_stroke_width.setFixedWidth(50)
        layout.addLayout(style_row(
            "    Style:",
            self.top_text_size, self.top_text_bold,
            self.top_text_color, self.top_text_stroke_color, self.top_text_stroke_width
        ))

        bg_row = QHBoxLayout()
        bg_row.addWidget(QLabel("  Background:"))
        self.top_text_bg_color = ColorButton()
        bg_row.addWidget(self.top_text_bg_color)
        bg_row.addWidget(QLabel("(Leave empty = transparent)"))
        bg_row.addStretch()
        layout.addLayout(bg_row)

        layout.addWidget(self._hline())

        # Bottom disclaimer
        layout.addWidget(QLabel("[Bottom Disclaimer]"))
        bottom_row1 = QHBoxLayout()
        bottom_row1.addWidget(QLabel("Content:"))
        self.bottom_text = QLineEdit()
        bottom_row1.addWidget(self.bottom_text)
        layout.addLayout(bottom_row1)

        self.bottom_text_size = QSpinBox()
        self.bottom_text_size.setRange(18, 72)
        self.bottom_text_size.setFixedWidth(70)
        self.bottom_text_bold = QCheckBox("Bold")
        self.bottom_text_color = ColorButton()
        self.bottom_text_stroke_color = ColorButton()
        self.bottom_text_stroke_width = QSpinBox()
        self.bottom_text_stroke_width.setRange(0, 5)
        self.bottom_text_stroke_width.setFixedWidth(50)
        layout.addLayout(style_row(
            "  Style:",
            self.bottom_text_size, self.bottom_text_bold,
            self.bottom_text_color, self.bottom_text_stroke_color, self.bottom_text_stroke_width
        ))

        # Bottom center disclaimer
        bcr = QHBoxLayout()
        bcr.addWidget(QLabel("Bottom Center:"))
        self.bottom_center_text = QLineEdit()
        self.bottom_center_text.setPlaceholderText("Lyrics for appreciation only")
        bcr.addWidget(self.bottom_center_text)
        layout.addLayout(bcr)

        layout.addWidget(self._hline())

        # Subtitle toggles
        sub_toggle_row = QHBoxLayout()
        self.enable_intro_subtitles = QCheckBox("Intro Subtitles")
        self.enable_intro_subtitles.setChecked(True)
        self.enable_guide_subtitles = QCheckBox("Guide Subtitles")
        self.enable_guide_subtitles.setChecked(True)
        self.enable_outro_subtitles = QCheckBox("Outro Subtitles")
        self.enable_outro_subtitles.setChecked(True)
        sub_toggle_row.addWidget(QLabel("Subtitles:"))
        sub_toggle_row.addWidget(self.enable_intro_subtitles)
        sub_toggle_row.addWidget(self.enable_guide_subtitles)
        sub_toggle_row.addWidget(self.enable_outro_subtitles)
        sub_toggle_row.addStretch()
        layout.addLayout(sub_toggle_row)
        self.subtitle_size = QSpinBox()
        self.subtitle_size.setRange(24, 80)
        self.subtitle_size.setFixedWidth(70)
        self.subtitle_bold = QCheckBox("Bold")
        self.subtitle_color = ColorButton()
        self.subtitle_stroke_color = ColorButton()
        self.subtitle_stroke_width = QSpinBox()
        self.subtitle_stroke_width.setRange(0, 5)
        self.subtitle_stroke_width.setFixedWidth(50)
        layout.addLayout(style_row(
            "    Style:",
            self.subtitle_size, self.subtitle_bold,
            self.subtitle_color, self.subtitle_stroke_color, self.subtitle_stroke_width
        ))

        anim_row = QHBoxLayout()
        anim_row.addWidget(QLabel("Slide-in Duration:"))
        self.slide_in_duration = QDoubleSpinBox()
        self.slide_in_duration.setRange(0.1, 1.0)
        self.slide_in_duration.setSingleStep(0.1)
        self.slide_in_duration.setSuffix(" s")
        self.slide_in_duration.setFixedWidth(90)
        anim_row.addWidget(self.slide_in_duration)
        anim_row.addSpacing(20)
        anim_row.addWidget(QLabel("Max Visible Lines:"))
        self.max_subtitle_lines = QSpinBox()
        self.max_subtitle_lines.setRange(1, 5)
        self.max_subtitle_lines.setFixedWidth(50)
        anim_row.addWidget(self.max_subtitle_lines)
        anim_row.addStretch()
        layout.addLayout(anim_row)

        return box

    def _hline(self) -> QFrame:
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        return line

    # ─── Group 6: Default Subtitles ───────────────────────────────────────────

    def _build_group6_subtitles(self) -> QGroupBox:
        box = QGroupBox("Default Subtitles")
        layout = QVBoxLayout(box)
        layout.setSpacing(6)

        self.subtitle_table = QTableWidget(0, 2)
        self.subtitle_table.setHorizontalHeaderLabels(["Time (s)", "Subtitle Text"])
        self.subtitle_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self.subtitle_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.subtitle_table.setColumnWidth(0, 90)
        self.subtitle_table.setMinimumHeight(160)
        layout.addWidget(self.subtitle_table)

        btn_row = QHBoxLayout()
        btn_add = QPushButton("+ Add Row")
        btn_del = QPushButton("- Delete Row")
        btn_clear = QPushButton("Clear")
        btn_add.clicked.connect(self._add_subtitle_row)
        btn_del.clicked.connect(self._del_subtitle_row)
        btn_clear.clicked.connect(self._clear_subtitles)
        btn_row.addWidget(btn_add)
        btn_row.addWidget(btn_del)
        btn_row.addWidget(btn_clear)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        return box

    def _add_subtitle_row(self):
        row = self.subtitle_table.rowCount()
        self.subtitle_table.insertRow(row)
        # Auto-increment time by 1.0s from previous row
        prev_time = 0.0
        if row > 0:
            prev_item = self.subtitle_table.item(row - 1, 0)
            if prev_item:
                try:
                    prev_time = float(prev_item.text()) + 1.0
                except ValueError:
                    pass
        self.subtitle_table.setItem(row, 0, QTableWidgetItem(f"{prev_time:.1f}"))
        self.subtitle_table.setItem(row, 1, QTableWidgetItem(""))

    def _del_subtitle_row(self):
        rows = sorted(set(idx.row() for idx in self.subtitle_table.selectedIndexes()), reverse=True)
        for row in rows:
            self.subtitle_table.removeRow(row)

    def _clear_subtitles(self):
        reply = QMessageBox.question(
            self, "Confirm Clear", "Are you sure you want to clear all subtitles?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.subtitle_table.setRowCount(0)

    # ─── Data loading/saving ───────────────────────────────────────────────────

    def _set_audio_combo_value(self, combo: QComboBox, value: str):
        """Set combo box value, dynamically add option if it's a local file path."""
        if not value:
            combo.setCurrentIndex(0)
            return
        idx = combo.findData(value)
        if idx >= 0:
            combo.setCurrentIndex(idx)
        else:
            # Local file path, dynamically add
            filename = Path(value).name
            insert_pos = combo.count() - 1
            combo.insertItem(insert_pos, f"[Local] {filename}", value)
            combo.setCurrentIndex(insert_pos)

    def _load_from_config(self):
        cfg = config.get_all()

        # Group 1
        self.enable_intro.setChecked(cfg.get("enable_intro", True))
        self._set_audio_combo_value(self.intro_audio, cfg.get("intro_audio", ""))

        self.enable_guide.setChecked(cfg.get("enable_guide", True))
        self._set_audio_combo_value(self.guide_audio, cfg.get("guide_audio", ""))

        self.enable_outro.setChecked(cfg.get("enable_outro", True))
        self._set_audio_combo_value(self.outro_audio, cfg.get("outro_audio", ""))
        self.silence_gap.setValue(cfg.get("silence_gap", 0.3))
        self.fadeout_duration.setValue(cfg.get("fadeout_duration", 1.5))

        # Group 2
        trim_mode = cfg.get("trim_mode", "fixed")
        {
            "fixed":  self.rb_trim_fixed,
            "slice":  self.rb_trim_slice,
            "manual": self.rb_trim_manual,
        }.get(trim_mode, self.rb_trim_fixed).setChecked(True)
        self.trim_stack.setCurrentIndex({"fixed": 0, "slice": 1, "manual": 2}.get(trim_mode, 0))
        self.trim_duration.setValue(cfg.get("trim_duration", 45))
        self.slice_interval.setValue(cfg.get("slice_interval", 45))
        self.manual_start.setValue(cfg.get("manual_start", 0))
        self.manual_duration.setValue(cfg.get("manual_duration", 45))

        # Group 3
        bg_mode = cfg.get("background_mode", "fixed")
        (self.rb_bg_fixed if bg_mode == "fixed" else self.rb_bg_folder).setChecked(True)
        self.bg_stack.setCurrentIndex(0 if bg_mode == "fixed" else 1)
        self.bg_file.set_path(cfg.get("background_file", ""))
        self.bg_folder.set_path(cfg.get("background_folder", ""))
        strategy = cfg.get("background_select_strategy", "sequential")
        (self.rb_bg_seq if strategy == "sequential" else self.rb_bg_rand).setChecked(True)
        if cfg.get("background_folder"):
            self._refresh_bg_list(cfg.get("background_folder", ""))

        # Group 4
        self.output_folder.set_path(cfg.get("output_folder", ""))
        self.output_template.setText(cfg.get("output_filename_template", "MelodyClip_{song_name}"))
        res = cfg.get("output_resolution", [1080, 1920])
        self.rb_res_1080x1920.setChecked(res == [1080, 1920])
        self.rb_res_1920x1080.setChecked(res == [1920, 1080])
        self.rb_res_1080s.setChecked(res == [1080, 1080])
        fps = cfg.get("fps", 30)
        self.rb_fps30.setChecked(fps == 30)
        self.rb_fps24.setChecked(fps == 24)
        bitrate_str = str(cfg.get("bitrate", "4000k"))
        try:
            self.bitrate.setValue(int(bitrate_str.lower().replace("k", "").replace("kbps", "").strip()))
        except (ValueError, AttributeError):
            self.bitrate.setValue(4000)

        # Group 5
        self.top_text_template.setText(cfg.get("top_text_template", "{song_name}"))
        self.top_text_size.setValue(cfg.get("top_text_size", 48))
        self.top_text_bold.setChecked(cfg.get("top_text_bold", True))
        self.top_text_color.set_color(cfg.get("top_text_color", "#FFFFFF"))
        self.top_text_stroke_color.set_color(cfg.get("top_text_stroke_color", "#000000"))
        self.top_text_stroke_width.setValue(cfg.get("top_text_stroke_width", 0))
        self.top_text_bg_color.set_color(cfg.get("top_text_bg_color", "#FFD700"))

        self.bottom_text.setText(cfg.get("bottom_text", "Songs for sharing, no harmful intent"))
        self.bottom_center_text.setText(cfg.get("bottom_center_text", "Lyrics for appreciation only"))
        self.bottom_text_size.setValue(cfg.get("bottom_text_size", 36))
        self.bottom_text_bold.setChecked(cfg.get("bottom_text_bold", False))
        self.bottom_text_color.set_color(cfg.get("bottom_text_color", "#FFFFFF"))
        self.bottom_text_stroke_color.set_color(cfg.get("bottom_text_stroke_color", "#000000"))
        self.bottom_text_stroke_width.setValue(cfg.get("bottom_text_stroke_width", 2))

        self.enable_intro_subtitles.setChecked(cfg.get("enable_intro_subtitles", True))
        self.enable_guide_subtitles.setChecked(cfg.get("enable_guide_subtitles", True))
        self.enable_outro_subtitles.setChecked(cfg.get("enable_outro_subtitles", True))
        self.subtitle_size.setValue(cfg.get("subtitle_size", 48))
        self.subtitle_bold.setChecked(cfg.get("subtitle_bold", True))
        self.subtitle_color.set_color(cfg.get("subtitle_color", "#FFFFFF"))
        self.subtitle_stroke_color.set_color(cfg.get("subtitle_stroke_color", "#000000"))
        self.subtitle_stroke_width.setValue(cfg.get("subtitle_stroke_width", 2))
        self.slide_in_duration.setValue(cfg.get("slide_in_duration", 0.3))
        self.max_subtitle_lines.setValue(cfg.get("max_subtitle_lines", 3))

        # Group 6
        self.subtitle_table.setRowCount(0)
        for sub in cfg.get("default_subtitles", []):
            row = self.subtitle_table.rowCount()
            self.subtitle_table.insertRow(row)
            self.subtitle_table.setItem(row, 0, QTableWidgetItem(str(sub.get("time", 0.0))))
            self.subtitle_table.setItem(row, 1, QTableWidgetItem(sub.get("text", "")))

    def _collect_to_config(self) -> dict:
        """Read all values from UI controls and return config dict."""
        trim_map = {0: "fixed", 1: "slice", 2: "manual"}
        trim_mode = trim_map.get(self.trim_group.checkedId(), "fixed")

        if self.rb_res_1080x1920.isChecked():
            res = [1080, 1920]
        elif self.rb_res_1920x1080.isChecked():
            res = [1920, 1080]
        else:
            res = [1080, 1080]
        fps = 30 if self.rb_fps30.isChecked() else 24
        bg_mode = "fixed" if self.rb_bg_fixed.isChecked() else "folder"
        bg_strategy = "sequential" if self.rb_bg_seq.isChecked() else "random"

        subtitles = []
        for row in range(self.subtitle_table.rowCount()):
            t_item = self.subtitle_table.item(row, 0)
            txt_item = self.subtitle_table.item(row, 1)
            try:
                t = float(t_item.text()) if t_item else 0.0
            except ValueError:
                t = 0.0
            txt = txt_item.text() if txt_item else ""
            if txt:
                subtitles.append({"time": t, "text": txt})

        return {
            "enable_intro": self.enable_intro.isChecked(),
            "intro_audio": self.intro_audio.currentData() or "",
            "enable_guide": self.enable_guide.isChecked(),
            "guide_audio": self.guide_audio.currentData() or "",
            "enable_outro": self.enable_outro.isChecked(),
            "outro_audio": self.outro_audio.currentData() or "",
            "silence_gap": self.silence_gap.value(),
            "fadeout_duration": self.fadeout_duration.value(),
            "trim_mode": trim_mode,
            "trim_duration": self.trim_duration.value(),
            "slice_interval": self.slice_interval.value(),
            "manual_start": self.manual_start.value(),
            "manual_duration": self.manual_duration.value(),
            "background_mode": bg_mode,
            "background_file": self.bg_file.get_path(),
            "background_folder": self.bg_folder.get_path(),
            "background_select_strategy": bg_strategy,
            "output_folder": self.output_folder.get_path(),
            "output_filename_template": self.output_template.text() or "MelodyClip_{song_name}",
            "output_resolution": res,
            "fps": fps,
            "bitrate": f"{self.bitrate.value()}k",
            "top_text_template": self.top_text_template.text(),
            "top_text_size": self.top_text_size.value(),
            "top_text_bold": self.top_text_bold.isChecked(),
            "top_text_color": self.top_text_color.get_color(),
            "top_text_stroke_color": self.top_text_stroke_color.get_color(),
            "top_text_stroke_width": self.top_text_stroke_width.value(),
            "top_text_bg_color": self.top_text_bg_color.get_color(),
            "bottom_text": self.bottom_text.text(),
            "bottom_center_text": self.bottom_center_text.text() or "Lyrics for appreciation only",
            "bottom_text_size": self.bottom_text_size.value(),
            "bottom_text_bold": self.bottom_text_bold.isChecked(),
            "bottom_text_color": self.bottom_text_color.get_color(),
            "bottom_text_stroke_color": self.bottom_text_stroke_color.get_color(),
            "bottom_text_stroke_width": self.bottom_text_stroke_width.value(),
            "enable_intro_subtitles": self.enable_intro_subtitles.isChecked(),
            "enable_guide_subtitles": self.enable_guide_subtitles.isChecked(),
            "enable_outro_subtitles": self.enable_outro_subtitles.isChecked(),
            "subtitle_size": self.subtitle_size.value(),
            "subtitle_bold": self.subtitle_bold.isChecked(),
            "subtitle_color": self.subtitle_color.get_color(),
            "subtitle_stroke_color": self.subtitle_stroke_color.get_color(),
            "subtitle_stroke_width": self.subtitle_stroke_width.value(),
            "slide_in_duration": self.slide_in_duration.value(),
            "max_subtitle_lines": self.max_subtitle_lines.value(),
            "default_subtitles": subtitles,
        }

    # ─── Slot functions ────────────────────────────────────────────────────────

    def _on_save(self):
        new_cfg = self._collect_to_config()
        # Basic validation
        if not new_cfg["output_folder"]:
            QMessageBox.warning(self, "Save Failed", "Please set an output folder first.")
            return
        config.update_many(new_cfg)
        try:
            config.save()
        except RuntimeError as e:
            QMessageBox.critical(self, "Save Failed", str(e))
            return
        self.accept()

    def _on_reset(self):
        reply = QMessageBox.question(
            self, "Reset to Defaults",
            "Reset all settings to defaults?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            config.reset_to_defaults()
            self._load_from_config()
