"""Main application window for UF Print."""

import logging
import os
import tempfile
import traceback
from datetime import datetime

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QCursor
from PyQt5.QtWidgets import (
    QAction,
    QComboBox,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSlider,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ufprint.color_dialog import ColorSettingsDialog
from ufprint import company_config
from ufprint import orders
from ufprint.editor import ImageEditor
from ufprint.paths import normalize_path
from ufprint.pdf_export import (
    export_commercial_offer_pdf,
    export_print_pdf,
    export_print_pdf_single,
)
from ufprint.styles import APP_STYLESHEET


class CardPrintingApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("UF Print - Банковские карты")
        self.setGeometry(100, 100, 1400, 900)

        self.setStyleSheet(APP_STYLESHEET)

        orders.init_db()
        self.current_order = {}
        self.current_side = "BOTH"  # 'A', 'B', or 'BOTH'
        self.organization_data = self.load_organization_config()
        self.undo_stack = []
        self.redo_stack = []
        self.max_history_depth = 30
        self.init_ui()

    def init_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)

        self._create_main_menu()

        header = QLabel("UF PRINT - СИСТЕМА ДЛЯ ПЕЧАТИ БАНКОВСКИХ КАРТ")
        header.setStyleSheet("font-size: 24px; font-weight: bold; color: #89b4fa; padding: 10px;")
        header.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(header)

        self.tab_widget = QTabWidget()
        main_layout.addWidget(self.tab_widget)

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

        left_panel = self.create_side_panel("Сторона А", "side_a")
        layout.addWidget(left_panel, 1)

        right_panel = self.create_side_panel("Сторона Б", "side_b")
        layout.addWidget(right_panel, 1)

        tools_panel = self.create_tools_panel()
        layout.addWidget(tools_panel, 0)

        self.tab_widget.addTab(editor_tab, "Редактор")

    def create_side_panel(self, title, side_key):
        panel = QGroupBox(title)
        layout = QVBoxLayout(panel)

        editor = ImageEditor()
        setattr(self, f"{side_key}_editor", editor)

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

        load_btn = QPushButton(f"Загрузить {title}")
        load_btn.clicked.connect(lambda: self.load_image(side_key))
        layout.addWidget(load_btn)

        path_label = QLabel("Файл не выбран")
        path_label.setStyleSheet("color: #a6adc8; font-size: 11px;")
        setattr(self, f"{side_key}_path_label", path_label)
        layout.addWidget(path_label)

        return panel

    def create_tools_panel(self):
        panel = QGroupBox("Инструменты")
        layout = QVBoxLayout(panel)

        layout.addWidget(QLabel("Режим:"))
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["Просмотр", "Перемещение", "Ластик"])
        self.mode_combo.currentTextChanged.connect(self.change_mode)
        layout.addWidget(self.mode_combo)

        self.mode_controls = QWidget()
        mode_controls_layout = QVBoxLayout(self.mode_controls)
        mode_controls_layout.setContentsMargins(0, 0, 0, 0)

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

        self.move_hint = QLabel("Перетаскивайте изображение мышкой\nили используйте стрелки")
        self.move_hint.setStyleSheet("color: #a6adc8; font-size: 11px; padding: 5px;")
        self.move_hint.setVisible(False)
        mode_controls_layout.addWidget(self.move_hint)
        logging.info("Move hint added to layout")

        layout.addWidget(self.mode_controls)
        logging.info("Mode controls added to layout")

        self.sync_checkbox = QCheckBox("Синхронное редактирование обеих сторон")
        self.sync_checkbox.setChecked(True)
        self.sync_checkbox.setStyleSheet("color: #a6adc8; padding: 5px;")
        self.sync_checkbox.stateChanged.connect(self.toggle_sync_mode)
        layout.addWidget(self.sync_checkbox)
        logging.info("Sync checkbox added to layout")

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

        color_settings_btn = QPushButton("Настройки цвета")
        color_settings_btn.clicked.connect(self.open_color_settings)
        layout.addWidget(color_settings_btn)

        reset_btn = QPushButton("Сбросить изображение")
        reset_btn.clicked.connect(self.reset_current_image)
        layout.addWidget(reset_btn)

        layout.addStretch()
        return panel

    def create_customer_tab(self):
        customer_tab = QWidget()
        layout = QVBoxLayout(customer_tab)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        customer_group = QGroupBox("Данные заказчика")
        customer_layout = QFormLayout(customer_group)

        self.customer_name = QLineEdit()
        customer_layout.addRow("Имя заказчика:", self.customer_name)

        self.customer_phone = QLineEdit()
        customer_layout.addRow("Телефон:", self.customer_phone)

        self.customer_email = QLineEdit()
        customer_layout.addRow("Email:", self.customer_email)

        splitter.addWidget(customer_group)

        company_group = QGroupBox("Данные компании и печати")
        company_layout = QFormLayout(company_group)

        self.company_name = QLineEdit()
        company_layout.addRow("Название компании:", self.company_name)

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
        self.lamination.addItems(["Без лака", "Матовый", "Глянцевый"])
        company_layout.addRow("Лак:", self.lamination)

        self.additional_specs = QTextEdit()
        self.additional_specs.setMaximumHeight(100)
        company_layout.addRow("Доп. характеристики:", self.additional_specs)

        splitter.addWidget(company_group)

        layout.addWidget(splitter)

        save_btn = QPushButton("Сохранить заказ")
        save_btn.clicked.connect(self.save_order)
        layout.addWidget(save_btn)

        export_btn = QPushButton("Экспорт в PDF (для печати)")
        export_btn.clicked.connect(self.export_pdf)
        layout.addWidget(export_btn)

        self.btn_export_a = QPushButton("Сторона А")
        self.btn_export_a.clicked.connect(self.export_pdf_side_a)
        layout.addWidget(self.btn_export_a)

        self.btn_export_b = QPushButton("Сторона Б")
        self.btn_export_b.clicked.connect(self.export_pdf_side_b)
        layout.addWidget(self.btn_export_b)

        self.btn_generate_kp = QPushButton("Сформировать КП в PDF")
        self.btn_generate_kp.setObjectName("btnPrimary")
        self.btn_generate_kp.clicked.connect(self.generate_commercial_offer_pdf)
        layout.addWidget(self.btn_generate_kp)

        self.btn_preview_kp = QPushButton("Просмотр КП")
        self.btn_preview_kp.setObjectName("btnPreview")
        self.btn_preview_kp.clicked.connect(self.preview_commercial_offer_pdf)
        layout.addWidget(self.btn_preview_kp)

        self.tab_widget.addTab(customer_tab, "Данные заказа")

    def create_history_tab(self):
        history_tab = QWidget()
        layout = QVBoxLayout(history_tab)

        self.orders_table = QTableWidget()
        self.orders_table.setColumnCount(7)
        self.orders_table.setHorizontalHeaderLabels(
            ["ID", "Заказчик", "Компания", "Дата", "Тираж", "Статус", "Действия"]
        )
        self.orders_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.orders_table)

        refresh_btn = QPushButton("Обновить список")
        refresh_btn.clicked.connect(self.load_orders)
        layout.addWidget(refresh_btn)

        self.tab_widget.addTab(history_tab, "История заказов")

        QTimer.singleShot(100, self.load_orders)

    def active_editors(self):
        """Return editors affected by the current side selection."""
        if self.current_side == "BOTH":
            return [self.side_a_editor, self.side_b_editor]
        if self.current_side == "A":
            return [self.side_a_editor]
        if self.current_side == "B":
            return [self.side_b_editor]
        return []

    def capture_state(self):
        """Snapshot both editors + CMYK for undo/redo."""

        def editor_state(editor):
            return {
                "image": editor.image.copy() if editor.image else None,
                "original_image": editor.original_image.copy() if editor.original_image else None,
                "base_image": editor.base_image.copy() if editor.base_image else None,
                "scale_factor": editor.scale_factor,
                "offset_x": editor.offset_x,
                "offset_y": editor.offset_y,
            }

        return {
            "side_a": editor_state(self.side_a_editor),
            "side_b": editor_state(self.side_b_editor),
            "cmyk": {
                "c": self.c_slider.value(),
                "m": self.m_slider.value(),
                "y": self.y_slider.value(),
                "k": self.k_slider.value(),
            },
        }

    def load_image(self, side_key):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            f"Выберите изображение для {side_key.upper()}",
            "",
            "Изображения (*.png *.jpg *.jpeg *.bmp *.tiff)",
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
        if state == Qt.Checked:
            self.current_side = "BOTH"
            logging.info("Sync mode enabled: editing both sides simultaneously")
        else:
            self.current_side = "A"
            logging.info("Sync mode disabled: editing side A only")
        self.update_side_visuals()

    def on_editor_click(self, side_key):
        """Handle click on editor canvas for side selection."""
        if self.current_side != "BOTH":
            new_side = "A" if side_key == "side_a" else "B"
            if self.current_side != new_side:
                self.current_side = new_side
                logging.info(f"Switched to side {new_side} via canvas click")
                self.update_side_visuals()

    def update_side_visuals(self):
        """Update visual indication of active side."""
        if self.current_side == "BOTH":
            self.side_a_editor.setStyleSheet("background-color: #252538; border: 2px solid #89b4fa;")
            self.side_b_editor.setStyleSheet("background-color: #252538; border: 2px solid #89b4fa;")
        elif self.current_side == "A":
            self.side_a_editor.setStyleSheet("background-color: #252538; border: 3px solid #89b4fa;")
            self.side_b_editor.setStyleSheet("background-color: #252538; border: 1px solid #45475a;")
        elif self.current_side == "B":
            self.side_a_editor.setStyleSheet("background-color: #252538; border: 1px solid #45475a;")
            self.side_b_editor.setStyleSheet("background-color: #252538; border: 3px solid #89b4fa;")

    def save_to_history(self):
        """Save current state of both sides to undo stack."""
        try:
            self.undo_stack.append(self.capture_state())
            if len(self.undo_stack) > self.max_history_depth:
                self.undo_stack.pop(0)
            self.redo_stack.clear()
            logging.info(f"State saved to undo stack (depth: {len(self.undo_stack)})")
        except Exception as e:
            logging.error(f"Error saving to history: {e}", exc_info=True)

    def undo(self):
        """Restore previous state from undo stack."""
        if not self.undo_stack:
            logging.info("Nothing to undo")
            return

        try:
            self.redo_stack.append(self.capture_state())
            state = self.undo_stack.pop()
            self.restore_state(state)
            logging.info(
                f"Undo performed (undo depth: {len(self.undo_stack)}, redo depth: {len(self.redo_stack)})"
            )
        except Exception as e:
            logging.error(f"Error during undo: {e}", exc_info=True)

    def redo(self):
        """Restore next state from redo stack."""
        if not self.redo_stack:
            logging.info("Nothing to redo")
            return

        try:
            self.undo_stack.append(self.capture_state())
            state = self.redo_stack.pop()
            self.restore_state(state)
            logging.info(
                f"Redo performed (undo depth: {len(self.undo_stack)}, redo depth: {len(self.redo_stack)})"
            )
        except Exception as e:
            logging.error(f"Error during redo: {e}", exc_info=True)

    def restore_state(self, state):
        """Restore editor state from saved state dict."""
        try:
            if state["side_a"]["image"]:
                self.side_a_editor.image = state["side_a"]["image"].copy()
                self.side_a_editor.original_image = state["side_a"]["original_image"].copy()
                self.side_a_editor.base_image = state["side_a"]["base_image"].copy()
                self.side_a_editor.scale_factor = state["side_a"]["scale_factor"]
                self.side_a_editor.offset_x = state["side_a"]["offset_x"]
                self.side_a_editor.offset_y = state["side_a"]["offset_y"]
                self.side_a_editor.update()

            if state["side_b"]["image"]:
                self.side_b_editor.image = state["side_b"]["image"].copy()
                self.side_b_editor.original_image = state["side_b"]["original_image"].copy()
                self.side_b_editor.base_image = state["side_b"]["base_image"].copy()
                self.side_b_editor.scale_factor = state["side_b"]["scale_factor"]
                self.side_b_editor.offset_x = state["side_b"]["offset_x"]
                self.side_b_editor.offset_y = state["side_b"]["offset_y"]
                self.side_b_editor.update()

            self.c_slider.blockSignals(True)
            self.m_slider.blockSignals(True)
            self.y_slider.blockSignals(True)
            self.k_slider.blockSignals(True)

            self.c_slider.setValue(state["cmyk"]["c"])
            self.m_slider.setValue(state["cmyk"]["m"])
            self.y_slider.setValue(state["cmyk"]["y"])
            self.k_slider.setValue(state["cmyk"]["k"])

            self.c_slider.blockSignals(False)
            self.m_slider.blockSignals(False)
            self.y_slider.blockSignals(False)
            self.k_slider.blockSignals(False)

            logging.info("State restored successfully")
        except Exception as e:
            logging.error(f"Error restoring state: {e}", exc_info=True)

    def sync_position(self, target_side, dx, dy):
        """Sync position changes to the other side when in BOTH mode."""
        if self.current_side == "BOTH":
            target_editor = getattr(self, f"{target_side}_editor")
            target_editor.offset_x += dx
            target_editor.offset_y += dy
            target_editor.update()

    def sync_eraser(self, target_side, x, y, size):
        """Sync eraser operations to the other side when in BOTH mode."""
        if self.current_side == "BOTH":
            target_editor = getattr(self, f"{target_side}_editor")
            target_editor.erase_at(x, y, size)

    def change_mode(self, mode):
        mode_map = {
            "Просмотр": "view",
            "Перемещение": "move",
            "Ластик": "eraser",
        }
        self.side_a_editor.current_mode = mode_map[mode]
        self.side_b_editor.current_mode = mode_map[mode]

        self.eraser_control.setVisible(mode == "Ластик")
        self.move_hint.setVisible(mode == "Перемещение")

        if mode == "Ластик":
            self.side_a_editor.setCursor(QCursor(Qt.CrossCursor))
            self.side_b_editor.setCursor(QCursor(Qt.CrossCursor))
        elif mode == "Перемещение":
            self.side_a_editor.setCursor(QCursor(Qt.OpenHandCursor))
            self.side_b_editor.setCursor(QCursor(Qt.OpenHandCursor))
        else:
            self.side_a_editor.setCursor(QCursor(Qt.ArrowCursor))
            self.side_b_editor.setCursor(QCursor(Qt.ArrowCursor))

    def change_eraser_size(self, size):
        self.side_a_editor.eraser_size = size
        self.side_b_editor.eraser_size = size

    def apply_cmyk(self):
        c = self.c_slider.value() * 2.55
        m = self.m_slider.value() * 2.55
        y = self.y_slider.value() * 2.55
        k = self.k_slider.value() * 2.55

        for editor in self.active_editors():
            editor.apply_cmyk_color(c, m, y, k)

    def open_color_settings(self):
        dialog = ColorSettingsDialog(self)
        dialog.exec()

    def apply_zoom(self, factor):
        for editor in self.active_editors():
            editor.zoom_image(factor)

    def reset_position(self):
        self.side_a_editor.reset_position()
        self.side_b_editor.reset_position()

    def reset_current_image(self):
        self.side_a_editor.reset_image()
        self.side_b_editor.reset_image()
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
        return company_config.get_config_path()

    def save_company_settings(self, name, address, phone, logo_path):
        ok = company_config.save_company_settings(name, address, phone, logo_path)
        if ok:
            self.organization_data = company_config.to_org_view(
                {
                    "company_name": name,
                    "company_address": address,
                    "company_phone": phone,
                    "company_logo": logo_path,
                }
            )
        return ok

    def load_company_settings(self):
        return company_config.load_company_settings()

    def load_organization_config(self):
        return company_config.to_org_view(company_config.load_company_settings())

    def save_organization_config(self, data):
        mapped = company_config.from_org_view(data)
        return self.save_company_settings(
            mapped["name"],
            mapped["address"],
            mapped["phone"],
            mapped["logo_path"],
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

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
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
            "Изображения (*.png *.jpg *.jpeg *.bmp *.tiff)",
        )
        if file_path:
            logo_edit.setText(normalize_path(file_path))

    def save_order(self):
        if not self.side_a_editor.get_image() and not self.side_b_editor.get_image():
            QMessageBox.warning(self, "Ошибка", "Загрузите хотя бы одно изображение")
            return

        print_specs = {
            "quantity": self.print_quantity.value(),
            "print_type": self.print_type.currentText(),
            "paper_type": self.paper_type.currentText(),
            "lamination": self.lamination.currentText(),
            "additional": self.additional_specs.toPlainText(),
            "order_number": self.order_number.text().strip(),
            "production_deadline": self.production_deadline.text().strip(),
        }

        orders.insert_order(
            customer_name=self.customer_name.text(),
            customer_phone=self.customer_phone.text(),
            customer_email=self.customer_email.text(),
            company_name=self.company_name.text(),
            print_specs=print_specs,
            side_a_path=self.current_order.get("side_a_path", ""),
            side_b_path=self.current_order.get("side_b_path", ""),
            status="Черновик",
        )

        QMessageBox.information(self, "Успех", "Заказ сохранен!")
        self.load_orders()

    def load_orders(self):
        order_rows = orders.list_orders()

        self.orders_table.setRowCount(len(order_rows))

        for row, order in enumerate(order_rows):
            order_id, customer, company, date, specs_json, status = order

            specs = orders.decode_print_specs(specs_json)
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
        order = orders.get_order(order_id)

        if order:
            self.customer_name.setText(order["customer_name"] or "")
            self.customer_phone.setText(order["customer_phone"] or "")
            self.customer_email.setText(order["customer_email"] or "")
            self.company_name.setText(order["company_name"] or "")

            specs = orders.decode_print_specs(order["print_specs"])
            self.print_quantity.setValue(specs.get("quantity", 100))
            self.print_type.setCurrentText(specs.get("print_type", "Цифровая печать"))
            self.paper_type.setCurrentText(specs.get("paper_type", "Пластик PVC"))
            self.lamination.setCurrentText(specs.get("lamination", "Без лака"))
            self.additional_specs.setText(specs.get("additional", ""))
            self.order_number.setText(specs.get("order_number", ""))
            self.production_deadline.setText(specs.get("production_deadline", ""))

            side_a = order["side_a_path"] or ""
            side_b = order["side_b_path"] or ""

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

        image_a = self.side_a_editor.get_framed_image()
        image_b = self.side_b_editor.get_framed_image()

        if not image_a and not image_b:
            QMessageBox.warning(self, "Ошибка", "Нет изображений для генерации КП")
            return

        order_number = self.order_number.text().strip() or "Б/Н"
        order_fields = {
            "customer_name": self.customer_name.text().strip() or "Не указан",
            "customer_phone": self.customer_phone.text().strip() or "Не указан",
            "customer_email": self.customer_email.text().strip() or "Не указан",
            "order_number": order_number,
            "production_deadline": self.production_deadline.text().strip() or "Не установлен",
            "company_name": self.company_name.text().strip() or "—",
            "print_quantity": str(self.print_quantity.value()),
            "print_type": self.print_type.currentText(),
            "paper_type": self.paper_type.currentText(),
            "lamination": self.lamination.currentText(),
            "additional": self.additional_specs.toPlainText().strip() or "—",
        }

        default_filename = f"kp_order_{order_number}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Сохранить коммерческое предложение",
            default_filename,
            "PDF файлы (*.pdf)",
        )

        if not file_path:
            return

        try:
            export_commercial_offer_pdf(
                file_path,
                company_data=company_data,
                order_fields=order_fields,
                image_a=image_a,
                image_b=image_b,
            )
            QMessageBox.information(self, "Успех", f"КП успешно сохранено:\n{file_path}")
        except Exception as e:
            error_msg = f"Не удалось сгенерировать PDF: {str(e)}\n\nTraceback:\n{traceback.format_exc()}"
            logging.error(error_msg)
            QMessageBox.critical(self, "Ошибка генерации КП", error_msg)

    def preview_commercial_offer_pdf(self):
        company_data = self.load_company_settings()

        image_a = self.side_a_editor.get_framed_image()
        image_b = self.side_b_editor.get_framed_image()

        if not image_a and not image_b:
            QMessageBox.warning(self, "Ошибка", "Нет изображений для генерации КП")
            return

        order_number = self.order_number.text().strip() or "Б/Н"
        order_fields = {
            "customer_name": self.customer_name.text().strip() or "Не указан",
            "customer_phone": self.customer_phone.text().strip() or "Не указан",
            "customer_email": self.customer_email.text().strip() or "Не указан",
            "order_number": order_number,
            "production_deadline": self.production_deadline.text().strip() or "Не установлен",
            "company_name": self.company_name.text().strip() or "—",
            "print_quantity": str(self.print_quantity.value()),
            "print_type": self.print_type.currentText(),
            "paper_type": self.paper_type.currentText(),
            "lamination": self.lamination.currentText(),
            "additional": self.additional_specs.toPlainText().strip() or "—",
        }

        try:
            fd, temp_path = tempfile.mkstemp(suffix=".pdf")
            os.close(fd)
            export_commercial_offer_pdf(
                temp_path,
                company_data=company_data,
                order_fields=order_fields,
                image_a=image_a,
                image_b=image_b,
            )
            os.startfile(temp_path)
        except Exception as e:
            error_msg = f"Не удалось создать превью КП: {str(e)}\n\nTraceback:\n{traceback.format_exc()}"
            logging.error(error_msg)
            QMessageBox.critical(self, "Ошибка превью КП", error_msg)

    def export_pdf(self):
        image_a = self.side_a_editor.get_framed_image()
        image_b = self.side_b_editor.get_framed_image()

        if not image_a and not image_b:
            QMessageBox.warning(self, "Ошибка", "Нет изображений для экспорта")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Сохранить PDF",
            f"card_print_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
            "PDF файлы (*.pdf)",
        )

        if file_path:
            try:
                export_print_pdf(file_path, image_a, image_b)
                QMessageBox.information(self, "Успех", f"PDF сохранен: {file_path}")
            except Exception as e:
                error_msg = f"Не удалось создать PDF: {str(e)}\n\nTraceback:\n{traceback.format_exc()}"
                logging.error(error_msg)
                QMessageBox.critical(self, "Ошибка экспорта PDF", error_msg)

    def export_pdf_side_a(self):
        image = self.side_a_editor.get_framed_image()
        if image is None:
            QMessageBox.warning(self, "Ошибка", "Нет изображения для Стороны А")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Сохранить Сторону А",
            f"card_side_a_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
            "PDF файлы (*.pdf)",
        )

        if file_path:
            try:
                export_print_pdf_single(file_path, image)
                QMessageBox.information(self, "Успех", f"Сторона А сохранена:\n{file_path}")
            except Exception as e:
                error_msg = f"Не удалось создать PDF: {str(e)}\n\nTraceback:\n{traceback.format_exc()}"
                logging.error(error_msg)
                QMessageBox.critical(self, "Ошибка экспорта PDF", error_msg)

    def export_pdf_side_b(self):
        image = self.side_b_editor.get_framed_image()
        if image is None:
            QMessageBox.warning(self, "Ошибка", "Нет изображения для Стороны Б")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Сохранить Сторону Б",
            f"card_side_b_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
            "PDF файлы (*.pdf)",
        )

        if file_path:
            try:
                export_print_pdf_single(file_path, image)
                QMessageBox.information(self, "Успех", f"Сторона Б сохранена:\n{file_path}")
            except Exception as e:
                error_msg = f"Не удалось создать PDF: {str(e)}\n\nTraceback:\n{traceback.format_exc()}"
                logging.error(error_msg)
                QMessageBox.critical(self, "Ошибка экспорта PDF", error_msg)
