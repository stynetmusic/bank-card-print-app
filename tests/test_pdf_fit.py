"""Tests for PDF fit helper (no GUI / no reportlab needed for this unit)."""

from ufprint.pdf_export import fit_image_to_box


def test_fit_width_limited():
    # Wide image: width is limiting
    w, h = fit_image_to_box(400, 100, 200, 140)
    assert w == 200
    assert abs(h - 50.0) < 1e-9


def test_fit_height_limited():
    # Tall image: height is limiting
    w, h = fit_image_to_box(100, 400, 230, 140)
    assert h == 140
    assert abs(w - 35.0) < 1e-9


def test_fit_exact_aspect():
    w, h = fit_image_to_box(230, 140, 230, 140)
    assert w == 230
    assert h == 140


def test_fit_zero_size():
    assert fit_image_to_box(0, 10, 100, 100) == (0.0, 0.0)
    assert fit_image_to_box(10, 0, 100, 100) == (0.0, 0.0)
