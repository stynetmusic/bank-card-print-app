import sys
import os
import json
import sqlite3
from datetime import datetime
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLabel, QPushButton, QFileDialog, 
                             QTabWidget, QTextEdit, QLineEdit, QFormLayout, 
                             QGroupBox, QSplitter, QScrollArea, QMessageBox,
                             QSlider, QComboBox, QCheckBox, QSpinBox, QDialog,
                             QDialogButtonBox, QTableWidget, QTableWidgetItem,
                             QHeaderView, QFrame)
from PyQt5.QtCore import Qt, QSize, QTimer, QRect
from PyQt5.QtGui import QPixmap, QImage, QIcon, QPainter, QColor, QPen, QBrush, QFont
from PIL import Image, ImageDraw, ImageQt
import io

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
        self.current_mode = "view"  # view, stretch, shrink, eraser
        self.eraser_size = 20
        self.cmyk_values = {"C": 0, "M": 0, "Y": 0, "K": 0}
        self.scale_factor = 1.0
        self.setMouseTracking(True)
        self.setMinimumSize(348, 224)  # 87x56mm at 100 DPI
        self.setStyleSheet("background-color: #f0f0f0; border: 2px solid #00ff00;")
        
    def load_image(self, path):
        try:
            self.original_image = Image.open(path).convert("RGBA")
            self.image = self.original_image.copy()
            self.update()
            return True
        except Exception as e:
            print(f"Error loading image: {e}")
            return False
    
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(240, 240, 240))
        
        if self.image:
            # Scale image to fit widget while maintaining aspect ratio
            img_width, img_height = self.image.size
            widget_width = self.width()
            widget_height = self.height()
            
            scale_x = widget_width / img_width
            scale_y = widget_height / img_height
            self.scale_factor = min(scale_x, scale_y)
            
            new_width = int(img_width * self.scale_factor)
            new_height = int(img_height * self.scale_factor)
            
            # Center the image
            x = (widget_width - new_width) // 2
            y = (widget_height - new_height) // 2
            
            qimage = ImageQt.ImageQt(self.image)
            pixmap = QPixmap.fromImage(qimage)
            painter.drawPixmap(x, y, pixmap.scaled(new_width, new_height, Qt.AspectRatioMode.KeepAspectRatio))
        else:
            painter.setPen(QPen(QColor(150, 150, 150), 2))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Загрузите изображение\n(87x56mm)")
    
    def mousePressEvent(self, event):
        if self.current_mode == "eraser" and self.image:
            self.apply_eraser(event.position())
    
    def mouseMoveEvent(self, event):
        if self.current_mode == "eraser" and event.buttons() & Qt.MouseButton.LeftButton and self.image:
            self.apply_eraser(event.position())
    
    def apply_eraser(self, pos):
        if not self.image:
            return
            
        img_width, img_height = self.image.size
        widget_width = self.width()
        widget_height = self.height()
        
        # Convert widget coordinates to image coordinates
        x = int((pos.x() - (widget_width - img_width * self.scale_factor) // 2) / self.scale_factor)
        y = int((pos.y() - (widget_height - img_height * self.scale_factor) // 2) / self.scale_factor)
        
        if 0 <= x < img_width and 0 <= y < img_height:
            draw = ImageDraw.Draw(self.image)
            eraser_radius = self.eraser_size
            bbox = [x - eraser_radius, y - eraser_radius, x + eraser_radius, y + eraser_radius]
            draw.ellipse(bbox, fill=(0, 0, 0, 0))
            self.update()
    
    def stretch_image(self, factor):
        if self.image:
            width, height = self.image.size
            new_width = int(width * factor)
            new_height = int(height * factor)
            self.image = self.image.resize((new_width, new_height), Image.Resampling.LANCZOS)
            self.update()
    
    def shrink_image(self, factor):
        if self.image:
            width, height = self.image.size
            new_width = int(width / factor)
            new_height = int(height / factor)
            self.image = self.image.resize((new_width, new_height), Image.Resampling.LANCZOS)
            self.update()
    
    def apply_cmyk_color(self, c, m, y, k):
        if self.image:
            # Simple CMYK adjustment
            pixels = self.image.load()
            for i in range(self.image.width):
                for j in range(self.image.height):
                    r, g, b, a = pixels[i, j]
                    # Apply CMYK color shift
                    r = max(0, min(255, r - c))
                    g = max(0, min(255, g - m))
                    b = max(0, min(255, b - y))
                    brightness = 1 - (k / 255)
                    r = int(r * brightness)
                    g = int(g * brightness)
                    b = int(b * brightness)
                    pixels[i, j] = (r, g, b, a)
            self.update()
    
    def get_image(self):
        return self.image
    
    def reset_image(self):
        if self.original_image:
            self.image = self.original_image.copy()
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
            QLineEdit, QTextEdit, QComboBox, QSpinBox {
                background-color: #0f3460;
                color: #ffffff;
                border: 1px solid #00ff00;
                padding: 5px;
                border-radius: 3px;
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
        self.mode_combo.addItems(["Просмотр", "Растянуть", "Уменьшить", "Ластик"])
        self.mode_combo.currentTextChanged.connect(self.change_mode)
        layout.addWidget(self.mode_combo)
        
        # Eraser size
        layout.addWidget(QLabel("Размер ластика:"))
        self.eraser_slider = QSlider(Qt.Orientation.Horizontal)
        self.eraser_slider.setRange(5, 50)
        self.eraser_slider.setValue(20)
        self.eraser_slider.valueChanged.connect(self.change_eraser_size)
        layout.addWidget(self.eraser_slider)
        
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
        
        stretch_btn = QPushButton("Растянуть x1.1")
        stretch_btn.clicked.connect(lambda: self.apply_transform("stretch"))
        layout.addWidget(stretch_btn)
        
        shrink_btn = QPushButton("Уменьшить x0.9")
        shrink_btn.clicked.connect(lambda: self.apply_transform("shrink"))
        layout.addWidget(shrink_btn)
        
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
            editor = getattr(self, f"{side_key}_editor")
            if editor.load_image(file_path):
                path_label = getattr(self, f"{side_key}_path_label")
                path_label.setText(file_path)
                self.current_order[f"{side_key}_path"] = file_path
                QMessageBox.information(self, "Успех", "Изображение загружено!")
            else:
                QMessageBox.warning(self, "Ошибка", "Не удалось загрузить изображение")
    
    def change_mode(self, mode):
        mode_map = {
            "Просмотр": "view",
            "Растянуть": "stretch",
            "Уменьшить": "shrink",
            "Ластик": "eraser"
        }
        self.side_a_editor.current_mode = mode_map[mode]
        self.side_b_editor.current_mode = mode_map[mode]
    
    def change_eraser_size(self, size):
        self.side_a_editor.eraser_size = size
        self.side_b_editor.eraser_size = size
    
    def apply_cmyk(self):
        c = self.c_slider.value() * 2.55
        m = self.m_slider.value() * 2.55
        y = self.y_slider.value() * 2.55
        k = self.k_slider.value() * 2.55
        
        # Apply to currently focused editor (simple approach: both)
        self.side_a_editor.apply_cmyk_color(c, m, y, k)
        self.side_b_editor.apply_cmyk_color(c, m, y, k)
    
    def apply_transform(self, transform):
        if transform == "stretch":
            self.side_a_editor.stretch_image(1.1)
            self.side_b_editor.stretch_image(1.1)
        elif transform == "shrink":
            self.side_a_editor.shrink_image(0.9)
            self.side_b_editor.shrink_image(0.9)
    
    def reset_current_image(self):
        self.side_a_editor.reset_image()
        self.side_b_editor.reset_image()
        # Reset CMYK sliders
        self.c_slider.setValue(0)
        self.m_slider.setValue(0)
        self.y_slider.setValue(0)
        self.k_slider.setValue(0)
    
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
                
                # Side A
                if self.side_a_editor.get_image():
                    img_a = self.side_a_editor.get_image()
                    img_buffer = io.BytesIO()
                    img_a.save(img_buffer, format='PNG')
                    img_buffer.seek(0)
                    
                    rl_img = Image(img_buffer, width=87*mm, height=56*mm)
                    story.append(rl_img)
                
                # Side B (if exists)
                if self.side_b_editor.get_image():
                    story.append(PageBreak())
                    img_b = self.side_b_editor.get_image()
                    img_buffer = io.BytesIO()
                    img_b.save(img_buffer, format='PNG')
                    img_buffer.seek(0)
                    
                    rl_img = Image(img_buffer, width=87*mm, height=56*mm)
                    story.append(rl_img)
                
                doc.build(story)
                
                QMessageBox.information(self, "Успех", f"PDF сохранен: {file_path}")
                
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Не удалось создать PDF: {str(e)}")

def main():
    app = QApplication(sys.argv)
    window = CardPrintingApp()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
