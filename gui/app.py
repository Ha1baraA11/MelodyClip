"""
app.py — Main Window (QMainWindow)

Threading model: Video generation runs in GeneratorThread (QThread),
progress, logs, and results are relayed via Signal/Slot, keeping the UI main thread responsive.
"""

from pathlib import Path

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QRadioButton, QButtonGroup, QLabel, QLineEdit,
    QPushButton, QProgressBar, QMessageBox, QFileDialog,
    QSizePolicy, QFrame, QTextEdit,
)
from PySide6.QtCore import Qt, QThread, Signal, Slot, QUrl, QTimer, QElapsedTimer
from PySide6.QtGui import QFont, QIcon, QDesktopServices

from gui.widgets import FileSelectWidget
from gui.settings_dialog import SettingsDialog
from utils.config_manager import config
from utils.file_utils import get_resource_path
from core.video_builder import generate_single, generate_batch


# ─── Step → progress percentage mapping ────────────────────────────────────────

_STEP_PROGRESS = {
    "Loading song audio...": 5,
    "Extracting audio from MP4...": 10,
    "Streaming MP4 audio...": 10,
    "Compositing audio...": 20,
    "Loading intro audio...": 25,
    "Loading guide audio...": 30,
    "Loading background video...": 45,
    "Generating subtitles...": 60,
    "Generating intro subtitles...": 60,
    "Generating guide subtitles...": 62,
    "Generating outro subtitles...": 65,
    "Generating text overlays...": 70,
    "Compositing video (this may take a minute)...": 80,
    "Saving video file...": 92,
}


# ─── Background generation thread ─────────────────────────────────────────────

class GeneratorThread(QThread):
    """
    Background video generation thread.
    All time-consuming operations (audio processing, video rendering) run here,
    results are relayed to the UI main thread via Signal.
    """

    progress_text = Signal(str)      # Current step description
    progress_value = Signal(int)     # Progress value 0~100
    log_message = Signal(str)        # Log message (appended to log area)
    finished_ok = Signal(str)        # Completed, parameter is output path
    finished_error = Signal(str)     # Failed, parameter is error message
    batch_total = Signal(int, int, str)  # Batch: current, total, filename

    def __init__(self, mode: str, song_path: str, song_name: str, cfg: dict):
        super().__init__()
        self._mode = mode          # "single" or "batch"
        self._song_path = song_path
        self._song_name = song_name
        self._cfg = cfg

    def run(self):
        try:
            if self._mode == "single":
                self._run_single()
            else:
                self._run_batch()
        except Exception as e:
            self.log_message.emit(f"[Error] {e}")
            self.finished_error.emit(str(e))

    def _run_single(self):
        def cb(text: str):
            self.progress_text.emit(text)
            self.log_message.emit(text)
            pct = _STEP_PROGRESS.get(text, -1)
            if pct >= 0:
                self.progress_value.emit(pct)

        generate_single(
            song_file=self._song_path,
            song_name=self._song_name,
            cfg=self._cfg,
            progress_cb=cb,
        )

        output_dir = self._cfg.get("output_folder", "")
        self.progress_value.emit(100)
        self.finished_ok.emit(output_dir)

    def _run_batch(self):
        def cb(text: str):
            self.progress_text.emit(text)
            self.log_message.emit(text)

        def total_cb(cur: int, total: int, fname: str):
            pct = int((cur - 1) / total * 100)
            self.progress_value.emit(pct)
            self.batch_total.emit(cur, total, fname)

        failed = generate_batch(
            songs_path=self._song_path,
            cfg=self._cfg,
            progress_cb=cb,
            total_progress_cb=total_cb,
        )

        self.progress_value.emit(100)
        if failed:
            details = "\n".join(f"• {name}: {err}" for name, err in failed)
            self.log_message.emit(f"[Done] {len(failed)} failed")
            self.finished_error.emit(
                f"Batch complete, but {len(failed)} failed:\n\n{details}"
            )
        else:
            self.finished_ok.emit(self._cfg.get("output_folder", ""))


# ─── Main window ──────────────────────────────────────────────────────────────

