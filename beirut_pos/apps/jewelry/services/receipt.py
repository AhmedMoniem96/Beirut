"""Text receipt generator for Jewelry invoices."""

from __future__ import annotations

from typing import Iterable

from beirut_pos.services.printer import RECEIPT_WIDTH_CHARS, _draw_line, _format_currency_simple

from .db import JewelryInvoice, JewelryInvoiceItem
from .settings import GallerySettings, load_gallery_settings

COL_WIDTHS = (29, 5, 7, 7)  # 48-char (80mm) model: 29+5+7+7
_BRAND_BOX_WIDTH = min(30, RECEIPT_WIDTH_CHARS - 2)


def _truncate(text: str, width: int) -> str:
    if len(text) <= width:
        return text
    return text[: max(1, width - 1)] + "…"


def _format_row(columns: Iterable[str]) -> str:
    name, qty, price, total = columns
    return (
        f"{_truncate(name, COL_WIDTHS[0]):<{COL_WIDTHS[0]}}"
        f"{_truncate(qty, COL_WIDTHS[1]):>{COL_WIDTHS[1]}}"
        f"{_truncate(price, COL_WIDTHS[2]):>{COL_WIDTHS[2]}}"
        f"{_truncate(total, COL_WIDTHS[3]):>{COL_WIDTHS[3]}}"
    )


def _build_brand_box(lines: list[str], box_width: int = _BRAND_BOX_WIDTH) -> list[str]:
    out = ["╔" + "═" * box_width + "╗"]
    for text in lines:
        trimmed = text[:box_width]
        out.append(f"║{trimmed.center(box_width)}║")
    out.append("╚" + "═" * box_width + "╝")
    return out


def build_receipt_text(
    invoice: JewelryInvoice,
    items: list[JewelryInvoiceItem],
    *,
    loyalty_balance: float | None = None,
    loyalty_threshold: int | None = None,
    gallery: GallerySettings | None = None,
) -> str:
    """Return the receipt text for a jewelry invoice."""
    gallery = gallery or load_gallery_settings()
    brand_lines = [gallery.name_en, gallery.name_ar, gallery.address, gallery.phone]
    brand_lines = [line.strip() for line in brand_lines if line and line.strip()]

    lines: list[str] = []
    for line in _build_brand_box(brand_lines):
        lines.append(">>C " + line)

    lines.append(f">>R Date: {invoice.datetime}")
    lines.append(f">>R Invoice: {invoice.invoice_no}")
    lines.append(f">>R Cashier: {invoice.cashier_name}")
    if invoice.payment_method:
        lines.append(f">>R Payment: {invoice.payment_method}")
    if invoice.txn_type == "return":
        lines.append(">>R Type: Return")
    customer_label = "Walk-in"
    if invoice.customer_name or invoice.customer_phone:
        customer_label = " ".join(
            part for part in [invoice.customer_name, invoice.customer_phone] if part
        )
    lines.append(f">>R Customer: {customer_label}")
    if invoice.customer_phone:
        lines.append(f">>R Phone: {invoice.customer_phone}")
    if invoice.delivery_enabled and invoice.delivery_address:
        lines.append(f">>R Delivery Address: {invoice.delivery_address}")

    lines.append(_draw_line("═"))
    lines.append(_format_row(("Item", "Qty", "Price", "Total")))
    lines.append(_draw_line("─"))
    for item in items:
        label = item.product_name
        if item.product_code:
            label = f"{label} ({item.product_code})"
        lines.append(
            _format_row(
                (
                    label,
                    _format_currency_simple(item.qty),
                    _format_currency_simple(item.unit_price),
                    _format_currency_simple(item.line_total),
                )
            )
        )

    lines.append(_draw_line("═"))
    lines.append(f">>R Subtotal: {_format_currency_simple(invoice.subtotal)}")
    if invoice.discount and float(invoice.discount) > 0:
        discount_amount = _format_currency_simple(-abs(float(invoice.discount)))
        lines.append(f">>R Discount: {discount_amount}")
    if invoice.loyalty_redeemed and float(invoice.loyalty_redeemed) > 0:
        redeemed_amount = _format_currency_simple(-abs(float(invoice.loyalty_redeemed)))
        lines.append(f">>R Loyalty Redeem: {redeemed_amount}")
    if invoice.delivery_fee and float(invoice.delivery_fee) > 0:
        lines.append(f">>R Delivery Fee: {_format_currency_simple(invoice.delivery_fee)}")
    lines.append(f">>R Grand Total: {_format_currency_simple(invoice.total)}")
    lines.append(f">>R Paid: {_format_currency_simple(invoice.paid_total)}")
    if float(invoice.remaining_total or 0) > 0:
        lines.append(f">>R Remaining: {_format_currency_simple(invoice.remaining_total)}")

    lines.append(_draw_line("═"))
    lines.append(">>C LOYALTY")
    has_customer = bool(invoice.customer_id or invoice.customer_name or invoice.customer_phone)
    earned_points = int(invoice.loyalty_earned) if has_customer else 0
    redeemed_points = int(abs(float(invoice.loyalty_redeemed or 0))) if has_customer else 0
    lines.append(f">>R Earned this invoice: {earned_points}")
    lines.append(f">>R Redeemed this invoice: {redeemed_points}")
    if has_customer and loyalty_balance is not None:
        lines.append(f">>R Remaining points: {int(loyalty_balance)}")
    if (
        has_customer
        and loyalty_balance is not None
        and loyalty_threshold
        and loyalty_threshold > 0
        and loyalty_balance >= loyalty_threshold
    ):
        lines.append(f">>R Threshold reached: {loyalty_threshold}")

    lines.append(_draw_line("═"))
    lines.append(">>C Thank you")
    return "\n".join(lines)


def receipt_preview_text(
    invoice: JewelryInvoice,
    items: list[JewelryInvoiceItem],
    *,
    loyalty_balance: float | None = None,
    loyalty_threshold: int | None = None,
    gallery: GallerySettings | None = None,
) -> str:
    """Return the receipt text for preview/debugging."""
    return build_receipt_text(
        invoice,
        items,
        loyalty_balance=loyalty_balance,
        loyalty_threshold=loyalty_threshold,
        gallery=gallery,
    )
