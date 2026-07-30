"""PDF export helpers for print cards and commercial offers."""

import io
import logging
import os
import sys
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Image,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from ufprint.paths import get_app_dir


def fit_image_to_box(img_w, img_h, max_w, max_h):
    """Scale dimensions to fit inside max_w x max_h preserving aspect ratio."""
    if img_w <= 0 or img_h <= 0:
        return 0.0, 0.0
    aspect_ratio = img_w / img_h
    if aspect_ratio > (max_w / max_h):
        final_width = max_w
        final_height = max_w / aspect_ratio
    else:
        final_height = max_h
        final_width = max_h * aspect_ratio
    return final_width, final_height

PAGE_W = 87 * mm
PAGE_H = 56 * mm


def _find_arial_font():
    candidates = []
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        candidates.extend(
            [
                os.path.join(meipass, "Arial.ttf"),
                os.path.join(meipass, "_internal", "Arial.ttf"),
                os.path.join(meipass, "fonts", "Arial.ttf"),
            ]
        )
    app_dir = get_app_dir()
    candidates.extend(
        [
            os.path.join(app_dir, "Arial.ttf"),
            os.path.join(app_dir, "_internal", "Arial.ttf"),
            os.path.join(app_dir, "fonts", "Arial.ttf"),
            os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts", "arial.ttf"),
        ]
    )
    for candidate in candidates:
        if candidate and os.path.exists(candidate):
            return candidate
    return None


def _pil_to_rl_image(pil_img, width, height):
    buf = io.BytesIO()
    img = pil_img if pil_img.mode in ("RGB", "RGBA") else pil_img.convert("RGBA")
    img.save(buf, format="PNG")
    buf.seek(0)
    return Image(buf, width=width, height=height)


def export_print_pdf(file_path, image_a, image_b):
    """Export bank-card PDF (87x56mm pages). Images are already-framed PIL Images or None.

    Each side is rendered at full card size with no quality-lossy scaling.
    The PNG data is embedded losslessly into the PDF.
    """
    doc = SimpleDocTemplate(
        file_path,
        pagesize=(PAGE_W, PAGE_H),
        rightMargin=0,
        leftMargin=0,
        topMargin=0,
        bottomMargin=0,
    )

    story = []
    if image_a is not None:
        story.append(_pil_to_rl_image(image_a, PAGE_W, PAGE_H))

    if image_b is not None:
        if story:
            story.append(PageBreak())
        story.append(_pil_to_rl_image(image_b, PAGE_W, PAGE_H))

    if not story:
        raise ValueError("No images to export")

    doc.build(story)
    return file_path


def export_print_pdf_single(file_path, image):
    """Export a single card side as a PDF (87x56mm) with full quality.

    The image is embedded as lossless PNG and rendered at the full card size
    without any intermediate resizing that would degrade detail.
    """
    doc = SimpleDocTemplate(
        file_path,
        pagesize=(PAGE_W, PAGE_H),
        rightMargin=0,
        leftMargin=0,
        topMargin=0,
        bottomMargin=0,
    )

    if image is None:
        raise ValueError("No image to export")

    story = [_pil_to_rl_image(image, PAGE_W, PAGE_H)]
    doc.build(story)
    return file_path


