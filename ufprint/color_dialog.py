"""Color settings dialog for detailed color model editing."""

import logging

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QPainter
from PyQt5.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


def rgb_to_hex(r, g, b):
    return f"#{r:02X}{g:02X}{b:02X}"


def clamp_int(value, min_val=0, max_val=255):
    try:
        v = int(value)
        return max(min_val, min(max_val, v))
    except (ValueError, TypeError):
        return min_val


def clamp_float(value, min_val=0.0, max_val=100.0):
    try:
        v = float(value)
        return max(min_val, min(max_val, v))
    except (ValueError, TypeError):
        return min_val


class ColorSwatch(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._color = QColor(43, 43, 42)
        self.setFixedSize(60, 60)
        self.setCursor(Qt.PointingHandCursor)

    def color(self):
        return self._color

    def set_color(self, color):
        self._color = QColor(color)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(Qt.NoPen)
        painter.setBrush(self._color)
        painter.drawRoundedRect(1, 1, self.width() - 2, self.height() - 2, 8, 8)


class ColorSettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Настройки цвета")
        self.setMinimumWidth(420)
        self.setModal(True)

        self._fields = {}
        self._build_ui()
        self._connect_signals()
        self._load_initial_values()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(10)

        swatch_row = QHBoxLayout()
        self.swatch = ColorSwatch()
        swatch_row.addWidget(self.swatch)
        swatch_row.addStretch(1)

        self.model_combo = QComboBox()
        self.model_combo.addItems(["RGB", "HEX", "CMYK", "Lab", "HSB", "HSL", "YIQ"])
        self.model_combo.setCurrentText("RGB")
        swatch_row.addWidget(QLabel("Цвет модели:"))
        swatch_row.addWidget(self.model_combo)
        root.addLayout(swatch_row)

        name_row = QHBoxLayout()
        self.name_combo = QComboBox()
        self.name_combo.addItems(["Черный", "Белый", "Красный", "Зеленый", "Синий", "Желтый", "Произвольный"])
        self.name_combo.setCurrentText("Черный")
        self.name_combo.setEditable(True)
        self.name_combo.lineEdit().setPlaceholderText("Введите имя")
        name_row.addWidget(QLabel("Имя:"))
        name_row.addWidget(self.name_combo)
        root.addLayout(name_row)

        self._grid = QGridLayout()
        self._grid.setHorizontalSpacing(12)
        self._grid.setVerticalSpacing(6)
        self._grid.setColumnMinimumWidth(0, 30)
        self._grid.setColumnStretch(1, 1)
        root.addLayout(self._grid)

        self._add_section("RGB", ["R", "G", "B"], [43, 43, 42])
        self._add_hex_field()
        self._add_section("CMYK", ["C", "M", "Y", "K"], [0, 0, 0, 100])
        self._add_section("Lab", ["L", "a", "b"], [17, -1, 0])
        self._add_section("HSB", ["H", "S", "B"], [0, 0, 0])
        self._add_section("HSL", ["H", "S", "L"], [0, 0, 0])
        self._add_section("YIQ", ["Y", "I", "Q"], [0, 0, 0])

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def _add_section(self, title, labels, values):
        group = QGroupBox(title)
        group.setFlat(True)
        layout = QHBoxLayout(group)
        layout.setContentsMargins(8, 8, 8, 8)
        for label_text, value in zip(labels, values):
            lbl = QLabel(f"{label_text}:")
            lbl.setFixedWidth(20)
            edit = QLineEdit(str(value))
            edit.setFixedWidth(70)
            edit.setObjectName(f"field_{title}_{label_text}")
            self._fields[f"{title}_{label_text}"] = edit
            layout.addWidget(lbl)
            layout.addWidget(edit)
        self._grid.addWidget(group, self._grid.rowCount(), 0, 1, 2)

    def _add_hex_field(self):
        group = QGroupBox("HEX")
        group.setFlat(True)
        layout = QHBoxLayout(group)
        layout.setContentsMargins(8, 8, 8, 8)
        lbl = QLabel("#")
        lbl.setFixedWidth(20)
        edit = QLineEdit("#2B2B2A")
        edit.setFixedWidth(100)
        edit.setObjectName("field_HEX_hash")
        edit.setStyleSheet(
            "background-color: #2b2b2a; color: #cdd6f4; "
            "border: 1px solid #45475a; padding: 8px 10px; border-radius: 6px;"
        )
        self._fields["HEX_hash"] = edit
        layout.addWidget(lbl)
        layout.addWidget(edit)
        self._grid.addWidget(group, self._grid.rowCount(), 0, 1, 2)

    def _connect_signals(self):
        # Placeholder for bidirectional color-conversion logic.
        for name, widget in self._fields.items():
            widget.textChanged.connect(self._on_field_changed)

    def _on_field_changed(self):
        pass

    def _load_initial_values(self):
        pass

    def get_color_values(self):
        """Return current field values as a dict (placeholder for next iteration)."""
        result = {}
        for key, widget in self._fields.items():
            result[key] = widget.text().strip()
        return result