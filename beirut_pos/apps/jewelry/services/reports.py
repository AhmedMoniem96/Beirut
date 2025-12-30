"""Reporting queries for Jewelry app."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple

from beirut_pos.core.db import get_conn


@dataclass
class SalesAggregate:
    invoice_count: int
    subtotal: float
    discounts: float
    net_sales: float


@dataclass
class ReturnsAggregate:
    return_count: int
    return_total: float
    reasons: List[Tuple[str, int, float]]


@dataclass
class ProductAggregate:
    name: str
    code: str
    qty: float


def sales_aggregate(start_iso: str, end_iso: str) -> SalesAggregate:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """SELECT COUNT(*), COALESCE(SUM(subtotal), 0),
                  COALESCE(SUM(discount), 0), COALESCE(SUM(total), 0)
           FROM jw_invoices
           WHERE txn_type = 'sale' AND datetime BETWEEN ? AND ?""",
        (start_iso, end_iso),
    )
    row = cur.fetchone()
    conn.close()
    return SalesAggregate(
        invoice_count=row[0],
        subtotal=row[1],
        discounts=row[2],
        net_sales=row[3],
    )


def payment_breakdown(start_iso: str, end_iso: str, *, include_returns: bool = False) -> Dict[str, float]:
    conn = get_conn()
    cur = conn.cursor()
    if include_returns:
        cur.execute(
            """SELECT payment_method,
                      COALESCE(SUM(CASE WHEN txn_type = 'sale' THEN total ELSE -total END), 0)
               FROM jw_invoices
               WHERE datetime BETWEEN ? AND ?
               GROUP BY payment_method""",
            (start_iso, end_iso),
        )
    else:
        cur.execute(
            """SELECT payment_method, COALESCE(SUM(total), 0)
               FROM jw_invoices
               WHERE txn_type = 'sale' AND datetime BETWEEN ? AND ?
               GROUP BY payment_method""",
            (start_iso, end_iso),
        )
    rows = cur.fetchall()
    conn.close()
    return {row[0]: row[1] for row in rows}


def returns_aggregate(start_iso: str, end_iso: str) -> ReturnsAggregate:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """SELECT COUNT(*), COALESCE(SUM(total), 0)
           FROM jw_invoices
           WHERE txn_type = 'return' AND datetime BETWEEN ? AND ?""",
        (start_iso, end_iso),
    )
    summary = cur.fetchone()
    cur.execute(
        """SELECT return_reason, COUNT(*), COALESCE(SUM(total), 0)
           FROM jw_invoices
           WHERE txn_type = 'return' AND datetime BETWEEN ? AND ?
           GROUP BY return_reason
           ORDER BY COUNT(*) DESC""",
        (start_iso, end_iso),
    )
    reasons = cur.fetchall()
    conn.close()
    return ReturnsAggregate(
        return_count=summary[0],
        return_total=summary[1],
        reasons=[(row[0] or "N/A", row[1], row[2]) for row in reasons],
    )


def top_products(start_iso: str, end_iso: str, limit: int = 5) -> List[ProductAggregate]:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """SELECT product_name, product_code, COALESCE(SUM(qty), 0) AS total_qty
           FROM jw_invoice_items
           WHERE invoice_id IN (
               SELECT id FROM jw_invoices
               WHERE txn_type = 'sale' AND datetime BETWEEN ? AND ?
           )
           GROUP BY product_name, product_code
           ORDER BY total_qty DESC
           LIMIT ?""",
        (start_iso, end_iso, limit),
    )
    rows = cur.fetchall()
    conn.close()
    return [ProductAggregate(row[0], row[1], row[2]) for row in rows]


def lowest_products(start_iso: str, end_iso: str, limit: int = 5) -> List[ProductAggregate]:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """SELECT product_name, product_code, COALESCE(SUM(qty), 0) AS total_qty
           FROM jw_invoice_items
           WHERE invoice_id IN (
               SELECT id FROM jw_invoices
               WHERE txn_type = 'sale' AND datetime BETWEEN ? AND ?
           )
           GROUP BY product_name, product_code
           HAVING total_qty > 0
           ORDER BY total_qty ASC
           LIMIT ?""",
        (start_iso, end_iso, limit),
    )
    rows = cur.fetchall()
    conn.close()
    return [ProductAggregate(row[0], row[1], row[2]) for row in rows]


def stock_alerts() -> Tuple[List[Tuple], List[Tuple]]:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """SELECT name_ar, name_en, sku, qty_on_hand, min_qty
           FROM jw_products
           WHERE qty_on_hand <= 0
           ORDER BY qty_on_hand ASC"""
    )
    out_of_stock = cur.fetchall()
    cur.execute(
        """SELECT name_ar, name_en, sku, qty_on_hand, min_qty
           FROM jw_products
           WHERE qty_on_hand > 0 AND qty_on_hand <= min_qty
           ORDER BY qty_on_hand ASC"""
    )
    near_out = cur.fetchall()
    conn.close()
    return out_of_stock, near_out
