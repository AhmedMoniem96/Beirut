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


@dataclass
class ProductionHistoryRow:
    order_no: str
    datetime: str
    status: str
    product_name: str
    qty_to_produce: float
    qty_produced: float
    total_cost: float


@dataclass
class MaterialUsageRow:
    material_name: str
    total_qty: float
    total_cost: float


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


def production_history(
    start_iso: str,
    end_iso: str,
    status: str,
    product_id: int | None,
) -> List[ProductionHistoryRow]:
    conn = get_conn()
    cur = conn.cursor()
    query = """SELECT o.order_no, o.datetime, o.status,
                      p.name_en || ' / ' || p.name_ar,
                      o.qty_to_produce, o.qty_produced,
                      (COALESCE(SUM(c.qty_consumed * c.cost_at_time), 0) + o.labor_cost + o.overhead_cost)
               FROM jw_production_orders o
               JOIN jw_products p ON p.id = o.product_id
               LEFT JOIN jw_production_consumption c ON c.production_order_id = o.id
               WHERE o.datetime BETWEEN ? AND ?"""
    params: List = [start_iso, end_iso]
    if status and status != "all":
        query += " AND o.status = ?"
        params.append(status)
    if product_id:
        query += " AND o.product_id = ?"
        params.append(product_id)
    query += " GROUP BY o.id ORDER BY o.datetime DESC"
    cur.execute(query, tuple(params))
    rows = cur.fetchall()
    conn.close()
    return [
        ProductionHistoryRow(
            order_no=row[0],
            datetime=row[1],
            status=row[2],
            product_name=row[3],
            qty_to_produce=row[4],
            qty_produced=row[5],
            total_cost=row[6],
        )
        for row in rows
    ]


def material_usage(start_iso: str, end_iso: str) -> List[MaterialUsageRow]:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """SELECT m.name_en || ' / ' || m.name_ar,
                  COALESCE(SUM(c.qty_consumed), 0),
                  COALESCE(SUM(c.qty_consumed * c.cost_at_time), 0)
           FROM jw_production_consumption c
           JOIN jw_materials m ON m.id = c.material_id
           JOIN jw_production_orders o ON o.id = c.production_order_id
           WHERE o.datetime BETWEEN ? AND ?
           GROUP BY m.id
           ORDER BY total_cost DESC""",
        (start_iso, end_iso),
    )
    rows = cur.fetchall()
    conn.close()
    return [
        MaterialUsageRow(material_name=row[0], total_qty=row[1], total_cost=row[2])
        for row in rows
    ]
