"""PDF exports for Jewelry invoices and reports."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable, List, Tuple

import arabic_reshaper
from bidi.algorithm import get_display
from reportlab.lib.pagesizes import A4
from reportlab.graphics.barcode import code128
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas


@dataclass
class GalleryInfo:
    name_en: str
    name_ar: str
    address: str
    phone: str
    logo_path: str | None = None
    font_path: str | None = None


def _shape_arabic(text: str) -> str:
    if not text:
        return text
    # Note: Arabic shaping requires a compatible font. If no Arabic font is
    # registered, ReportLab may show missing glyphs.
    reshaped = arabic_reshaper.reshape(text)
    return get_display(reshaped)


def _register_arabic_font(font_path: str | None) -> str:
    if font_path and Path(font_path).exists():
        try:
            pdfmetrics.registerFont(TTFont("ArabicFont", font_path))
            return "ArabicFont"
        except Exception:
            return "Helvetica"
    return "Helvetica"


def export_invoice_pdf(
    path: str,
    gallery: GalleryInfo,
    invoice_no: str,
    invoice_datetime: str,
    cashier_name: str,
    txn_type: str,
    items: Iterable[Tuple[str, str, float, float, float]],
    subtotal: float,
    discount: float,
    discount_type: str,
    discount_value: float,
    total: float,
    payment_method: str,
    notes: str,
    return_reason: str,
) -> None:
    font_name = _register_arabic_font(gallery.font_path)
    c = canvas.Canvas(path, pagesize=A4)
    width, height = A4

    y = height - 40
    if gallery.logo_path and Path(gallery.logo_path).exists():
        try:
            c.drawImage(gallery.logo_path, width - 140, height - 90, width=80, height=50, preserveAspectRatio=True)
        except Exception:
            c.rect(width - 140, height - 90, 80, 50)
            c.drawString(width - 135, height - 70, "Logo")
    else:
        c.rect(width - 140, height - 90, 80, 50)
        c.drawString(width - 135, height - 70, "Logo")
    c.setFont(font_name, 14)
    c.drawString(40, y, gallery.name_en)
    c.drawString(40, y - 18, _shape_arabic(gallery.name_ar))
    c.setFont(font_name, 10)
    c.drawString(40, y - 36, f"Address: {gallery.address}")
    c.drawString(40, y - 52, _shape_arabic(f"العنوان: {gallery.address}"))
    c.drawString(40, y - 68, f"Phone: {gallery.phone}")
    c.drawString(40, y - 84, _shape_arabic(f"هاتف: {gallery.phone}"))

    y -= 110
    c.setFont(font_name, 11)
    c.drawString(40, y, f"Invoice No: {invoice_no}")
    c.drawString(300, y, _shape_arabic(f"رقم الفاتورة: {invoice_no}"))
    y -= 18
    c.drawString(40, y, f"Date & Time: {invoice_datetime}")
    y -= 18
    c.drawString(40, y, f"Cashier: {cashier_name}")
    y -= 18
    txn_label = "Sale" if txn_type == "sale" else "Return"
    c.drawString(40, y, f"Transaction: {txn_label}")
    c.drawString(300, y, _shape_arabic(f"العملية: {'بيع' if txn_type == 'sale' else 'مرتجع'}"))
    y -= 10
    c.line(40, y, width - 40, y)

    y -= 20
    c.setFont(font_name, 10)
    c.drawString(40, y, "Product")
    c.drawString(240, y, "Code")
    c.drawString(320, y, "Qty")
    c.drawString(360, y, "Unit")
    c.drawString(430, y, "Total")
    y -= 12
    c.line(40, y, width - 40, y)
    y -= 18

    for name, code, qty, unit_price, line_total in items:
        c.drawString(40, y, name)
        c.drawString(240, y, code)
        c.drawRightString(350, y, f"{qty:.2f}")
        c.drawRightString(420, y, f"{unit_price:.2f}")
        c.drawRightString(width - 40, y, f"{line_total:.2f}")
        y -= 16
        if y < 120:
            c.showPage()
            y = height - 40
            c.setFont(font_name, 10)

    y -= 10
    c.line(40, y, width - 40, y)
    y -= 20
    c.drawString(40, y, f"Subtotal: {subtotal:.2f}")
    y -= 16
    if discount_type == "percent":
        c.drawString(40, y, f"Discount: {discount_value:.2f}% ({discount:.2f})")
    else:
        c.drawString(40, y, f"Discount: {discount:.2f}")
    y -= 16
    c.drawString(40, y, f"Net Total: {total:.2f}")
    y -= 16
    c.drawString(40, y, f"Payment Method: {payment_method}")
    y -= 16
    if txn_type == "return":
        c.drawString(40, y, f"Return Reason: {return_reason}")
        y -= 16
    if notes:
        c.drawString(40, y, f"Notes: {notes}")
        y -= 16

    y -= 10
    c.setFont(font_name, 9)
    c.drawString(40, y, "Return same day.")
    y -= 14
    c.drawString(40, y, "Exchange within 14 days with invoice and in good condition.")
    y -= 14
    c.drawString(40, y, _shape_arabic("الاسترجاع في نفس اليوم."))
    y -= 14
    c.drawString(40, y, _shape_arabic("الاستبدال خلال 14 يوم مع الفاتورة وبحالة جيدة."))

    c.showPage()
    c.save()


def export_daily_report_pdf(
    path: str,
    gallery: GalleryInfo,
    report_date: str,
    report_number: str,
    cashier: str,
    shift_open: str,
    shift_close: str,
    opening_cash: float,
    closing_cash_actual: float,
    expected_cash: float,
    notes: str,
    sales_summary: Tuple[int, float, float, float],
    payment_breakdown: Iterable[Tuple[str, float]],
    returns_summary: Tuple[int, float],
    return_reasons: Iterable[Tuple[str, int, float]],
    top_products: Iterable[Tuple[str, str, float]],
    low_products: Iterable[Tuple[str, str, float]],
    out_of_stock: Iterable[Tuple[str, str, str, float, float]],
    near_out: Iterable[Tuple[str, str, str, float, float]],
) -> None:
    font_name = _register_arabic_font(gallery.font_path)
    c = canvas.Canvas(path, pagesize=A4)
    width, height = A4
    y = height - 40
    if gallery.logo_path and Path(gallery.logo_path).exists():
        try:
            c.drawImage(gallery.logo_path, width - 140, height - 90, width=80, height=50, preserveAspectRatio=True)
        except Exception:
            c.rect(width - 140, height - 90, 80, 50)
            c.drawString(width - 135, height - 70, "Logo")
    else:
        c.rect(width - 140, height - 90, 80, 50)
        c.drawString(width - 135, height - 70, "Logo")
    c.setFont(font_name, 14)
    c.drawString(40, y, "Daily Report")
    c.drawString(240, y, _shape_arabic("تقرير يومي"))
    y -= 20
    c.setFont(font_name, 10)
    c.drawString(40, y, f"Date: {report_date}")
    y -= 16
    c.drawString(40, y, f"Report No: {report_number}")
    y -= 16
    c.drawString(40, y, f"Cashier: {cashier}")
    y -= 16
    c.drawString(40, y, f"Shift Open: {shift_open}")
    y -= 16
    c.drawString(40, y, f"Shift Close: {shift_close}")
    y -= 20
    c.line(40, y, width - 40, y)

    y -= 20
    c.drawString(40, y, "Sales Movement")
    y -= 16
    invoices, subtotal, discounts, net_sales = sales_summary
    c.drawString(40, y, f"Invoices: {invoices}")
    y -= 16
    c.drawString(40, y, f"Subtotal: {subtotal:.2f}")
    y -= 16
    c.drawString(40, y, f"Discounts: {discounts:.2f}")
    y -= 16
    c.drawString(40, y, f"Net Sales: {net_sales:.2f}")
    y -= 20

    c.drawString(40, y, "Payment Breakdown")
    y -= 16
    for method, value in payment_breakdown:
        c.drawString(40, y, f"{method}: {value:.2f}")
        y -= 14

    y -= 10
    c.drawString(40, y, "Returns")
    y -= 16
    c.drawString(40, y, f"Return invoices: {returns_summary[0]}")
    y -= 16
    c.drawString(40, y, f"Return value: {returns_summary[1]:.2f}")
    y -= 16
    for reason, count, total in return_reasons:
        c.drawString(40, y, f"{reason} ({count}) - {total:.2f}")
        y -= 14

    y -= 10
    c.drawString(40, y, "Top 5 Sold Products")
    y -= 16
    for name, code, qty in top_products:
        c.drawString(40, y, f"{name} ({code}) - {qty:.2f}")
        y -= 14

    y -= 10
    c.drawString(40, y, "Lowest Sold Products")
    y -= 16
    for name, code, qty in low_products:
        c.drawString(40, y, f"{name} ({code}) - {qty:.2f}")
        y -= 14

    y -= 10
    c.drawString(40, y, "Stock Alerts")
    y -= 16
    c.drawString(40, y, "Out of stock:")
    y -= 14
    for name_ar, name_en, sku, qty, min_qty in out_of_stock:
        c.drawString(40, y, f"{name_en} / {name_ar} ({sku}) - {qty:.2f}")
        y -= 14
    y -= 10
    c.drawString(40, y, "Near out of stock:")
    y -= 14
    for name_ar, name_en, sku, qty, min_qty in near_out:
        c.drawString(40, y, f"{name_en} / {name_ar} ({sku}) - {qty:.2f}")
        y -= 14

    y -= 10
    c.drawString(40, y, "Cashbox")
    y -= 16
    c.drawString(40, y, f"Opening cash: {opening_cash:.2f}")
    y -= 16
    c.drawString(40, y, f"Expected cash: {expected_cash:.2f}")
    y -= 16
    c.drawString(40, y, f"Actual cash: {closing_cash_actual:.2f}")
    y -= 16
    diff = closing_cash_actual - expected_cash
    c.drawString(40, y, f"Over/Short: {diff:.2f}")
    y -= 20
    if notes:
        c.drawString(40, y, f"Notes: {notes}")

    c.showPage()
    c.save()


def export_barcode_labels_pdf(
    path: str,
    product_name: str,
    sku: str,
    barcode_value: str,
    barcode_type: str,
) -> None:
    c = canvas.Canvas(path, pagesize=A4)
    width, height = A4
    columns = 3
    rows = 8
    margin_x = 30
    margin_y = 30
    gap_x = 10
    gap_y = 8
    label_width = (width - (2 * margin_x) - (gap_x * (columns - 1))) / columns
    label_height = (height - (2 * margin_y) - (gap_y * (rows - 1))) / rows

    label_text = f"{product_name}\n{sku}"
    for row in range(rows):
        for col in range(columns):
            x = margin_x + col * (label_width + gap_x)
            y = height - margin_y - (row + 1) * label_height - row * gap_y
            c.roundRect(x, y, label_width, label_height, 6, stroke=1, fill=0)
            c.setFont("Helvetica", 7)
            text_y = y + label_height - 12
            for line in label_text.splitlines():
                c.drawString(x + 6, text_y, line[:40])
                text_y -= 10
            if barcode_value:
                barcode_obj = code128.Code128(barcode_value, barHeight=22, barWidth=0.6)
                barcode_obj.drawOn(c, x + 6, y + 8)
                c.setFont("Helvetica", 6)
                c.drawString(x + 6, y + 4, f"{barcode_type or 'Barcode'}: {barcode_value}")
    c.showPage()
    c.save()
