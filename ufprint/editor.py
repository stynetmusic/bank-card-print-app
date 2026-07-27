"""Image editor widget for bank-card sides."""

import logging
import os
import traceback

import numpy as np
from PIL import Image, ImageDraw, ImageQt
from PyQt5.QtCore import QPoint, Qt
from PyQt5.QtGui import QBrush, QColor, QCursor, QImage, QPainter, QPen, QPixmap
from PyQt5.QtWidgets import QWidget

from ufprint.framing import render_framed_rgba
from ufprint.paths import normalize_path


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
            qimg = QImage(data, pil_img.size[0], pil_img.size[1], QImage.Format_RGBA8888)
            return QPixmap.fromImage(qimg)
    except Exception as e:
        logging.error(f"Error converting PIL to QPixmap: {e}", exc_info=True)
        return None


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
                candidate_paths.extend([path.replace("/", "\\"), path.replace("\\", "/")])

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

            img = Image.open(path)
            logging.info(f"Image loaded successfully: {img.size}, mode: {img.mode}")

            if img.mode != "RGB":
                logging.info(f"Converting image from {img.mode} to RGB")
                img = img.convert("RGB")

            self.original_image = img.convert("RGBA")
            self.base_image = self.original_image.copy()
            self.image = self.original_image.copy()

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

            display_width = int(img_width * self.scale_factor)
            display_height = int(img_height * self.scale_factor)

            x = (widget_width - display_width) // 2 + self.offset_x
            y = (widget_height - display_height) // 2 + self.offset_y

            try:
                pixmap = pillow_to_qpixmap(self.image)
                if pixmap:
                    painter.drawPixmap(
                        x, y, pixmap.scaled(display_width, display_height, Qt.KeepAspectRatio)
                    )
                else:
                    raise Exception("Failed to convert image to QPixmap")
            except Exception as e:
                logging.error(f"Error drawing image: {e}", exc_info=True)
                painter.setPen(QPen(QColor(255, 0, 0), 2))
                painter.drawText(self.rect(), Qt.AlignCenter, "Ошибка отображения")

            if self.current_mode == "eraser":
                painter.setPen(QPen(QColor(255, 0, 0), 2))
                painter.setBrush(QBrush(QColor(255, 0, 0, 50)))
                cursor_size = self.eraser_size * 2
                painter.drawEllipse(
                    self.last_mouse_pos.x() - cursor_size // 2,
                    self.last_mouse_pos.y() - cursor_size // 2,
                    cursor_size,
                    cursor_size,
                )
        else:
            painter.setPen(QPen(QColor(166, 173, 200), 2))
            painter.drawText(self.rect(), Qt.AlignCenter, "Загрузите изображение\n(87x56mm)")

    def mousePressEvent(self, event):
        if not self.image:
            return

        if self.click_callback:
            self.click_callback()

        if self.current_mode == "eraser":
            self.apply_eraser(event.pos())
        elif self.current_mode == "move":
            self.dragging = True
            self.last_mouse_pos = event.pos()
            self.setCursor(QCursor(Qt.ClosedHandCursor))

    def mouseMoveEvent(self, event):
        self.last_mouse_pos = event.pos()

        if not self.image:
            return

        if self.current_mode == "eraser" and event.buttons() & Qt.LeftButton:
            self.apply_eraser(event.pos())
        elif self.current_mode == "move" and self.dragging:
            delta = event.pos() - self.last_mouse_pos
            self.offset_x += delta.x()
            self.offset_y += delta.y()
            self.last_mouse_pos = event.pos()
            self.update()
            if self.position_callback:
                self.position_callback(delta.x(), delta.y())

        if self.current_mode == "eraser":
            self.update()

    def mouseReleaseEvent(self, event):
        if self.current_mode == "move":
            self.dragging = False
            self.setCursor(QCursor(Qt.ArrowCursor))
            if self.history_callback:
                self.history_callback()

    def keyPressEvent(self, event):
        if not self.image:
            return

        key = event.key()
        step = 10

        if key == Qt.Key_Left:
            self.offset_x -= step
            if self.position_callback:
                self.position_callback(-step, 0)
        elif key == Qt.Key_Right:
            self.offset_x += step
            if self.position_callback:
                self.position_callback(step, 0)
        elif key == Qt.Key_Up:
            self.offset_y -= step
            if self.position_callback:
                self.position_callback(0, -step)
        elif key == Qt.Key_Down:
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

            base_x = (widget_width - display_width) // 2 + self.offset_x
            base_y = (widget_height - display_height) // 2 + self.offset_y

            x = int((pos.x() - base_x) / self.scale_factor)
            y = int((pos.y() - base_y) / self.scale_factor)

            if self.eraser_callback:
                self.eraser_callback(x, y, self.eraser_size)

            self.erase_at(x, y, self.eraser_size)
        except Exception as e:
            logging.error(f"Error applying eraser: {e}")

    def erase_at(self, x, y, size):
        """Erase a circular region in image coordinates (no sync callback)."""
        if not self.image:
            return
        img_width, img_height = self.image.size
        if 0 <= x < img_width and 0 <= y < img_height:
            draw = ImageDraw.Draw(self.image)
            eraser_radius = size
            bbox = [x - eraser_radius, y - eraser_radius, x + eraser_radius, y + eraser_radius]
            draw.ellipse(bbox, fill=(0, 0, 0, 0))
            self.update()

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
                self.image = self.base_image.copy()

                img_array = np.array(self.image, dtype=np.float32)

                img_array[..., 0] = np.maximum(0, img_array[..., 0] - c)
                img_array[..., 1] = np.maximum(0, img_array[..., 1] - m)
                img_array[..., 2] = np.maximum(0, img_array[..., 2] - y)

                brightness = 1.0 - (k / 255.0)
                img_array[..., 0] = img_array[..., 0] * brightness
                img_array[..., 1] = img_array[..., 1] * brightness
                img_array[..., 2] = img_array[..., 2] * brightness

                img_array = np.clip(img_array, 0, 255).astype(np.uint8)

                self.image = Image.fromarray(img_array)
                self.update()
            except Exception as e:
                logging.error(f"Error applying CMYK: {e}", exc_info=True)

    def get_image(self):
        """Return raw PIL image (internal / undo use)."""
        return self.image

    def get_framed_image(self, out_width=None, out_height=None):
        """Return WYSIWYG framed RGBA canvas matching paintEvent.

        Always renders at current widget size (or provided stand-in when width is 0).
        ``out_width`` / ``out_height`` are only used as canvas size when the widget
        reports zero size (e.g. before show); they are not a separate export size.
        """
        if not self.image:
            return None

        canvas_w = self.width() or out_width or 348
        canvas_h = self.height() or out_height or 224
        return render_framed_rgba(
            self.image,
            canvas_w,
            canvas_h,
            self.scale_factor,
            self.offset_x,
            self.offset_y,
        )

    def reset_image(self):
        if self.base_image:
            self.image = self.base_image.copy()
            self.original_image = self.base_image.copy()
            self.offset_x = 0
            self.offset_y = 0
            self.scale_factor = 1.0
            self.update()