class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()
        self.setWindowTitle("MelodyClip")
        self.setFixedSize(560, 500)

        icon_path = get_resource_path("assets/Logo.png")
        if Path(icon_path).exists():
            self.setWindowIcon(QIcon(icon_path))

        self._thread: GeneratorThread | None = None
        self._elapsed_timer = QElapsedTimer()
        self._elapsed_display_timer = QTimer(self)
        self._elapsed_display_timer.timeout.connect(self._update_elapsed)
        self._build_ui()
        self._update_file_selector()

    # ─── UI construction ──────────────────────────────────────────────────────

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(20, 16, 20, 16)
        root.setSpacing(10)

        # ── Title row (title + gear button) ────────────────────────────────
        title_row = QHBoxLayout()
        title_label = QLabel("MelodyClip")
        font = QFont()
        font.setPointSize(13)
        font.setBold(True)
        title_label.setFont(font)
        title_row.addWidget(title_label)
        title_row.addStretch()

        self.btn_open_folder = QPushButton("📂")
        self.btn_open_folder.setFixedSize(32, 32)
        self.btn_open_folder.setToolTip("Open output folder")
        self.btn_open_folder.setStyleSheet(
            "QPushButton { border: none; font-size: 16px; }"
            "QPushButton:hover { background: #e0e0e0; border-radius: 4px; }"
        )
        self.btn_open_folder.clicked.connect(self._open_output_folder)
        title_row.addWidget(self.btn_open_folder)

        self.btn_settings = QPushButton("⚙")
        self.btn_settings.setFixedSize(32, 32)
        self.btn_settings.setToolTip("Open settings")
        self.btn_settings.setStyleSheet(
            "QPushButton { border: none; font-size: 16px; }"
            "QPushButton:hover { background: #e0e0e0; border-radius: 4px; }"
        )
        self.btn_settings.clicked.connect(self._open_settings)
        title_row.addWidget(self.btn_settings)
        root.addLayout(title_row)

        # ── Single/Batch toggle ──────────────────────────────────────────────
        mode_row = QHBoxLayout()
        self.mode_group = QButtonGroup(self)
        self.rb_single = QRadioButton("Single")
        self.rb_batch = QRadioButton("Batch")
        self.rb_single.setChecked(True)
        self.mode_group.addButton(self.rb_single, 0)
        self.mode_group.addButton(self.rb_batch, 1)
        mode_row.addWidget(self.rb_single)
        mode_row.addWidget(self.rb_batch)
        mode_row.addStretch()
        root.addLayout(mode_row)
        self.mode_group.idClicked.connect(self._on_mode_changed)

        # ── File selection area ─────────────────────────────────────────────
        self.file_label = QLabel("Song File (MP3/MP4):")
        root.addWidget(self.file_label)

        file_row = QHBoxLayout()
        self.song_path_edit = QLineEdit()
        self.song_path_edit.setReadOnly(True)
        self.song_path_edit.setPlaceholderText("Select a song file...")
        file_row.addWidget(self.song_path_edit)

        self.btn_select = QPushButton("Browse")
        self.btn_select.setFixedWidth(60)
        self.btn_select.clicked.connect(self._select_file)
        file_row.addWidget(self.btn_select)
        root.addLayout(file_row)

        # ── Separator line ───────────────────────────────────────────────────
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        root.addWidget(line)

        # ── Start/Stop buttons ────────────────────────────────────────────────
        btn_row = QHBoxLayout()
        self.btn_start = QPushButton("▶  Generate Video")
        self.btn_start.setFixedHeight(42)
        font2 = QFont()
        font2.setPointSize(14)
        font2.setBold(True)
        self.btn_start.setFont(font2)
        self.btn_start.setEnabled(False)
        self.btn_start.setStyleSheet(
            "QPushButton:enabled  { background: #27ae60; color: white; border-radius: 6px; }"
            "QPushButton:disabled { background: #bdc3c7; color: #888; border-radius: 6px; }"
            "QPushButton:hover:enabled { background: #2ecc71; }"
        )
        self.btn_start.clicked.connect(self._on_start)
        btn_row.addWidget(self.btn_start)

        self.btn_stop = QPushButton("■  Stop")
        self.btn_stop.setFixedHeight(42)
        self.btn_stop.setFixedWidth(80)
        self.btn_stop.setFont(font2)
        self.btn_stop.setEnabled(False)
        self.btn_stop.setStyleSheet(
            "QPushButton:enabled  { background: #e74c3c; color: white; border-radius: 6px; }"
            "QPushButton:disabled { background: #bdc3c7; color: #888; border-radius: 6px; }"
            "QPushButton:hover:enabled { background: #c0392b; }"
        )
        self.btn_stop.clicked.connect(self._on_stop)
        btn_row.addWidget(self.btn_stop)
        root.addLayout(btn_row)

        # ── Progress area (hidden by default) ─────────────────────────────────
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(False)
        self.progress_bar.setTextVisible(True)
        root.addWidget(self.progress_bar)

        self.lbl_step = QLabel("")
        self.lbl_step.setVisible(False)
        self.lbl_step.setWordWrap(True)
        root.addWidget(self.lbl_step)

        # ── Log area (always visible) ─────────────────────────────────────────
        self.log_area = QTextEdit()
        self.log_area.setReadOnly(True)
        self.log_area.setPlaceholderText("Waiting for action...")
        self.log_area.setStyleSheet(
            "QTextEdit { background: #1e1e1e; color: #d4d4d4; font-family: monospace; "
            "font-size: 12px; border: 1px solid #444; border-radius: 4px; padding: 4px; }"
        )
        root.addWidget(self.log_area, 1)  # stretch=1 lets the log area fill remaining space

        # Update button state when file path changes
        self.song_path_edit.textChanged.connect(self._update_start_btn)

    # ─── Mode switching ────────────────────────────────────────────────────────

    def _on_mode_changed(self, mode_id: int):
        self._update_file_selector()
        self.song_path_edit.clear()
        self._update_start_btn()

    def _update_file_selector(self):
        is_batch = self.rb_batch.isChecked()
        self.file_label.setText("Song File/Folder:" if is_batch else "Song File (MP3/MP4):")
        self.btn_select.setText("Browse..." if is_batch else "Browse")
        self.song_path_edit.setPlaceholderText(
            "Select a folder for batch, or a single file for auto-slicing..." if is_batch else "Select a song file..."
        )

    def _select_file(self):
        if self.rb_batch.isChecked():
            # Batch mode: select file first, cancel to pick folder instead
            path, _ = QFileDialog.getOpenFileName(
                self, "Select a song file (cancel to pick folder)", "",
                "Audio/Video Files (*.mp3 *.mp4)"
            )
            if not path:
                path = QFileDialog.getExistingDirectory(self, "Or select a song folder")
        else:
            path, _ = QFileDialog.getOpenFileName(
                self, "Select a song file", "",
                "Audio/Video Files (*.mp3 *.mp4)"
            )
        if path:
            self.song_path_edit.setText(path)

    def _update_start_btn(self):
        has_path = bool(self.song_path_edit.text().strip())
        self.btn_start.setEnabled(has_path and self._thread is None)

    # ─── Settings dialog ───────────────────────────────────────────────────────

    def _open_settings(self):
        dlg = SettingsDialog(self)
        dlg.exec()

    def _open_output_folder(self):
        folder = config.get("output_folder", "")
        if folder and Path(folder).exists():
            QDesktopServices.openUrl(QUrl.fromLocalFile(folder))
        else:
            QMessageBox.information(self, "Notice", "Output folder does not exist. Please configure it in Settings.")

    # ─── Start generation ──────────────────────────────────────────────────────

    def _on_start(self):
        song_path = self.song_path_edit.text().strip()
        if not song_path:
            return

        cfg = config.get_all()

        # Basic pre-checks
        if not cfg.get("output_folder"):
            QMessageBox.warning(self, "No output folder configured",
                                "Please click the gear icon in the top-right corner to configure the output folder.")
            return

        if not Path(cfg["output_folder"]).exists():
            QMessageBox.warning(self, "Output folder does not exist",
                                f"Output folder does not exist: {cfg['output_folder']}\nPlease update it in Settings.")
            return

        # Background video check
        bg_mode = cfg.get("background_mode", "fixed")
        if bg_mode == "fixed" and not cfg.get("background_file"):
            QMessageBox.warning(self, "No background video configured",
                                "Please configure the background video in Settings.")
            return

        song_name = Path(song_path).stem
        mode = "single" if self.rb_single.isChecked() else "batch"

        # Clear log, lock UI, start timer
        self.log_area.clear()
        self._set_ui_locked(True)
        self._elapsed_timer.start()
        self._elapsed_display_timer.start(1000)  # Update every second

        # Launch background thread
        self._thread = GeneratorThread(mode, song_path, song_name, cfg)
        self._thread.progress_text.connect(self._on_progress_text)
        self._thread.progress_value.connect(self._on_progress_value)
        self._thread.log_message.connect(self._on_log_message)
        self._thread.batch_total.connect(self._on_batch_total)
        self._thread.finished_ok.connect(self._on_finished_ok)
        self._thread.finished_error.connect(self._on_finished_error)
        self._thread.finished.connect(self._on_thread_finished)
        self._thread.start()

    # ─── Progress callbacks (main thread slots) ────────────────────────────────

    @Slot(str)
    def _on_progress_text(self, text: str):
        self.lbl_step.setText(text)
        self.lbl_step.setStyleSheet("color: #333;")

    @Slot(int)
    def _on_progress_value(self, value: int):
        self.progress_bar.setValue(value)

    @Slot(str)
    def _on_log_message(self, msg: str):
        self.log_area.append(msg)
        # Auto-scroll to bottom
        sb = self.log_area.verticalScrollBar()
        sb.setValue(sb.maximum())

    @Slot(int, int, str)
    def _on_batch_total(self, cur: int, total: int, fname: str):
        self.lbl_step.setText(f"Processing {cur}/{total}: {fname}")

    @Slot(str)
    def _on_finished_ok(self, output_dir: str):
        self._elapsed_display_timer.stop()
        elapsed = self._elapsed_timer.elapsed()
        self._set_ui_locked(False)
        self.progress_bar.setValue(100)
        self.lbl_step.setText(f"Done! Saved to {output_dir}")
        self.lbl_step.setStyleSheet("color: #27ae60;")
        self._on_log_message(f"✅ All done  Total time: {self._format_elapsed(elapsed)}")
        self._reset_title()

    @Slot(str)
    def _on_finished_error(self, error_msg: str):
        self._elapsed_display_timer.stop()
        elapsed = self._elapsed_timer.elapsed()
        self._set_ui_locked(False)
        self.lbl_step.setText(f"Error: {error_msg[:80]}")
        self._on_log_message(f"❌ Failed  Time: {self._format_elapsed(elapsed)}")
        self._reset_title()
        self.lbl_step.setStyleSheet("color: #e74c3c;")
        # Delayed popup to avoid blocking thread destruction in the signal chain
        from PySide6.QtCore import QTimer
        QTimer.singleShot(100, lambda: QMessageBox.warning(self, "Generation Failed", error_msg))

    @Slot()
    def _on_thread_finished(self):
        """QThread.finished signal slot: wait for thread to actually finish before releasing reference."""
        if self._thread is not None:
            self._thread.wait(3000)  # Wait up to 3 seconds
            self._thread.deleteLater()
            self._thread = None
            self._update_start_btn()

    # ─── Timer ───────────────────────────────────────────────────────────────

    def _update_elapsed(self):
        elapsed = self._elapsed_timer.elapsed()
        self.setWindowTitle(f"MelodyClip  ⏱ {self._format_elapsed(elapsed)}")

    @staticmethod
    def _format_elapsed(ms: int) -> str:
        secs = ms // 1000
        if secs < 60:
            return f"{secs}s"
        mins = secs // 60
        secs = secs % 60
        return f"{mins}m{secs}s"

    # ─── Stop ──────────────────────────────────────────────────────────────

    def _on_stop(self):
        if self._thread is not None and self._thread.isRunning():
            self._thread.terminate()
            self._thread.wait(3000)
            self._on_log_message("[Stopped] User manually stopped generation")
            self._on_thread_finished()

    # ─── UI lock/unlock ──────────────────────────────────────────────────────

    def _set_ui_locked(self, locked: bool):
        self.btn_start.setEnabled(not locked)
        self.btn_stop.setEnabled(locked)
        self.btn_select.setEnabled(not locked)
        self.rb_single.setEnabled(not locked)
        self.rb_batch.setEnabled(not locked)
        self.btn_settings.setEnabled(not locked)

        self.progress_bar.setVisible(locked)
        self.lbl_step.setVisible(locked)

        if locked:
            self.progress_bar.setValue(0)
            self.lbl_step.setText("Preparing...")
            self.lbl_step.setStyleSheet("color: #333;")

    def _reset_title(self):
        self.setWindowTitle("MelodyClip")

    def closeEvent(self, event):
        """Ensure background thread exits safely when the window is closed."""
        if self._thread is not None and self._thread.isRunning():
            self._thread.quit()
            self._thread.wait(2000)
        event.accept()