def export_commercial_offer_pdf(file_path, *, company_data, order_fields, image_a, image_b):
    """Generate commercial offer (КП) PDF."""
    company_data = company_data or {}
    order_fields = order_fields or {}

    comp_name = company_data.get("company_name", "Имя компании не указано")
    comp_address = company_data.get("company_address", "Адрес не указан")
    comp_phone = company_data.get("company_phone", "Телефон не указан")
    comp_logo = company_data.get("company_logo", "")

    customer_name = order_fields.get("customer_name", "Не указан")
    customer_phone = order_fields.get("customer_phone", "Не указан")
    customer_email = order_fields.get("customer_email", "Не указан")
    order_number = order_fields.get("order_number", "Б/Н")
    production_deadline = order_fields.get("production_deadline", "Не установлен")
    company_name = order_fields.get("company_name", "—")
    print_quantity = order_fields.get("print_quantity", "")
    print_type = order_fields.get("print_type", "")
    paper_type = order_fields.get("paper_type", "")
    lamination = order_fields.get("lamination", "")
    additional = order_fields.get("additional", "—")

    doc = SimpleDocTemplate(
        file_path, pagesize=A4, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30
    )
    styles = getSampleStyleSheet()
    story = []

    font_path = _find_arial_font()
    if font_path:
        pdfmetrics.registerFont(TTFont("CustomArial", font_path))
    else:
        logging.warning("Arial.ttf not found for КП PDF generation; falling back to default font")

    font_name = "CustomArial" if font_path else "Helvetica"
    title_style = ParagraphStyle(
        "KPTitle",
        parent=styles["Heading1"],
        fontName=font_name,
        fontSize=18,
        leading=22,
        textColor=colors.HexColor("#0066cc"),
    )
    normal_style = ParagraphStyle(
        "KPNormal",
        parent=styles["Normal"],
        fontName=font_name,
        fontSize=10,
        leading=14,
    )

    company_info_text = f"<b>{comp_name}</b><br/>Адрес: {comp_address}<br/>Тел: {comp_phone}"
    header_data = []
    if comp_logo and os.path.exists(comp_logo):
        try:
            logo_img = Image(comp_logo, width=100, height=50)
            header_data.append([logo_img, Paragraph(company_info_text, normal_style)])
        except Exception:
            header_data.append(["", Paragraph(company_info_text, normal_style)])
    else:
        header_data.append(["", Paragraph(company_info_text, normal_style)])

    header_table = Table(header_data, colWidths=[120, 420])
    header_table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
            ]
        )
    )
    story.append(header_table)
    story.append(Spacer(1, 15))

    story.append(Paragraph(f"Коммерческое предложение по заказу № {order_number}", title_style))
    story.append(Paragraph(f"Дата создания: {datetime.now().strftime('%d.%m.%Y')}", normal_style))
    story.append(Spacer(1, 15))

    info_data = [
        [
            Paragraph("<b>Информация о заказчике:</b>", normal_style),
            Paragraph("<b>Параметры заказа:</b>", normal_style),
        ],
        [
            Paragraph(
                f"Заказчик: {customer_name}<br/>Телефон: {customer_phone}<br/>Email: {customer_email}",
                normal_style,
            ),
            Paragraph(
                f"Срок изготовления: {production_deadline}<br/>Компания: {company_name}<br/>"
                f"Тираж: {print_quantity}<br/>Тип печати: {print_type}<br/>"
                f"Материал: {paper_type}<br/>Ламинация: {lamination}",
                normal_style,
            ),
        ],
    ]
    info_table = Table(info_data, colWidths=[270, 270])
    info_table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                ("PADDING", (0, 0), (-1, -1), 6),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ]
        )
    )
    story.append(info_table)
    story.append(Spacer(1, 20))

    story.append(Paragraph("<b>Макет карты (Сторона А и Сторона Б):</b>", normal_style))
    story.append(Spacer(1, 10))

    row_images = []
    for label, image_obj in (("Сторона А", image_a), ("Сторона Б", image_b)):
        if image_obj is not None:
            try:
                row_images.append(_pil_to_rl_image(image_obj, 240, 150))
            except Exception:
                row_images.append(Paragraph(f"[Ошибка загрузки {label}]", normal_style))
        else:
            row_images.append(Paragraph(f"[{label} отсутствует]", normal_style))

    images_table = Table([row_images], colWidths=[270, 270])
    images_table.setStyle(
        TableStyle(
            [
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )
    story.append(images_table)
    story.append(Spacer(1, 10))
    story.append(Paragraph("<b>Дополнительные характеристики:</b>", normal_style))
    story.append(Paragraph(additional, normal_style))

    doc.build(story)
    return file_path