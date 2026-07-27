"""Application stylesheet for CardPrintingApp."""

APP_STYLESHEET = """
            QMainWindow, QWidget {
                background-color: #1e1e2e;
                color: #cdd6f4;
                font-family: "Segoe UI", "Roboto", "Helvetica Neue", Arial, sans-serif;
                font-size: 14px;
            }
            QTabWidget::pane {
                border: 1px solid #313244;
                background-color: #252538;
                border-radius: 8px;
                padding: 4px;
            }
            QTabBar::tab {
                background-color: #313244;
                color: #a6adc8;
                padding: 10px 18px;
                border: none;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
                margin-right: 2px;
                margin-bottom: -1px;
            }
            QTabBar::tab:selected {
                background-color: #89b4fa;
                color: #1e1e2e;
                font-weight: 600;
            }
            QTabBar::tab:hover:!selected {
                background-color: #45475a;
            }
            QPushButton {
                background-color: #313244;
                color: #cdd6f4;
                border: none;
                padding: 10px 18px;
                font-weight: 600;
                border-radius: 8px;
            }
            QPushButton:hover {
                background-color: #45475a;
            }
            QPushButton:pressed {
                background-color: #585b70;
            }
            QPushButton#btnPrimary {
                background-color: #89b4fa;
                color: #1e1e2e;
            }
            QPushButton#btnPrimary:hover {
                background-color: #a6c5fa;
            }
            QPushButton#btnPrimary:pressed {
                background-color: #74a0f5;
            }
            QPushButton#zoomButton {
                background-color: #89b4fa;
                color: #1e1e2e;
                font-weight: bold;
                font-size: 16px;
                border-radius: 8px;
            }
            QPushButton#zoomButton:hover {
                background-color: #a6c5fa;
            }
            QPushButton#zoomButton:pressed {
                background-color: #74a0f5;
            }
            QLineEdit, QTextEdit, QComboBox, QSpinBox {
                background-color: #313244;
                color: #cdd6f4;
                border: 1px solid #45475a;
                padding: 8px 10px;
                border-radius: 6px;
                selection-background-color: #89b4fa;
                selection-color: #1e1e2e;
            }
            QLineEdit:focus, QTextEdit:focus, QComboBox:focus, QSpinBox:focus {
                border: 1px solid #89b4fa;
            }
            QComboBox QAbstractItemView {
                background-color: #313244;
                color: #cdd6f4;
                selection-background-color: #89b4fa;
                selection-color: #1e1e2e;
                border: 1px solid #45475a;
                border-radius: 4px;
            }
            QComboBox::drop-down {
                border: none;
                width: 24px;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 5px solid #cdd6f4;
                width: 0;
                height: 0;
                margin-right: 6px;
            }
            QComboBox:hover::down-arrow {
                border-top: 5px solid #89b4fa;
            }
            QGroupBox {
                border: 1px solid #313244;
                border-radius: 8px;
                margin-top: 14px;
                font-weight: 600;
                color: #cdd6f4;
                padding-top: 18px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 14px;
                padding: 0 8px;
            }
            QLabel {
                color: #cdd6f4;
            }
            QTableWidget {
                background-color: #252538;
                color: #cdd6f4;
                border: 1px solid #313244;
                gridline-color: #313244;
                border-radius: 6px;
            }
            QTableWidget::item {
                padding: 8px;
                color: #cdd6f4;
            }
            QHeaderView::section {
                background-color: #313244;
                color: #cdd6f4;
                padding: 10px;
                border: none;
                border-bottom: 1px solid #45475a;
                font-weight: 600;
            }
            QHeaderView::section:hover {
                background-color: #45475a;
            }
            QSlider::groove:horizontal {
                height: 6px;
                background: #313244;
                border-radius: 3px;
            }
            QSlider::handle:horizontal {
                background: #89b4fa;
                width: 16px;
                height: 16px;
                margin: -5px 0;
                border-radius: 8px;
                border: none;
            }
            QSlider::handle:horizontal:hover {
                background: #a6c5fa;
            }
            QSlider::handle:horizontal:pressed {
                background: #74a0f5;
            }
            QSlider::sub-page:horizontal {
                background: #89b4fa;
                border-radius: 3px;
            }
            QCheckBox {
                spacing: 8px;
                color: #cdd6f4;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border: 1px solid #45475a;
                border-radius: 4px;
                background-color: #313244;
            }
            QCheckBox::indicator:hover {
                border: 1px solid #89b4fa;
            }
            QCheckBox::indicator:checked {
                background-color: #89b4fa;
                border: 1px solid #89b4fa;
            }
            QCheckBox::indicator:checked:hover {
                background-color: #a6c5fa;
            }
            QSpinBox::up-button, QSpinBox::down-button {
                width: 16px;
                height: 12px;
                background-color: transparent;
                border: none;
            }
            QSpinBox::up-button:hover, QSpinBox::down-button:hover {
                background-color: #45475a;
                border-radius: 3px;
            }
            QScrollBar:vertical {
                background: #1e1e2e;
                width: 10px;
                margin: 0px 0px 0px 0px;
            }
            QScrollBar::handle:vertical {
                background: #45475a;
                min-height: 20px;
                border-radius: 5px;
            }
            QScrollBar::handle:vertical:hover {
                background: #585b70;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
            QScrollBar:horizontal {
                background: #1e1e2e;
                height: 10px;
                margin: 0px 0px 0px 0px;
            }
            QScrollBar::handle:horizontal {
                background: #45475a;
                min-width: 20px;
                border-radius: 5px;
            }
            QScrollBar::handle:horizontal:hover {
                background: #585b70;
            }
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
                width: 0px;
            }
            QFrame[frameShape="4"] {
                border: none;
            }
            QSplitter::handle {
                background-color: #313244;
                width: 2px;
            }
            QMessageBox {
                background-color: #1e1e2e;
            }
            QMessageBox QLabel {
                color: #cdd6f4;
            }
            QDialog {
                background-color: #1e1e2e;
            }
            QDialog QLabel {
                color: #cdd6f4;
            }
"""
