import sys
import os
import json
import sqlite3
import logging
import traceback
from pathlib import Path
from datetime import datetime
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLabel, QPushButton, QFileDialog, 
                             QTabWidget, QTextEdit, QLineEdit, QFormLayout, 
                             QGroupBox, QSplitter, QScrollArea, QMessageBox,
                             QSlider, QComboBox, QCheckBox, QSpinBox, QDialog,
                             QDialogButtonBox, QTableWidget, QTableWidgetItem,
                             QHeaderView, QFrame)
from PyQt6.QtCore import Qt, QSize, QTimer, QRect, QPoint, QDir
from PyQt6.QtGui import QPixmap, QImage, QIcon, QPainter, QColor, QPen, QBrush, QFont, QCursor, QAction
from PIL import Image, ImageDraw, ImageQt
import io
import numpy as np

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('app.log'),
        logging.StreamHandler()
    ]
)

def pillow_to_qpixmap(pil_img):
    """Convert PIL Image to QPixmap without relying on Qt's built-in image plugins."""
    try:
        if pil_img is None:
            return None

        if pil_img.mode != "RGBA":
            pil_img = pil_img.convert("RGBA")

        try:
            image_qt = ImageQt.ImageQt(pil_img)
            qimg = QImage(image_qt)
            if qimg.isNull():
                raise ValueError("ImageQt conversion produced an empty QImage")
            return QPixmap.fromImage(qimg)
        except Exception as exc:
            logging.debug(f"ImageQt conversion failed, falling back to raw bytes: {exc}")

            data = pil_img.tobytes("raw", "RGBA")
            qimg = QImage(data, pil_img.size[0], pil_img.size[1], QImage.Format.Format_RGBA8888)
            return QPixmap.fromImage(qimg)
    except Exception as e:
        logging.error(f"Error converting PIL to QPixmap: {e}", exc_info=True)
        return None

# Database setup
DB_NAME = "card_printing.db"
CONFIG_PATH = Path(__file__).resolve().parent / "company_config.json"


def normalize_path(path):
    if not path:
        return ""

    raw_path = str(path).strip()
    if not raw_path:
        return ""

    try:
        normalized = Path(raw_path).expanduser().resolve(strict=False)
        return QDir.toNativeSeparators(str(normalized))
    except Exception:
        return QDir.toNativeSeparators(raw_path)


