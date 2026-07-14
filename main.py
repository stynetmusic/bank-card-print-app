import sys
import os
import json
import sqlite3
import logging
import traceback
from datetime import datetime
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLabel, QPushButton, QFileDialog, 
                             QTabWidget, QTextEdit, QLineEdit, QFormLayout, 
                             QGroupBox, QSplitter, QScrollArea, QMessageBox,
                             QSlider, QComboBox, QCheckBox, QSpinBox, QDialog,
                             QDialogButtonBox, QTableWidget, QTableWidgetItem,
                             QHeaderView, QFrame)
from PyQt5.QtCore import Qt, QSize, QTimer, QRect, QPoint
from PyQt5.QtGui import QPixmap, QImage, QIcon, QPainter, QColor, QPen, QBrush, QFont, QCursor
from PIL import Image, ImageDraw
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
    """Convert PIL Image to QPixmap using raw data (fast, no compression)"""
    try:
        # Convert to RGBA if needed
        if pil_img.mode != "RGBA":
            pil_img = pil_img.convert("RGBA")
        
        # Get raw pixel bytes without PNG compression
        data = pil_img.tobytes("raw", "RGBA")
        
        # Create QImage directly from memory
        qimg = QImage(data, pil_img.size[0], pil_img.size[1], QImage.Format_RGBA8888)
        
        # Important: keep reference to data to prevent Qt crash
        qimg.bits().setsize(pil_img.size[0] * pil_img.size[1] * 4)
        
        return QPixmap.fromImage(qimg)
    except Exception as e:
        logging.error(f"Error converting PIL to QPixmap: {e}", exc_info=True)
        return None

