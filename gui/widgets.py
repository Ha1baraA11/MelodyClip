"""
widgets.py — Reusable custom widgets

- FileSelectWidget   File/folder selection row (LineEdit + Browse button)
- ColorButton        Color swatch button (opens QColorDialog on click)
"""

from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QLineEdit, QPushButton,
    QFileDialog, QColorDialog, QSizePolicy,
)
from PySide6.QtCore import Signal
from PySide6.QtGui import QColor


class FileSelectWidget(QWidget):
    """
    File/folder selection row.

    Composed of: QLineEdit (read-only) + QPushButton ("Browse")
    Supported modes:
        - "file"    Single file selection (QFileDialog.getOpenFileName)
        - "folder"  Folder selection (QFileDialog.getExistingDirectory)

    Signals:
        path_changed(str)  Emitted when user selects a file/folder
    """

    path_changed = Signal(str)

    def __init__(
        self,
        mode: str = "file",
        file_filter: str = "Audio Files (*.mp3 *.mp4)",
        placeholder: str = "",
        button_text: str = "Browse",
        parent=None,
    ):
        super().__init__(parent)
        self._mode = mode
        self._filter = file_filter

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self.line_edit = QLineEdit()
        self.line_edit.setReadOnly(True)
        self.line_edit.setPlaceholderText(placeholder)
        self.line_edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        layout.addWidget(self.line_edit)

        self.btn = QPushButton(button_text)
        self.btn.setFixedWidth(64)
        self.btn.clicked.connect(self._on_click)
        layout.addWidget(self.btn)

    def _on_click(self):
        if self._mode == "folder":
            path = QFileDialog.getExistingDirectory(self, "Select Folder")
        else:
            path, _ = QFileDialog.getOpenFileName(
                self, "Select File", "", self._filter
            )
        if path:
            self.line_edit.setText(path)
            self.path_changed.emit(path)

    def get_path(self) -> str:
        return self.line_edit.text()

    def set_path(self, path: str):
        self.line_edit.setText(path)

    def set_enabled(self, enabled: bool):
        self.line_edit.setEnabled(enabled)
        self.btn.setEnabled(enabled)


class ColorButton(QPushButton):
    """
    Color swatch selection button.
    Displays current color as background, opens QColorDialog on click.

    Signals:
        color_changed(str)  Emitted when color changes, value is "#RRGGBB"
    """

    color_changed = Signal(str)

    def __init__(self, color: str = "#FFFFFF", parent=None):
        super().__init__(parent)
        self.setFixedSize(48, 24)
        self._color = color
        self._update_style()
        self.clicked.connect(self._pick_color)

    def _update_style(self):
        self.setStyleSheet(
            f"background-color: {self._color}; "
            f"border: 1px solid #888; border-radius: 3px;"
        )

    def _pick_color(self):
        color = QColorDialog.getColor(QColor(self._color), self, "Select Color")
        if color.isValid():
            self._color = color.name()
            self._update_style()
            self.color_changed.emit(self._color)

    def get_color(self) -> str:
        return self._color

    def set_color(self, color: str):
        self._color = color
        self._update_style()