def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_name TEXT,
            customer_phone TEXT,
            customer_email TEXT,
            company_name TEXT,
            print_specs TEXT,
            side_a_path TEXT,
            side_b_path TEXT,
            created_at TEXT,
            status TEXT
        )
    ''')
    conn.commit()
    conn.close()

class ImageEditor(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.image = None
        self.original_image = None
        self.base_image = None  # For CMYK reset
        self.current_mode = "view"  # view, move, eraser
        self.eraser_size = 20
        self.cmyk_values = {"C": 0, "M": 0, "Y": 0, "K": 0}
        self.scale_factor = 1.0
        self.offset_x = 0
        self.offset_y = 0
        self.dragging = False
        self.last_mouse_pos = QPoint()
        self.setMouseTracking(True)
        self.setMinimumSize(348, 224)  # 87x56mm at 100 DPI
        self.setStyleSheet("background-color: #252538; border: 2px solid #89b4fa;")
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.position_callback = None  # Callback for sync mode
        self.eraser_callback = None  # Callback for sync eraser
        self.click_callback = None  # Callback for side selection
        self.history_callback = None  # Callback for saving to history
        
    def load_image(self, path):
        try:
            path = normalize_path(path)
            logging.info(f"Attempting to load image: {path}")

            candidate_paths = [path]
            if os.name == "nt":
                candidate_paths.extend([path.replace('/', '\\'), path.replace('\\', '/')])

            resolved_path = None
            for candidate in candidate_paths:
                if os.path.exists(candidate):
                    resolved_path = candidate
                    break

            if not resolved_path:
                error_msg = f"Файл не существует: {path}"
                logging.error(error_msg)
                return False, error_msg

            path = resolved_path
            logging.info(f"Using resolved path: {path}")
            
            # Try loading with PIL
            img = Image.open(path)
            logging.info(f"Image loaded successfully: {img.size}, mode: {img.mode}")
            
            # Force RGB conversion to handle palette mode (P) and other modes
            if img.mode != 'RGB':
                logging.info(f"Converting image from {img.mode} to RGB")
                img = img.convert('RGB')
            
            # Convert to RGBA
            self.original_image = img.convert("RGBA")
            self.base_image = self.original_image.copy()
            self.image = self.original_image.copy()
            
            # Reset position
            self.offset_x = 0
            self.offset_y = 0
            self.scale_factor = 1.0
            
            self.update()
            logging.info("Image displayed successfully")
            return True, ""
            
        except Exception as e:
            error_msg = f"Ошибка загрузки изображения: {str(e)}\n\nTraceback:\n{traceback.format_exc()}"
            logging.error(error_msg)
            return False, error_msg
    
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(37, 37, 56))
        
        if self.image:
            img_width, img_height = self.image.size
            widget_width = self.width()
            widget_height = self.height()
            
            # Calculate display size with scale factor
            display_width = int(img_width * self.scale_factor)
            display_height = int(img_height * self.scale_factor)
            
            # Calculate position with offset
            x = (widget_width - display_width) // 2 + self.offset_x
            y = (widget_height - display_height) // 2 + self.offset_y
            
            # Draw image
            try:
                # Convert PIL Image to QPixmap using byte buffer (PyInstaller-safe)
                pixmap = pillow_to_qpixmap(self.image)
                if pixmap:
                    painter.drawPixmap(x, y, pixmap.scaled(display_width, display_height, Qt.AspectRatioMode.KeepAspectRatio))
                else:
                    raise Exception("Failed to convert image to QPixmap")
            except Exception as e:
                logging.error(f"Error drawing image: {e}", exc_info=True)
                painter.setPen(QPen(QColor(255, 0, 0), 2))
                painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Ошибка отображения")
            
            # Draw eraser cursor if in eraser mode
            if self.current_mode == "eraser":
                painter.setPen(QPen(QColor(255, 0, 0), 2))
                painter.setBrush(QBrush(QColor(255, 0, 0, 50)))
                cursor_size = self.eraser_size * 2
                painter.drawEllipse(self.last_mouse_pos.x() - cursor_size//2, 
                                   self.last_mouse_pos.y() - cursor_size//2, 
                                   cursor_size, cursor_size)
        else:
            painter.setPen(QPen(QColor(166, 173, 200), 2))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Загрузите изображение\n(87x56mm)")
    
    def mousePressEvent(self, event):
        if not self.image:
            return
            
        # Call click callback for side selection
        if self.click_callback:
            self.click_callback()
            
        if self.current_mode == "eraser":
            self.apply_eraser(event.pos())
        elif self.current_mode == "move":
            self.dragging = True
            self.last_mouse_pos = event.pos()
            self.setCursor(QCursor(Qt.CursorShape.ClosedHandCursor))
    
    def mouseMoveEvent(self, event):
        self.last_mouse_pos = event.pos()
        
        if not self.image:
            return
            
        if self.current_mode == "eraser" and event.buttons() & Qt.MouseButton.LeftButton:
            self.apply_eraser(event.pos())
        elif self.current_mode == "move" and self.dragging:
            delta = event.pos() - self.last_mouse_pos
            self.offset_x += delta.x()
            self.offset_y += delta.y()
            self.last_mouse_pos = event.pos()
            self.update()
            # Call position callback for sync mode
            if self.position_callback:
                self.position_callback(delta.x(), delta.y())
        
        # Update eraser cursor
        if self.current_mode == "eraser":
            self.update()
    
    def mouseReleaseEvent(self, event):
        if self.current_mode == "move":
            self.dragging = False
            self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))
            # Notify parent to save to history after move
            if self.history_callback:
                self.history_callback()
    
    def keyPressEvent(self, event):
        if not self.image:
            return
            
        key = event.key()
        step = 10
        
        if key == Qt.Key.Key_Left:
            self.offset_x -= step
            if self.position_callback:
                self.position_callback(-step, 0)
        elif key == Qt.Key.Key_Right:
            self.offset_x += step
            if self.position_callback:
                self.position_callback(step, 0)
        elif key == Qt.Key.Key_Up:
            self.offset_y -= step
            if self.position_callback:
                self.position_callback(0, -step)
        elif key == Qt.Key.Key_Down:
            self.offset_y += step
            if self.position_callback:
                self.position_callback(0, step)
        else:
            return
            
        self.update()
    
    def apply_eraser(self, pos):
        if not self.image:
            return
            
        try:
            img_width, img_height = self.image.size
            widget_width = self.width()
            widget_height = self.height()
            
            display_width = int(img_width * self.scale_factor)
            display_height = int(img_height * self.scale_factor)
            
            # Calculate image position
            base_x = (widget_width - display_width) // 2 + self.offset_x
            base_y = (widget_height - display_height) // 2 + self.offset_y
            
            # Convert widget coordinates to image coordinates
            x = int((pos.x() - base_x) / self.scale_factor)
            y = int((pos.y() - base_y) / self.scale_factor)
            
            # Call eraser callback for sync mode
            if self.eraser_callback:
                self.eraser_callback(x, y, self.eraser_size)
            
            if 0 <= x < img_width and 0 <= y < img_height:
                draw = ImageDraw.Draw(self.image)
                eraser_radius = self.eraser_size
                bbox = [x - eraser_radius, y - eraser_radius, x + eraser_radius, y + eraser_radius]
                draw.ellipse(bbox, fill=(0, 0, 0, 0))
                self.update()
        except Exception as e:
            logging.error(f"Error applying eraser: {e}")
    
    def zoom_image(self, factor):
        if self.image:
            self.scale_factor *= factor
            self.scale_factor = max(0.1, min(5.0, self.scale_factor))
            self.update()
            logging.info(f"Zoom changed to: {self.scale_factor}")
    
    def reset_position(self):
        self.offset_x = 0
        self.offset_y = 0
        self.scale_factor = 1.0
        self.update()
    
    def apply_cmyk_color(self, c, m, y, k):
        if self.base_image:
            try:
                # Always start from base image for consistent CMYK application
                self.image = self.base_image.copy()
                
                # Convert to numpy array for vectorized operations (fast)
                img_array = np.array(self.image, dtype=np.float32)
                
                # Apply CMYK color shift using vectorized operations
                # Subtract C from Red channel, M from Green, Y from Blue
                img_array[..., 0] = np.maximum(0, img_array[..., 0] - c)  # Red - Cyan
                img_array[..., 1] = np.maximum(0, img_array[..., 1] - m)  # Green - Magenta
                img_array[..., 2] = np.maximum(0, img_array[..., 2] - y)  # Blue - Yellow
                
                # Apply Black (brightness adjustment)
                brightness = 1.0 - (k / 255.0)
                img_array[..., 0] = img_array[..., 0] * brightness
                img_array[..., 1] = img_array[..., 1] * brightness
                img_array[..., 2] = img_array[..., 2] * brightness
                
                # Clip values to 0-255 and convert back to uint8
                img_array = np.clip(img_array, 0, 255).astype(np.uint8)
                
                # Convert back to PIL Image
                self.image = Image.fromarray(img_array)
                self.update()
            except Exception as e:
                logging.error(f"Error applying CMYK: {e}", exc_info=True)
    
    def get_image(self):
        return self.image
    
    def reset_image(self):
        if self.base_image:
            self.image = self.base_image.copy()
            self.original_image = self.base_image.copy()
            self.offset_x = 0
            self.offset_y = 0
            self.scale_factor = 1.0
            self.update()

class CardPrintingApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("UF Print - Банковские карты")
        self.setGeometry(100, 100, 1400, 900)
        
        # Dark mode style
        self.setStyleSheet("""
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
        """)
        
        init_db()
        self.current_order = {}
        self.current_side = 'BOTH'  # 'A', 'B', or 'BOTH' for synchronous editing
        self.organization_data = self.load_organization_config()
        self.undo_stack = []
        self.redo_stack = []
        self.max_history_depth = 30
        self.init_ui()
        
    def init_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)
        
        # Menu bar
        self._create_main_menu()

        # Header
        header = QLabel("UF PRINT - СИСТЕМА ДЛЯ ПЕЧАТИ БАНКОВСКИХ КАРТ")
        header.setStyleSheet("font-size: 24px; font-weight: bold; color: #89b4fa; padding: 10px;")
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(header)
        
        # Tab widget
        self.tab_widget = QTabWidget()
        main_layout.addWidget(self.tab_widget)
        
        # Create tabs
        self.create_editor_tab()
        self.create_customer_tab()
        self.create_history_tab()
        
    def _create_main_menu(self):
        menu_bar = self.menuBar()
        extra_menu = menu_bar.addMenu("Дополнительно")
        org_info_action = QAction("Информация об организации", self)
        org_info_action.triggered.connect(self.open_organization_info_dialog)
        extra_menu.addAction(org_info_action)

    def create_editor_tab(self):
        editor_tab = QWidget()
        layout = QHBoxLayout(editor_tab)
        
        # Left panel - Side A
        left_panel = self.create_side_panel("Сторона А", "side_a")
        layout.addWidget(left_panel, 1)
        
        # Right panel - Side B
        right_panel = self.create_side_panel("Сторона Б", "side_b")
        layout.addWidget(right_panel, 1)
        
        # Tools panel
        tools_panel = self.create_tools_panel()
        layout.addWidget(tools_panel, 0)
        
        self.tab_widget.addTab(editor_tab, "Редактор")
        
    def create_side_panel(self, title, side_key):
        panel = QGroupBox(title)
        layout = QVBoxLayout(panel)
        
        # Image editor
        editor = ImageEditor()
        setattr(self, f"{side_key}_editor", editor)
        
        # Set up sync callbacks
        if side_key == "side_a":
            editor.position_callback = lambda dx, dy: self.sync_position("side_b", dx, dy)
            editor.eraser_callback = lambda x, y, size: self.sync_eraser("side_b", x, y, size)
            editor.click_callback = lambda: self.on_editor_click("side_a")
            editor.history_callback = lambda: self.save_to_history()
        elif side_key == "side_b":
            editor.position_callback = lambda dx, dy: self.sync_position("side_a", dx, dy)
            editor.eraser_callback = lambda x, y, size: self.sync_eraser("side_a", x, y, size)
            editor.click_callback = lambda: self.on_editor_click("side_b")
            editor.history_callback = lambda: self.save_to_history()
        
        layout.addWidget(editor)
        
        # Load button
        load_btn = QPushButton(f"Загрузить {title}")
        load_btn.clicked.connect(lambda: self.load_image(side_key))
        layout.addWidget(load_btn)
        
        # Path label
        path_label = QLabel("Файл не выбран")
        path_label.setStyleSheet("color: #a6adc8; font-size: 11px;")
        setattr(self, f"{side_key}_path_label", path_label)
        layout.addWidget(path_label)
        
        return panel
    
    def create_tools_panel(self):
        panel = QGroupBox("Инструменты")
        layout = QVBoxLayout(panel)
        
        # Mode selection
        layout.addWidget(QLabel("Режим:"))
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["Просмотр", "Перемещение", "Ластик"])
        self.mode_combo.currentTextChanged.connect(self.change_mode)
        layout.addWidget(self.mode_combo)
        
        # Mode-specific controls container
        self.mode_controls = QWidget()
        mode_controls_layout = QVBoxLayout(self.mode_controls)
        mode_controls_layout.setContentsMargins(0, 0, 0, 0)
        
        # Eraser size control (shown only in eraser mode)
        self.eraser_control = QWidget()
        eraser_layout = QVBoxLayout(self.eraser_control)
        eraser_layout.addWidget(QLabel("Размер ластика:"))
        self.eraser_slider = QSlider(Qt.Orientation.Horizontal)
        self.eraser_slider.setRange(5, 50)
        self.eraser_slider.setValue(20)
        self.eraser_slider.valueChanged.connect(self.change_eraser_size)
        eraser_layout.addWidget(self.eraser_slider)
        self.eraser_control.setVisible(False)
        mode_controls_layout.addWidget(self.eraser_control)
        logging.info("Eraser control added to layout")
        
        # Move mode hint (shown only in move mode)
        self.move_hint = QLabel("Перетаскивайте изображение мышкой\nили используйте стрелки")
        self.move_hint.setStyleSheet("color: #a6adc8; font-size: 11px; padding: 5px;")
        self.move_hint.setVisible(False)
        mode_controls_layout.addWidget(self.move_hint)
        logging.info("Move hint added to layout")
        
        layout.addWidget(self.mode_controls)
        logging.info("Mode controls added to layout")
        
        # Sync editing mode checkbox
        self.sync_checkbox = QCheckBox("Синхронное редактирование обеих сторон")
        self.sync_checkbox.setChecked(True)  # Default to BOTH mode
        self.sync_checkbox.setStyleSheet("color: #a6adc8; padding: 5px;")
        self.sync_checkbox.stateChanged.connect(self.toggle_sync_mode)
        layout.addWidget(self.sync_checkbox)
        logging.info("Sync checkbox added to layout")
        
        # Zoom controls
        zoom_group = QGroupBox("Масштаб")
        zoom_layout = QHBoxLayout(zoom_group)
        
        zoom_in_btn = QPushButton("+")
        zoom_in_btn.setFixedSize(40, 30)
        zoom_in_btn.setObjectName("zoomButton")
        zoom_in_btn.clicked.connect(lambda: self.apply_zoom(1.2))
        zoom_layout.addWidget(zoom_in_btn)
        
        zoom_out_btn = QPushButton("-")
        zoom_out_btn.setFixedSize(40, 30)
        zoom_out_btn.setObjectName("zoomButton")
        zoom_out_btn.clicked.connect(lambda: self.apply_zoom(0.8))
        zoom_layout.addWidget(zoom_out_btn)
        
        reset_pos_btn = QPushButton("Сброс")
        reset_pos_btn.clicked.connect(self.reset_position)
        zoom_layout.addWidget(reset_pos_btn)
        
        layout.addWidget(zoom_group)
        logging.info("Zoom controls added to layout")
        
        # CMYK controls
        cmyk_group = QGroupBox("CMYK Цвет")
        cmyk_layout = QFormLayout(cmyk_group)
        
        self.c_slider = QSlider(Qt.Orientation.Horizontal)
        self.c_slider.setRange(0, 100)
        self.c_slider.valueChanged.connect(self.apply_cmyk)
        cmyk_layout.addRow("C (Cyan):", self.c_slider)
        
        self.m_slider = QSlider(Qt.Orientation.Horizontal)
        self.m_slider.setRange(0, 100)
        self.m_slider.valueChanged.connect(self.apply_cmyk)
        cmyk_layout.addRow("M (Magenta):", self.m_slider)
        
        self.y_slider = QSlider(Qt.Orientation.Horizontal)
        self.y_slider.setRange(0, 100)
        self.y_slider.valueChanged.connect(self.apply_cmyk)
        cmyk_layout.addRow("Y (Yellow):", self.y_slider)
        
        self.k_slider = QSlider(Qt.Orientation.Horizontal)
        self.k_slider.setRange(0, 100)
        self.k_slider.valueChanged.connect(self.apply_cmyk)
        cmyk_layout.addRow("K (Black):", self.k_slider)
        
        layout.addWidget(cmyk_group)
        
        # Action buttons
        reset_btn = QPushButton("Сбросить изображение")
        reset_btn.clicked.connect(self.reset_current_image)
        layout.addWidget(reset_btn)
        
        layout.addStretch()
        return panel
    
    def create_customer_tab(self):
        customer_tab = QWidget()
        layout = QVBoxLayout(customer_tab)
        
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Left - Customer info
        customer_group = QGroupBox("Данные заказчика")
        customer_layout = QFormLayout(customer_group)
        
        self.customer_name = QLineEdit()
        customer_layout.addRow("Имя заказчика:", self.customer_name)
        
        self.customer_phone = QLineEdit()
        customer_layout.addRow("Телефон:", self.customer_phone)
        
        self.customer_email = QLineEdit()
        customer_layout.addRow("Email:", self.customer_email)
        
        splitter.addWidget(customer_group)
        
        # Right - Company and print specs
        company_group = QGroupBox("Данные компании и печати")
        company_layout = QFormLayout(company_group)
        
        self.company_name = QLineEdit()
        company_layout.addRow("Название компании:", self.company_name)

        self.customer_contact_person = QLineEdit()
        company_layout.addRow("Заказчик:", self.customer_contact_person)

        self.order_number = QLineEdit()
        company_layout.addRow("Номер заказа:", self.order_number)

        self.production_deadline = QLineEdit()
        company_layout.addRow("Срок изготовления:", self.production_deadline)
        
        self.print_quantity = QSpinBox()
        self.print_quantity.setRange(1, 100000)
        self.print_quantity.setValue(100)
        company_layout.addRow("Тираж:", self.print_quantity)
        
        self.print_type = QComboBox()
        self.print_type.addItems(["Цифровая печать", "Офсетная печать", "УФ печать"])
        company_layout.addRow("Тип печати:", self.print_type)
        
        self.paper_type = QComboBox()
        self.paper_type.addItems(["Пластик PVC", "Пластик PET", "Комбинированный"])
        company_layout.addRow("Материал:", self.paper_type)
        
        self.lamination = QComboBox()
        self.lamination.addItems(["Без ламинации", "Матовая", "Глянцевая", "Soft Touch"])
        company_layout.addRow("Ламинация:", self.lamination)
        
        self.additional_specs = QTextEdit()
        self.additional_specs.setMaximumHeight(100)
        company_layout.addRow("Доп. характеристики:", self.additional_specs)
        
        splitter.addWidget(company_group)
        
        layout.addWidget(splitter)
        
        # Save order button
        save_btn = QPushButton("Сохранить заказ")
        save_btn.clicked.connect(self.save_order)
        layout.addWidget(save_btn)
        
        # Export PDF button
        export_btn = QPushButton("Экспорт в PDF (для печати)")
        export_btn.clicked.connect(self.export_pdf)
        layout.addWidget(export_btn)

        self.btn_generate_kp = QPushButton("Сформировать КП в PDF")
        self.btn_generate_kp.setObjectName("btnPrimary")
        self.btn_generate_kp.clicked.connect(self.generate_commercial_offer_pdf)
        layout.addWidget(self.btn_generate_kp)
        
        self.tab_widget.addTab(customer_tab, "Данные заказа")
        
    def create_history_tab(self):
        history_tab = QWidget()
        layout = QVBoxLayout(history_tab)
        
        # Orders table
        self.orders_table = QTableWidget()
        self.orders_table.setColumnCount(7)
        self.orders_table.setHorizontalHeaderLabels([
            "ID", "Заказчик", "Компания", "Дата", "Тираж", "Статус", "Действия"
        ])
        self.orders_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.orders_table)
        
        # Refresh button
        refresh_btn = QPushButton("Обновить список")
        refresh_btn.clicked.connect(self.load_orders)
        layout.addWidget(refresh_btn)
        
        self.tab_widget.addTab(history_tab, "История заказов")
        
        # Load orders on startup
        QTimer.singleShot(100, self.load_orders)
    
    def load_image(self, side_key):
        file_path, _ = QFileDialog.getOpenFileName(
            self, 
            f"Выберите изображение для {side_key.upper()}", 
            "", 
            "Изображения (*.png *.jpg *.jpeg *.bmp *.tiff)"
        )
        
        if file_path:
            normalized_path = normalize_path(file_path)
            logging.info(f"Original path: {file_path}")
            logging.info(f"Normalized path: {normalized_path}")
            
            editor = getattr(self, f"{side_key}_editor")
            success, error_msg = editor.load_image(normalized_path)
            if success:
                path_label = getattr(self, f"{side_key}_path_label")
                path_label.setText(normalized_path)
                self.current_order[f"{side_key}_path"] = normalized_path
                QMessageBox.information(self, "Успех", "Изображение загружено!")
            else:
                QMessageBox.critical(self, "Ошибка загрузки", error_msg)
    
    def toggle_sync_mode(self, state):
        if state == 2:  # Checked
            self.current_side = 'BOTH'
            logging.info("Sync mode enabled: editing both sides simultaneously")
        else:  # Unchecked
            self.current_side = 'A'  # Default to side A when sync is off
            logging.info("Sync mode disabled: editing side A only")
        self.update_side_visuals()
    
    def on_editor_click(self, side_key):
        """Handle click on editor canvas for side selection"""
        # Only switch sides if sync mode is OFF
        if self.current_side != 'BOTH':
            new_side = 'A' if side_key == 'side_a' else 'B'
            if self.current_side != new_side:
                self.current_side = new_side
                logging.info(f"Switched to side {new_side} via canvas click")
                self.update_side_visuals()
    
    def update_side_visuals(self):
        """Update visual indication of active side"""
        # Update border colors to show active side
        if self.current_side == 'BOTH':
            self.side_a_editor.setStyleSheet("background-color: #252538; border: 2px solid #89b4fa;")
            self.side_b_editor.setStyleSheet("background-color: #252538; border: 2px solid #89b4fa;")
        elif self.current_side == 'A':
            self.side_a_editor.setStyleSheet("background-color: #252538; border: 3px solid #89b4fa;")
            self.side_b_editor.setStyleSheet("background-color: #252538; border: 1px solid #45475a;")
        elif self.current_side == 'B':
            self.side_a_editor.setStyleSheet("background-color: #252538; border: 1px solid #45475a;")
            self.side_b_editor.setStyleSheet("background-color: #252538; border: 3px solid #89b4fa;")
    
    def save_to_history(self):
        """Save current state of both sides to undo stack"""
        try:
            # Save state of both editors
            state = {
                'side_a': {
                    'image': self.side_a_editor.image.copy() if self.side_a_editor.image else None,
                    'original_image': self.side_a_editor.original_image.copy() if self.side_a_editor.original_image else None,
                    'base_image': self.side_a_editor.base_image.copy() if self.side_a_editor.base_image else None,
                    'scale_factor': self.side_a_editor.scale_factor,
                    'offset_x': self.side_a_editor.offset_x,
                    'offset_y': self.side_a_editor.offset_y
                },
                'side_b': {
                    'image': self.side_b_editor.image.copy() if self.side_b_editor.image else None,
                    'original_image': self.side_b_editor.original_image.copy() if self.side_b_editor.original_image else None,
                    'base_image': self.side_b_editor.base_image.copy() if self.side_b_editor.base_image else None,
                    'scale_factor': self.side_b_editor.scale_factor,
                    'offset_x': self.side_b_editor.offset_x,
                    'offset_y': self.side_b_editor.offset_y
                },
                'cmyk': {
                    'c': self.c_slider.value(),
                    'm': self.m_slider.value(),
                    'y': self.y_slider.value(),
                    'k': self.k_slider.value()
                }
            }
            
            # Add to undo stack
            self.undo_stack.append(state)
            
            # Limit stack size
            if len(self.undo_stack) > self.max_history_depth:
                self.undo_stack.pop(0)
            
            # Clear redo stack on new action
            self.redo_stack.clear()
            
            logging.info(f"State saved to undo stack (depth: {len(self.undo_stack)})")
        except Exception as e:
            logging.error(f"Error saving to history: {e}", exc_info=True)
    
    def undo(self):
        """Restore previous state from undo stack"""
        if not self.undo_stack:
            logging.info("Nothing to undo")
            return
        
        try:
            # Save current state to redo stack
            current_state = {
                'side_a': {
                    'image': self.side_a_editor.image.copy() if self.side_a_editor.image else None,
                    'original_image': self.side_a_editor.original_image.copy() if self.side_a_editor.original_image else None,
                    'base_image': self.side_a_editor.base_image.copy() if self.side_a_editor.base_image else None,
                    'scale_factor': self.side_a_editor.scale_factor,
                    'offset_x': self.side_a_editor.offset_x,
                    'offset_y': self.side_a_editor.offset_y
                },
                'side_b': {
                    'image': self.side_b_editor.image.copy() if self.side_b_editor.image else None,
                    'original_image': self.side_b_editor.original_image.copy() if self.side_b_editor.original_image else None,
                    'base_image': self.side_b_editor.base_image.copy() if self.side_b_editor.base_image else None,
                    'scale_factor': self.side_b_editor.scale_factor,
                    'offset_x': self.side_b_editor.offset_x,
                    'offset_y': self.side_b_editor.offset_y
                },
                'cmyk': {
                    'c': self.c_slider.value(),
                    'm': self.m_slider.value(),
                    'y': self.y_slider.value(),
                    'k': self.k_slider.value()
                }
            }
            self.redo_stack.append(current_state)
            
            # Restore previous state
            state = self.undo_stack.pop()
            self.restore_state(state)
            
            logging.info(f"Undo performed (undo depth: {len(self.undo_stack)}, redo depth: {len(self.redo_stack)})")
        except Exception as e:
            logging.error(f"Error during undo: {e}", exc_info=True)
    
    def redo(self):
        """Restore next state from redo stack"""
        if not self.redo_stack:
            logging.info("Nothing to redo")
            return
        
        try:
            # Save current state to undo stack
            current_state = {
                'side_a': {
                    'image': self.side_a_editor.image.copy() if self.side_a_editor.image else None,
                    'original_image': self.side_a_editor.original_image.copy() if self.side_a_editor.original_image else None,
                    'base_image': self.side_a_editor.base_image.copy() if self.side_a_editor.base_image else None,
                    'scale_factor': self.side_a_editor.scale_factor,
                    'offset_x': self.side_a_editor.offset_x,
                    'offset_y': self.side_a_editor.offset_y
                },
                'side_b': {
                    'image': self.side_b_editor.image.copy() if self.side_b_editor.image else None,
                    'original_image': self.side_b_editor.original_image.copy() if self.side_b_editor.original_image else None,
                    'base_image': self.side_b_editor.base_image.copy() if self.side_b_editor.base_image else None,
                    'scale_factor': self.side_b_editor.scale_factor,
                    'offset_x': self.side_b_editor.offset_x,
                    'offset_y': self.side_b_editor.offset_y
                },
                'cmyk': {
                    'c': self.c_slider.value(),
                    'm': self.m_slider.value(),
                    'y': self.y_slider.value(),
                    'k': self.k_slider.value()
                }
            }
            self.undo_stack.append(current_state)
            
            # Restore next state
            state = self.redo_stack.pop()
            self.restore_state(state)
            
            logging.info(f"Redo performed (undo depth: {len(self.undo_stack)}, redo depth: {len(self.redo_stack)})")
        except Exception as e:
            logging.error(f"Error during redo: {e}", exc_info=True)
    
    def restore_state(self, state):
        """Restore editor state from saved state dict"""
        try:
            # Restore side A
            if state['side_a']['image']:
                self.side_a_editor.image = state['side_a']['image'].copy()
                self.side_a_editor.original_image = state['side_a']['original_image'].copy()
                self.side_a_editor.base_image = state['side_a']['base_image'].copy()
                self.side_a_editor.scale_factor = state['side_a']['scale_factor']
                self.side_a_editor.offset_x = state['side_a']['offset_x']
                self.side_a_editor.offset_y = state['side_a']['offset_y']
                self.side_a_editor.update()
            
            # Restore side B
            if state['side_b']['image']:
                self.side_b_editor.image = state['side_b']['image'].copy()
                self.side_b_editor.original_image = state['side_b']['original_image'].copy()
                self.side_b_editor.base_image = state['side_b']['base_image'].copy()
                self.side_b_editor.scale_factor = state['side_b']['scale_factor']
                self.side_b_editor.offset_x = state['side_b']['offset_x']
                self.side_b_editor.offset_y = state['side_b']['offset_y']
                self.side_b_editor.update()
            
            # Restore CMYK sliders
            self.c_slider.blockSignals(True)
            self.m_slider.blockSignals(True)
            self.y_slider.blockSignals(True)
            self.k_slider.blockSignals(True)
            
            self.c_slider.setValue(state['cmyk']['c'])
            self.m_slider.setValue(state['cmyk']['m'])
            self.y_slider.setValue(state['cmyk']['y'])
            self.k_slider.setValue(state['cmyk']['k'])
            
            self.c_slider.blockSignals(False)
            self.m_slider.blockSignals(False)
            self.y_slider.blockSignals(False)
            self.k_slider.blockSignals(False)
            
            logging.info("State restored successfully")
        except Exception as e:
            logging.error(f"Error restoring state: {e}", exc_info=True)
    
    def sync_position(self, target_side, dx, dy):
        """Sync position changes to the other side when in BOTH mode"""
        if self.current_side == 'BOTH':
            target_editor = getattr(self, f"{target_side}_editor")
            target_editor.offset_x += dx
            target_editor.offset_y += dy
            target_editor.update()
    
    def sync_eraser(self, target_side, x, y, size):
        """Sync eraser operations to the other side when in BOTH mode"""
        if self.current_side == 'BOTH':
            target_editor = getattr(self, f"{target_side}_editor")
            if target_editor.image:
                img_width, img_height = target_editor.image.size
                if 0 <= x < img_width and 0 <= y < img_height:
                    draw = ImageDraw.Draw(target_editor.image)
                    eraser_radius = size
                    bbox = [x - eraser_radius, y - eraser_radius, x + eraser_radius, y + eraser_radius]
                    draw.ellipse(bbox, fill=(0, 0, 0, 0))
                    target_editor.update()
    
    def change_mode(self, mode):
        mode_map = {
            "Просмотр": "view",
            "Перемещение": "move",
            "Ластик": "eraser"
        }
        self.side_a_editor.current_mode = mode_map[mode]
        self.side_b_editor.current_mode = mode_map[mode]
        
        # Show/hide mode-specific controls
        self.eraser_control.setVisible(mode == "Ластик")
        self.move_hint.setVisible(mode == "Перемещение")
        
        # Set cursor
        if mode == "Ластик":
            self.side_a_editor.setCursor(QCursor(Qt.CursorShape.CrossCursor))
            self.side_b_editor.setCursor(QCursor(Qt.CursorShape.CrossCursor))
        elif mode == "Перемещение":
            self.side_a_editor.setCursor(QCursor(Qt.CursorShape.OpenHandCursor))
            self.side_b_editor.setCursor(QCursor(Qt.CursorShape.OpenHandCursor))
        else:
            self.side_a_editor.setCursor(QCursor(Qt.CursorShape.ArrowCursor))
            self.side_b_editor.setCursor(QCursor(Qt.CursorShape.ArrowCursor))
    
    def change_eraser_size(self, size):
        self.side_a_editor.eraser_size = size
        self.side_b_editor.eraser_size = size
    
    def apply_cmyk(self):
        c = self.c_slider.value() * 2.55
        m = self.m_slider.value() * 2.55
        y = self.y_slider.value() * 2.55
        k = self.k_slider.value() * 2.55
        
        # Apply based on current side mode
        if self.current_side == 'BOTH':
            self.side_a_editor.apply_cmyk_color(c, m, y, k)
            self.side_b_editor.apply_cmyk_color(c, m, y, k)
        elif self.current_side == 'A':
            self.side_a_editor.apply_cmyk_color(c, m, y, k)
        elif self.current_side == 'B':
            self.side_b_editor.apply_cmyk_color(c, m, y, k)
    
    def apply_zoom(self, factor):
        # Apply based on current side mode
        if self.current_side == 'BOTH':
            self.side_a_editor.zoom_image(factor)
            self.side_b_editor.zoom_image(factor)
        elif self.current_side == 'A':
            self.side_a_editor.zoom_image(factor)
        elif self.current_side == 'B':
            self.side_b_editor.zoom_image(factor)
    
    def reset_position(self):
        self.side_a_editor.reset_position()
        self.side_b_editor.reset_position()
    
    def reset_current_image(self):
        self.side_a_editor.reset_image()
        self.side_b_editor.reset_image()
        # Reset CMYK sliders
        self.c_slider.blockSignals(True)
        self.m_slider.blockSignals(True)
        self.y_slider.blockSignals(True)
        self.k_slider.blockSignals(True)
        self.c_slider.setValue(0)
        self.m_slider.setValue(0)
        self.y_slider.setValue(0)
        self.k_slider.setValue(0)
        self.c_slider.blockSignals(False)
        self.m_slider.blockSignals(False)
        self.y_slider.blockSignals(False)
        self.k_slider.blockSignals(False)
    
    def get_config_path(self):
        return os.path.join(os.path.dirname(__file__), "company_config.json")

    def save_company_settings(self, name, address, phone, logo_path):
        data = {
            "company_name": name,
            "company_address": address,
            "company_phone": phone,
            "company_logo": logo_path
        }
        try:
            with open(self.get_config_path(), "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
            self.organization_data = {
                "name": name,
                "logo_path": logo_path,
                "address": address,
                "phone": phone,
            }
            return True
        except Exception as exc:
            logging.error(f"Ошибка сохранения конфигурации: {exc}")
            return False

    def load_company_settings(self):
        config_path = self.get_config_path()
        if os.path.exists(config_path):
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return {
                    "company_name": data.get("company_name", ""),
                    "company_address": data.get("company_address", ""),
                    "company_phone": data.get("company_phone", ""),
                    "company_logo": data.get("company_logo", "")
                }
            except Exception as exc:
                logging.error(f"Ошибка загрузки конфигурации: {exc}")
        return {"company_name": "", "company_address": "", "company_phone": "", "company_logo": ""}

    def load_organization_config(self):
        settings = self.load_company_settings()
        return {
            "name": settings.get("company_name", ""),
            "logo_path": settings.get("company_logo", ""),
            "address": settings.get("company_address", ""),
            "phone": settings.get("company_phone", "")
        }

    def save_organization_config(self, data):
        return self.save_company_settings(
            data.get("name", ""),
            data.get("address", ""),
            data.get("phone", ""),
            data.get("logo_path", "")
        )

    def open_organization_info_dialog(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Информация об организации")
        dialog.setMinimumWidth(480)

        form = QFormLayout(dialog)
        name_edit = QLineEdit(self.organization_data.get("name", ""))
        logo_edit = QLineEdit(self.organization_data.get("logo_path", ""))
        address_edit = QLineEdit(self.organization_data.get("address", ""))
        phone_edit = QLineEdit(self.organization_data.get("phone", ""))

        form.addRow("Название:", name_edit)
        form.addRow("Логотип:", logo_edit)
        form.addRow("", QPushButton("Выбрать файл", dialog))
        form.addRow("Адрес:", address_edit)
        form.addRow("Телефон:", phone_edit)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        form.addRow(buttons)

        select_logo_btn = dialog.findChild(QPushButton)
        if select_logo_btn is not None:
            select_logo_btn.clicked.connect(lambda: self.select_org_logo(logo_edit))

        def handle_save():
            data = {
                "name": name_edit.text().strip(),
                "logo_path": logo_edit.text().strip(),
                "address": address_edit.text().strip(),
                "phone": phone_edit.text().strip(),
            }
            if self.save_organization_config(data):
                QMessageBox.information(self, "Успех", "Данные организации сохранены")
                dialog.accept()
            else:
                QMessageBox.critical(self, "Ошибка", "Не удалось сохранить данные организации")

        buttons.accepted.connect(handle_save)
        buttons.rejected.connect(dialog.reject)
        dialog.exec()

    def select_org_logo(self, logo_edit):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Выберите логотип организации",
            "",
            "Изображения (*.png *.jpg *.jpeg *.bmp *.tiff)"
        )
        if file_path:
            logo_edit.setText(normalize_path(file_path))

    def save_order(self):
        if not self.side_a_editor.get_image() and not self.side_b_editor.get_image():
            QMessageBox.warning(self, "Ошибка", "Загрузите хотя бы одно изображение")
            return
        
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        print_specs = json.dumps({
            "quantity": self.print_quantity.value(),
            "print_type": self.print_type.currentText(),
            "paper_type": self.paper_type.currentText(),
            "lamination": self.lamination.currentText(),
            "additional": self.additional_specs.toPlainText(),
            "customer_contact": self.customer_contact_person.text().strip(),
            "order_number": self.order_number.text().strip(),
            "production_deadline": self.production_deadline.text().strip()
        })
        
        cursor.execute('''
            INSERT INTO orders (customer_name, customer_phone, customer_email, 
                              company_name, print_specs, side_a_path, side_b_path, 
                              created_at, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            self.customer_name.text(),
            self.customer_phone.text(),
            self.customer_email.text(),
            self.company_name.text(),
            print_specs,
            self.current_order.get("side_a_path", ""),
            self.current_order.get("side_b_path", ""),
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "Черновик"
        ))
        
        conn.commit()
        conn.close()
        
        QMessageBox.information(self, "Успех", "Заказ сохранен!")
        self.load_orders()
    
    def load_orders(self):
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        cursor.execute('SELECT id, customer_name, company_name, created_at, print_specs, status FROM orders ORDER BY created_at DESC')
        orders = cursor.fetchall()
        
        conn.close()
        
        self.orders_table.setRowCount(len(orders))
        
        for row, order in enumerate(orders):
            order_id, customer, company, date, specs_json, status = order
            
            specs = json.loads(specs_json)
            quantity = specs.get("quantity", 0)
            
            self.orders_table.setItem(row, 0, QTableWidgetItem(str(order_id)))
            self.orders_table.setItem(row, 1, QTableWidgetItem(customer))
            self.orders_table.setItem(row, 2, QTableWidgetItem(company))
            self.orders_table.setItem(row, 3, QTableWidgetItem(date))
            self.orders_table.setItem(row, 4, QTableWidgetItem(str(quantity)))
            self.orders_table.setItem(row, 5, QTableWidgetItem(status))
            
            action_btn = QPushButton("Открыть")
            action_btn.clicked.connect(lambda checked, oid=order_id: self.load_order(oid))
            self.orders_table.setCellWidget(row, 6, action_btn)
    
    def load_order(self, order_id):
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM orders WHERE id = ?', (order_id,))
        order = cursor.fetchone()
        
        conn.close()
        
        if order:
            _, customer_name, customer_phone, customer_email, company_name, print_specs, side_a, side_b, created_at, status = order
            
            self.customer_name.setText(customer_name)
            self.customer_phone.setText(customer_phone)
            self.customer_email.setText(customer_email)
            self.company_name.setText(company_name)
            
            specs = json.loads(print_specs)
            self.print_quantity.setValue(specs.get("quantity", 100))
            self.print_type.setCurrentText(specs.get("print_type", "Цифровая печать"))
            self.paper_type.setCurrentText(specs.get("paper_type", "Пластик PVC"))
            self.lamination.setCurrentText(specs.get("lamination", "Без ламинации"))
            self.additional_specs.setText(specs.get("additional", ""))
            self.customer_contact_person.setText(specs.get("customer_contact", ""))
            self.order_number.setText(specs.get("order_number", ""))
            self.production_deadline.setText(specs.get("production_deadline", ""))
            
            if side_a:
                self.side_a_editor.load_image(side_a)
                self.side_a_path_label.setText(side_a)
                self.current_order["side_a_path"] = side_a
            
            if side_b:
                self.side_b_editor.load_image(side_b)
                self.side_b_path_label.setText(side_b)
                self.current_order["side_b_path"] = side_b
            
            self.tab_widget.setCurrentIndex(0)
    
    def generate_commercial_offer_pdf(self):
        company_data = self.load_company_settings()
        comp_name = company_data.get("company_name", "Имя компании не указано")
        comp_address = company_data.get("company_address", "Адрес не указан")
        comp_phone = company_data.get("company_phone", "Телефон не указан")
        comp_logo = company_data.get("company_logo", "")

        image_a = self.side_a_editor.get_image()
        image_b = self.side_b_editor.get_image()

        if not image_a and not image_b:
            QMessageBox.warning(self, "Ошибка", "Нет изображений для генерации КП")
            return

        customer_name = self.customer_name.text().strip() or "Не указан"
        customer_phone = self.customer_phone.text().strip() or "Не указан"
        customer_email = self.customer_email.text().strip() or "Не указан"
        order_number = self.order_number.text().strip() or "Б/Н"
        production_deadline = self.production_deadline.text().strip() or "Не установлен"
        company_name = self.company_name.text().strip() or "—"
        print_quantity = str(self.print_quantity.value())
        print_type = self.print_type.currentText()
        paper_type = self.paper_type.currentText()
        lamination = self.lamination.currentText()
        additional = self.additional_specs.toPlainText().strip() or "—"

        default_filename = f"kp_order_{order_number}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Сохранить коммерческое предложение",
            default_filename,
            "PDF файлы (*.pdf)"
        )

        if not file_path:
            return

        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.lib import colors
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.units import mm
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle
            from reportlab.pdfbase import pdfmetrics
            from reportlab.pdfbase.ttfonts import TTFont

            doc = SimpleDocTemplate(file_path, pagesize=A4, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
            styles = getSampleStyleSheet()
            story = []

            base_dir = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
            font_candidates = [
                os.path.join(base_dir, "Arial.ttf"),
                os.path.join(base_dir, "fonts", "Arial.ttf"),
                os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts", "arial.ttf"),
            ]
            font_path = None
            for candidate in font_candidates:
                if os.path.exists(candidate):
                    font_path = candidate
                    break

            if font_path:
                pdfmetrics.registerFont(TTFont('CustomArial', font_path))
            else:
                logging.warning("Arial.ttf not found for КП PDF generation; falling back to default font")

            font_name = 'CustomArial' if font_path else 'Helvetica'
            title_style = ParagraphStyle('KPTitle', parent=styles['Heading1'], fontName=font_name, fontSize=18, leading=22, textColor=colors.HexColor("#0066cc"))
            normal_style = ParagraphStyle('KPNormal', parent=styles['Normal'], fontName=font_name, fontSize=10, leading=14)

            header_data = []
            company_info_text = f"<b>{comp_name}</b><br/>Адрес: {comp_address}<br/>Тел: {comp_phone}"

            if comp_logo and os.path.exists(comp_logo):
                try:
                    logo_img = Image(comp_logo, width=100, height=50)
                    header_data.append([logo_img, Paragraph(company_info_text, normal_style)])
                except Exception:
                    header_data.append(["", Paragraph(company_info_text, normal_style)])
            else:
                header_data.append(["", Paragraph(company_info_text, normal_style)])

            header_table = Table(header_data, colWidths=[120, 420])
            header_table.setStyle(TableStyle([
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
            ]))
            story.append(header_table)
            story.append(Spacer(1, 15))

            story.append(Paragraph(f"Коммерческое предложение по заказу № {order_number}", title_style))
            story.append(Paragraph(f"Дата создания: {datetime.now().strftime('%d.%m.%Y')}", normal_style))
            story.append(Spacer(1, 15))

            info_data = [
                [Paragraph("<b>Информация о заказчике:</b>", normal_style), Paragraph("<b>Параметры заказа:</b>", normal_style)],
                [
                    Paragraph(f"Заказчик: {customer_name}<br/>Телефон: {customer_phone}<br/>Email: {customer_email}", normal_style),
                    Paragraph(f"Срок изготовления: {production_deadline}<br/>Компания: {company_name}<br/>Тираж: {print_quantity}<br/>Тип печати: {print_type}<br/>Материал: {paper_type}<br/>Ламинация: {lamination}", normal_style)
                ]
            ]
            info_table = Table(info_data, colWidths=[270, 270])
            info_table.setStyle(TableStyle([
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
                ('PADDING', (0, 0), (-1, -1), 6),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ]))
            story.append(info_table)
            story.append(Spacer(1, 20))

            story.append(Paragraph("<b>Макет карты (Сторона А и Сторона Б):</b>", normal_style))
            story.append(Spacer(1, 10))

            images_data = []
            row_images = []

            for label, image_obj in (("Сторона А", image_a), ("Сторона Б", image_b)):
                if image_obj is not None:
                    try:
                        img_buffer = io.BytesIO()
                        image_obj.save(img_buffer, format='PNG')
                        img_buffer.seek(0)
                        row_images.append(Image(img_buffer, width=240, height=150))
                    except Exception:
                        row_images.append(Paragraph(f"[Ошибка загрузки {label}]", normal_style))
                else:
                    row_images.append(Paragraph(f"[{label} отсутствует]", normal_style))

            images_data.append(row_images)
            images_table = Table(images_data, colWidths=[270, 270])
            images_table.setStyle(TableStyle([
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ]))
            story.append(images_table)
            story.append(Spacer(1, 10))
            story.append(Paragraph("<b>Дополнительные характеристики:</b>", normal_style))
            story.append(Paragraph(additional, normal_style))

            doc.build(story)
            QMessageBox.information(self, "Успех", f"КП успешно сохранено:\n{file_path}")
        except Exception as e:
            error_msg = f"Не удалось сгенерировать PDF: {str(e)}\n\nTraceback:\n{traceback.format_exc()}"
            logging.error(error_msg)
            QMessageBox.critical(self, "Ошибка генерации КП", error_msg)

    def export_pdf(self):
        if not self.side_a_editor.get_image() and not self.side_b_editor.get_image():
            QMessageBox.warning(self, "Ошибка", "Нет изображений для экспорта")
            return
        
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Сохранить PDF",
            f"card_print_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
            "PDF файлы (*.pdf)"
        )
        
        if file_path:
            try:
                from reportlab.lib.pagesizes import mm
                from reportlab.platypus import SimpleDocTemplate, Image, PageBreak
                from reportlab.lib import colors
                
                # Bank card size: 87x56mm
                doc = SimpleDocTemplate(
                    file_path,
                    pagesize=(87*mm, 56*mm),
                    rightMargin=0,
                    leftMargin=0,
                    topMargin=0,
                    bottomMargin=0
                )
                
                story = []
                
                # Hard max limits for image dimensions (points)
                max_width = 230
                max_height = 140
                
                # Side A
                if self.side_a_editor.get_image():
                    img_a = self.side_a_editor.get_image()
                    img_buffer = io.BytesIO()
                    img_a.save(img_buffer, format='PNG')
                    img_buffer.seek(0)
                    
                    # Calculate aspect ratio and scale to fit within hard limits
                    img_width, img_height = img_a.size
                    aspect_ratio = img_width / img_height
                    
                    # Scale to fit while maintaining aspect ratio
                    if aspect_ratio > (max_width / max_height):
                        # Width is the limiting factor
                        final_width = max_width
                        final_height = max_width / aspect_ratio
                    else:
                        # Height is the limiting factor
                        final_height = max_height
                        final_width = max_height * aspect_ratio
                    
                    rl_img = Image(img_buffer, width=final_width, height=final_height)
                    story.append(rl_img)
                
                # Side B (if exists)
                if self.side_b_editor.get_image():
                    story.append(PageBreak())
                    img_b = self.side_b_editor.get_image()
                    img_buffer = io.BytesIO()
                    img_b.save(img_buffer, format='PNG')
                    img_buffer.seek(0)
                    
                    # Calculate aspect ratio and scale to fit within hard limits
                    img_width, img_height = img_b.size
                    aspect_ratio = img_width / img_height
                    
                    # Scale to fit while maintaining aspect ratio
                    if aspect_ratio > (max_width / max_height):
                        # Width is the limiting factor
                        final_width = max_width
                        final_height = max_width / aspect_ratio
                    else:
                        # Height is the limiting factor
                        final_height = max_height
                        final_width = max_height * aspect_ratio
                    
                    rl_img = Image(img_buffer, width=final_width, height=final_height)
                    story.append(rl_img)
                
                doc.build(story)
                
                QMessageBox.information(self, "Успех", f"PDF сохранен: {file_path}")
                
            except Exception as e:
                error_msg = f"Не удалось создать PDF: {str(e)}\n\nTraceback:\n{traceback.format_exc()}"
                logging.error(error_msg)
                QMessageBox.critical(self, "Ошибка экспорта PDF", error_msg)

def main():
    logging.info("=" * 50)
    logging.info("UF Print Application Starting")
    logging.info("Version: 2.0 (with zoom, move, eraser fixes)")
    logging.info("=" * 50)
    
    app = QApplication(sys.argv)
    window = CardPrintingApp()
    window.show()
    
    logging.info("Application window shown successfully")
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