# Database setup
DB_NAME = "card_printing.db"

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
        self.setStyleSheet("background-color: #f0f0f0; border: 2px solid #00ff00;")
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.position_callback = None  # Callback for sync mode
        self.eraser_callback = None  # Callback for sync eraser
        self.click_callback = None  # Callback for side selection
        
    def load_image(self, path):
        try:
            logging.info(f"Attempting to load image: {path}")
            
            # Check if path exists (handle both forward and back slashes)
            if not os.path.exists(path):
                # Try alternative path formats for Windows/Parallels
                alt_path = path.replace('/', '\\')
                if os.path.exists(alt_path):
                    path = alt_path
                    logging.info(f"Using alternative path format: {path}")
                else:
                    error_msg = f"Файл не существует: {path}\nПробованный альтернативный путь: {alt_path}"
                    logging.error(error_msg)
                    return False, error_msg
            
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
        painter.fillRect(self.rect(), QColor(240, 240, 240))
        
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
            painter.setPen(QPen(QColor(150, 150, 150), 2))
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
        
        # Colorful UF Print style
        self.setStyleSheet("""
            QMainWindow {
                background-color: #1a1a2e;
            }
            QWidget {
                color: #ffffff;
                font-family: Arial, sans-serif;
            }
            QTabWidget::pane {
                border: 2px solid #00ff00;
                background-color: #16213e;
            }
            QTabBar::tab {
                background-color: #0f3460;
                color: #ffffff;
                padding: 10px 20px;
                border: 1px solid #00ff00;
            }
            QTabBar::tab:selected {
                background-color: #00ff00;
                color: #1a1a2e;
            }
            QPushButton {
                background-color: #00ff00;
                color: #1a1a2e;
                border: none;
                padding: 10px 20px;
                font-weight: bold;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #00cc00;
            }
            QPushButton#zoomButton {
                background-color: #00ff00;
                color: #000000;
                font-weight: bold;
                font-size: 16px;
            }
            QLineEdit, QTextEdit, QComboBox, QSpinBox {
                background-color: #0f3460;
                color: #ffffff;
                border: 1px solid #00ff00;
                padding: 5px;
                border-radius: 3px;
            }
            QComboBox QAbstractItemView {
                background-color: #0f3460;
                color: #ffffff;
                selection-background-color: #00ff00;
                selection-color: #1a1a2e;
            }
            QComboBox::drop-down {
                border: 1px solid #00ff00;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 5px solid #00ff00;
                width: 0;
                height: 0;
            }
            QGroupBox {
                border: 2px solid #00ff00;
                border-radius: 5px;
                margin-top: 10px;
                font-weight: bold;
                color: #00ff00;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
            QLabel {
                color: #ffffff;
            }
            QTableWidget {
                background-color: #0f3460;
                color: #ffffff;
                border: 1px solid #00ff00;
                gridline-color: #00ff00;
            }
            QTableWidget::item {
                padding: 5px;
            }
            QHeaderView::section {
                background-color: #00ff00;
                color: #1a1a2e;
                padding: 5px;
                border: 1px solid #00ff00;
            }
            QSlider::groove:horizontal {
                height: 8px;
                background: #0f3460;
                border: 1px solid #00ff00;
                border-radius: 4px;
            }
            QSlider::handle:horizontal {
                background: #00ff00;
                width: 16px;
                margin: -4px 0;
                border-radius: 8px;
            }
        """)
        
        init_db()
        self.current_order = {}
        self.current_side = 'BOTH'  # 'A', 'B', or 'BOTH' for synchronous editing
        self.init_ui()
        
    def init_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)
        
        # Header
        header = QLabel("UF PRINT - СИСТЕМА ДЛЯ ПЕЧАТИ БАНКОВСКИХ КАРТ")
        header.setStyleSheet("font-size: 24px; font-weight: bold; color: #00ff00; padding: 10px;")
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(header)
        
        # Tab widget
        self.tab_widget = QTabWidget()
        main_layout.addWidget(self.tab_widget)
        
        # Create tabs
        self.create_editor_tab()
        self.create_customer_tab()
        self.create_history_tab()
        
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
        elif side_key == "side_b":
            editor.position_callback = lambda dx, dy: self.sync_position("side_a", dx, dy)
            editor.eraser_callback = lambda x, y, size: self.sync_eraser("side_a", x, y, size)
            editor.click_callback = lambda: self.on_editor_click("side_b")
        
        layout.addWidget(editor)
        
        # Load button
        load_btn = QPushButton(f"Загрузить {title}")
        load_btn.clicked.connect(lambda: self.load_image(side_key))
        layout.addWidget(load_btn)
        
        # Path label
        path_label = QLabel("Файл не выбран")
        path_label.setStyleSheet("color: #00ff00; font-size: 11px;")
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
        self.move_hint.setStyleSheet("color: #00ff00; font-size: 11px; padding: 5px;")
        self.move_hint.setVisible(False)
        mode_controls_layout.addWidget(self.move_hint)
        logging.info("Move hint added to layout")
        
        layout.addWidget(self.mode_controls)
        logging.info("Mode controls added to layout")
        
        # Sync editing mode checkbox
        self.sync_checkbox = QCheckBox("Синхронное редактирование обеих сторон")
        self.sync_checkbox.setChecked(True)  # Default to BOTH mode
        self.sync_checkbox.setStyleSheet("color: #00ff00; padding: 5px;")
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

        # Commercial offer (КП) button
        self.btn_kp = QPushButton("Сформировать КП")
        self.btn_kp.clicked.connect(self.generate_commercial_offer_pdf)
        layout.addWidget(self.btn_kp)
        
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
            # Normalize path for Parallels/Windows compatibility
            normalized_path = os.path.abspath(os.path.normpath(file_path))
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
            self.side_a_editor.setStyleSheet("background-color: #f0f0f0; border: 2px solid #00ff00;")
            self.side_b_editor.setStyleSheet("background-color: #f0f0f0; border: 2px solid #00ff00;")
        elif self.current_side == 'A':
            self.side_a_editor.setStyleSheet("background-color: #f0f0f0; border: 3px solid #00ff00;")
            self.side_b_editor.setStyleSheet("background-color: #f0f0f0; border: 1px solid #666666;")
        elif self.current_side == 'B':
            self.side_a_editor.setStyleSheet("background-color: #f0f0f0; border: 1px solid #666666;")
            self.side_b_editor.setStyleSheet("background-color: #f0f0f0; border: 3px solid #00ff00;")
    
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
            "additional": self.additional_specs.toPlainText()
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
            _, customer, company, print_specs, side_a, side_b, created_at, status = order
            
            self.customer_name.setText(customer)
            self.company_name.setText(company)
            
            specs = json.loads(print_specs)
            self.print_quantity.setValue(specs.get("quantity", 100))
            self.print_type.setCurrentText(specs.get("print_type", "Цифровая печать"))
            self.paper_type.setCurrentText(specs.get("paper_type", "Пластик PVC"))
            self.lamination.setCurrentText(specs.get("lamination", "Без ламинации"))
            self.additional_specs.setText(specs.get("additional", ""))
            
            if side_a:
                self.side_a_editor.load_image(side_a)
                self.side_a_path_label.setText(side_a)
                self.current_order["side_a_path"] = side_a
            
            if side_b:
                self.side_b_editor.load_image(side_b)
                self.side_b_path_label.setText(side_b)
                self.current_order["side_b_path"] = side_b
            
            self.tab_widget.setCurrentIndex(0)
    
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
                from reportlab.lib.units import mm
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

    def generate_commercial_offer_pdf(self):
        """Формирование полноценного PDF-документа коммерческого предложения (КП)"""
        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.units import mm
            from reportlab.lib import colors
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.enums import TA_CENTER, TA_RIGHT
            from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer,
                                            Table, TableStyle, HRFlowable)
            from reportlab.pdfbase import pdfmetrics
            from reportlab.pdfbase.ttfonts import TTFont
            import platform

            # --- Сбор данных о заказе из интерфейса ---
            customer = self.customer_name.text().strip() or "—"
            phone = self.customer_phone.text().strip() or "—"
            email = self.customer_email.text().strip() or "—"
            company = self.company_name.text().strip() or "—"

            quantity = self.print_quantity.value()
            print_type = self.print_type.currentText()
            material = self.paper_type.currentText()
            lamination = self.lamination.currentText()
            additional = self.additional_specs.toPlainText().strip()

            # --- Простая прозрачная модель ценообразования ---
            base_price = {
                "Цифровая печать": 15.0,
                "Офсетная печать": 8.0,
                "УФ печать": 25.0,
            }.get(print_type, 15.0)

            material_mult = {
                "Пластик PVC": 1.0,
                "Пластик PET": 1.2,
                "Комбинированный": 1.5,
            }.get(material, 1.0)

            lamination_add = {
                "Без ламинации": 0.0,
                "Матовая": 3.0,
                "Глянцевая": 3.0,
                "Soft Touch": 6.0,
            }.get(lamination, 0.0)

            price_per_unit = round((base_price + lamination_add) * material_mult, 2)
            total = round(price_per_unit * quantity, 2)

            # --- Имя файла КП ---
            now = datetime.now()
            file_path, _ = QFileDialog.getSaveFileName(
                self,
                "Сохранить коммерческое предложение",
                "КП_Заказ.pdf",
                "PDF файлы (*.pdf)"
            )
            if not file_path:
                return
            if not file_path.lower().endswith(".pdf"):
                file_path += ".pdf"

            # Регистрируем шрифт с поддержкой кириллицы (надёжный поиск по ОС)
            font_name = "Helvetica"
            local_font = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Arial.ttf")
            sys_name = platform.system()
            if sys_name == "Darwin":  # macOS
                possible_paths = [
                    "/System/Library/Fonts/Supplemental/Arial.ttf",
                    "/Library/Fonts/Arial.ttf",
                    local_font,
                ]
            elif sys_name == "Windows":
                possible_paths = [
                    "C:\\Windows\\Fonts\\arial.ttf",
                    local_font,
                ]
            else:  # Linux и пр.
                possible_paths = [
                    local_font,
                    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                    "/usr/share/fonts/TTF/DejaVuSans.ttf",
                ]
            for path in possible_paths:
                if os.path.exists(path):
                    try:
                        pdfmetrics.registerFont(TTFont("Arial", path))
                        font_name = "Arial"
                        break
                    except Exception as e:
                        logging.warning(f"Не удалось зарегистрировать шрифт {path}: {e}")

            # --- Стили ---
            styles = getSampleStyleSheet()
            title_style = ParagraphStyle("TitleCyr", parent=styles["Title"],
                                         fontName=font_name, fontSize=20, leading=24,
                                         alignment=TA_CENTER, textColor=colors.HexColor("#1a1a2e"))
            h_style = ParagraphStyle("HeadingCyr", parent=styles["Heading2"],
                                     fontName=font_name, fontSize=13, leading=16,
                                     textColor=colors.HexColor("#0f3460"))
            normal_style = ParagraphStyle("NormalCyr", parent=styles["Normal"],
                                          fontName=font_name, fontSize=10, leading=14)
            small_style = ParagraphStyle("SmallCyr", parent=styles["Normal"],
                                         fontName=font_name, fontSize=8, leading=11,
                                         textColor=colors.HexColor("#555555"))
            center_style = ParagraphStyle("CenterCyr", parent=normal_style, alignment=TA_CENTER)

            story = []

            # Шапка
            story.append(Paragraph("UF Print", ParagraphStyle(
                "Brand", parent=styles["Normal"], fontName=font_name, fontSize=14,
                leading=16, textColor=colors.HexColor("#00aa00"), spaceAfter=2)))
            story.append(Paragraph("Коммерческое предложение", title_style))
            story.append(Paragraph(f"Дата: {now.strftime('%d.%m.%Y')}", center_style))
            story.append(Spacer(1, 6))
            story.append(HRFlowable(width="100%", thickness=1.2, color=colors.HexColor("#00aa00")))
            story.append(Spacer(1, 10))

            # Данные заказчика
            story.append(Paragraph("Данные заказчика", h_style))
            client_data = [
                ["Заказчик:", customer],
                ["Организация:", company],
                ["Телефон:", phone],
                ["Email:", email],
            ]
            client_table = Table(client_data, colWidths=[35 * mm, 140 * mm])
            client_table.setStyle(TableStyle([
                ("FONTNAME", (0, 0), (-1, -1), font_name),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#0f3460")),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
            ]))
            story.append(client_table)
            story.append(Spacer(1, 12))

            # Таблица позиций
            story.append(Paragraph("Параметры заказа и стоимость", h_style))
            story.append(Spacer(1, 4))

            header = ["№", "Наименование услуги", "Кол-во", "Цена за ед., руб.", "Сумма, руб."]
            rows = [header, [
                "1",
                Paragraph(
                    f"<b>Печать банковских карт</b><br/><font size=8>"
                    f"Тип печати: {print_type}; Материал: {material}; Ламинация: {lamination}</font>",
                    normal_style),
                str(quantity),
                f"{price_per_unit:,.2f}".replace(",", " "),
                f"{total:,.2f}".replace(",", " "),
            ]]

            items_table = Table(rows, colWidths=[10 * mm, 95 * mm, 20 * mm, 30 * mm, 30 * mm],
                                repeatRows=1)
            items_table.setStyle(TableStyle([
                ("FONTNAME", (0, 0), (-1, -1), font_name),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f3460")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("ALIGN", (2, 0), (-1, -1), "RIGHT"),
                ("ALIGN", (0, 0), (0, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#999999")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f2f6ff")]),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]))
            story.append(items_table)
            story.append(Spacer(1, 8))

            # Итог
            story.append(Paragraph(
                f"Итого к оплате: {total:,.2f} руб.".replace(",", " "),
                ParagraphStyle("Total", parent=normal_style, alignment=TA_RIGHT, fontSize=12,
                               textColor=colors.HexColor("#0f3460"))))

            if additional:
                story.append(Spacer(1, 10))
                story.append(Paragraph("Дополнительные характеристики / пожелания:", h_style))
                story.append(Paragraph(additional.replace("\n", "<br/>"), normal_style))

            # Подвал
            story.append(Spacer(1, 16))
            story.append(HRFlowable(width="100%", thickness=0.6, color=colors.HexColor("#999999")))
            story.append(Spacer(1, 6))
            story.append(Paragraph(
                "Настоящее коммерческое предложение действительно в течение 14 календарных дней "
                "с даты выдачи. Окончательная стоимость может быть скорректирована после "
                "согласования макетов и технических требований. По всем вопросам: UF Print.",
                small_style))

            # --- Формирование документа ---
            doc = SimpleDocTemplate(
                file_path, pagesize=A4,
                leftMargin=18 * mm, rightMargin=18 * mm,
                topMargin=16 * mm, bottomMargin=16 * mm,
                title="Коммерческое предложение",
                author="UF Print",
            )
            doc.build(story)

            QMessageBox.information(self, "Успех", f"Коммерческое предложение сохранено:\n{file_path}")

        except Exception as e:
            error_msg = f"Не удалось сформировать КП: {str(e)}\n\nTraceback:\n{traceback.format_exc()}"
            logging.error(error_msg)
            QMessageBox.critical(self, "Ошибка формирования КП", error_msg)


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
