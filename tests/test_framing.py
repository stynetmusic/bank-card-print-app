"""Tests for framing math (no GUI)."""

from PIL import Image

from ufprint.framing import render_framed_rgba, scale_offsets_to_canvas


def test_render_framed_centered_no_offset():
    img = Image.new("RGBA", (100, 50), (255, 0, 0, 255))
    canvas = render_framed_rgba(img, 200, 100, 1.0, 0, 0)
    assert canvas.size == (200, 100)
    # Center pixel of pasted image should be opaque red
    assert canvas.getpixel((100, 50))[0] == 255
    # Corner outside image should be opaque white (print background)
    assert canvas.getpixel((0, 0))[:3] == (255, 255, 255)


def test_render_framed_transparent_background():
    img = Image.new("RGBA", (10, 10), (0, 0, 255, 255))
    canvas = render_framed_rgba(
        img, 40, 40, 1.0, 0, 0, background=(0, 0, 0, 0)
    )
    assert canvas.getpixel((0, 0))[3] == 0


def test_render_framed_with_scale_and_offset():
    img = Image.new("RGBA", (40, 40), (0, 255, 0, 255))
    canvas = render_framed_rgba(img, 100, 100, 2.0, 10, -5)
    assert canvas.size == (100, 100)
    display_w = 80
    display_h = 80
    x = (100 - display_w) // 2 + 10
    y = (100 - display_h) // 2 - 5
    # Top-left of pasted region
    px = canvas.getpixel((x + 1, y + 1))
    assert px[1] == 255
    assert px[3] == 255


def test_render_framed_none_returns_none():
    assert render_framed_rgba(None, 10, 10, 1.0, 0, 0) is None


def test_scale_offsets_uniform():
    ox, oy, sf = scale_offsets_to_canvas(10, 20, 1.0, 100, 100, 200, 200)
    assert ox == 20.0
    assert oy == 40.0
    assert sf == 2.0


def test_scale_offsets_min_scale():
    ox, oy, sf = scale_offsets_to_canvas(10, 0, 1.0, 100, 100, 200, 50)
    assert sf == 0.5
    assert ox == 5.0
