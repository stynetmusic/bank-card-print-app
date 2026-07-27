"""Pure PIL framing — matches ImageEditor.paintEvent placement math."""

from PIL import Image


def render_framed_rgba(
    image,
    canvas_w,
    canvas_h,
    scale_factor,
    offset_x,
    offset_y,
    background=(255, 255, 255, 255),
):
    """Composite RGBA image onto a canvas for WYSIWYG export.

    Placement matches ImageEditor.paintEvent:
        display_w = int(img_w * scale_factor)
        display_h = int(img_h * scale_factor)
        x = (canvas_w - display_w) // 2 + offset_x
        y = (canvas_h - display_h) // 2 + offset_y

    Default background is opaque white (print/КП). Pass (0,0,0,0) for transparent.
    """
    if image is None:
        return None

    img = image if image.mode == "RGBA" else image.convert("RGBA")
    img_w, img_h = img.size
    display_w = int(img_w * scale_factor)
    display_h = int(img_h * scale_factor)

    x = (canvas_w - display_w) // 2 + int(offset_x)
    y = (canvas_h - display_h) // 2 + int(offset_y)

    canvas = Image.new("RGBA", (int(canvas_w), int(canvas_h)), background)
    if display_w <= 0 or display_h <= 0:
        return canvas

    try:
        resample = Image.Resampling.LANCZOS
    except AttributeError:
        resample = Image.LANCZOS

    resized = img.resize((display_w, display_h), resample)
    canvas.paste(resized, (x, y), resized)
    return canvas

def scale_offsets_to_canvas(offset_x, offset_y, scale_factor, src_w, src_h, dst_w, dst_h):
    """Map widget-space offsets/scale to a destination canvas using uniform min scale.

    Prefer rendering at widget size for WYSIWYG; this helper is for callers that
    must map parameters when sizes differ.
    """
    src_w = max(int(src_w), 1)
    src_h = max(int(src_h), 1)
    sx = float(dst_w) / src_w
    sy = float(dst_h) / src_h
    uniform = min(sx, sy)
    return (
        offset_x * uniform,
        offset_y * uniform,
        scale_factor * uniform,
    )
