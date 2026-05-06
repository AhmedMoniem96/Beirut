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
class CustomerAggregate:
    customer: str
    phone: str
    spend: float
    points: float
    invoice_count: int
    last_purchase: str


@dataclass
class ProductRevenueAggregate:
    name: str
    code: str
    qty: float
    revenue: float


def top_products_by_revenue(start_iso: str, end_iso: str, limit: int = 10, product_id: int | None = None) -> List[ProductRevenueAggregate]:
    conn = get_conn()
    cur = conn.cursor()
    query = """SELECT ii.product_name, ii.product_code, COALESCE(SUM(ii.qty), 0), COALESCE(SUM(ii.line_total), 0)
               FROM jw_invoice_items ii
               JOIN jw_invoices i ON i.id = ii.invoice_id
               WHERE i.txn_type = 'sale' AND i.datetime BETWEEN ? AND ?"""
    params: List = [start_iso, end_iso]
    if product_id is not None:
        query += " AND ii.product_id = ?"
        params.append(product_id)
    query += " GROUP BY ii.product_name, ii.product_code ORDER BY 4 DESC LIMIT ?"
    params.append(limit)
    cur.execute(query, tuple(params))
    rows = cur.fetchall()
    conn.close()
    return [ProductRevenueAggregate(row[0], row[1], row[2], row[3]) for row in rows]


def customer_aggregates(start_iso: str, end_iso: str, customer_term: str = '', limit: int = 20) -> List[CustomerAggregate]:
    conn = get_conn()
    cur = conn.cursor()
    query = """SELECT COALESCE(NULLIF(TRIM(customer_name), ''), 'Walk-in'),
                      COALESCE(customer_phone, ''),
                      COALESCE(SUM(total), 0),
                      COALESCE(SUM(loyalty_earned), 0),
                      COUNT(*),
                      COALESCE(MAX(datetime), '')
               FROM jw_invoices
               WHERE txn_type = 'sale' AND datetime BETWEEN ? AND ?"""
    params: List = [start_iso, end_iso]
    if customer_term.strip():
        query += " AND (LOWER(COALESCE(customer_name,'')) LIKE ? OR COALESCE(customer_phone,'') LIKE ?)"
        term = f"%{customer_term.strip().lower()}%"
        params.extend([term, f"%{customer_term.strip()}%"])
    query += " GROUP BY COALESCE(NULLIF(TRIM(customer_name), ''), 'Walk-in'), COALESCE(customer_phone, '') ORDER BY 3 DESC LIMIT ?"
    params.append(limit)
    cur.execute(query, tuple(params))
    rows = cur.fetchall()
    conn.close()
    return [CustomerAggregate(*row) for row in rows]


def inventory_value_estimate() -> float:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT COALESCE(SUM(qty_on_hand * price), 0) FROM jw_products")
    value = float(cur.fetchone()[0] or 0.0)
    conn.close()
    return value
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


def _invoice_filter_clause(
    *,
    start_iso: str,
    end_iso: str,
    txn_type: str,
    product_id: int | None = None,
) -> Tuple[str, List]:
    clause = "txn_type = ? AND datetime BETWEEN ? AND ?"
    params: List = [txn_type, start_iso, end_iso]
    if product_id is not None:
        clause += """ AND EXISTS (
                        SELECT 1
                        FROM jw_invoice_items ii
                        WHERE ii.invoice_id = jw_invoices.id
                          AND ii.product_id = ?
                    )"""
        params.append(product_id)
    return clause, params


def sales_aggregate(start_iso: str, end_iso: str, product_id: int | None = None) -> SalesAggregate:
    conn = get_conn()
    cur = conn.cursor()
    where_clause, params = _invoice_filter_clause(
        start_iso=start_iso,
        end_iso=end_iso,
        txn_type="sale",
        product_id=product_id,
    )
    cur.execute(
        f"""SELECT COUNT(*), COALESCE(SUM(subtotal), 0),
                  COALESCE(SUM(discount), 0), COALESCE(SUM(total), 0)
           FROM jw_invoices
           WHERE {where_clause}""",
        tuple(params),
    )
    row = cur.fetchone()
    conn.close()
    return SalesAggregate(
        invoice_count=row[0],
        subtotal=row[1],
        discounts=row[2],
        net_sales=row[3],
    )


def payment_breakdown(
    start_iso: str,
    end_iso: str,
    *,
    include_returns: bool = False,
    product_id: int | None = None,
) -> Dict[str, float]:
    conn = get_conn()
    cur = conn.cursor()
    if include_returns:
        sale_where, sale_params = _invoice_filter_clause(
            start_iso=start_iso,
            end_iso=end_iso,
            txn_type="sale",
            product_id=product_id,
        )
        return_where, return_params = _invoice_filter_clause(
            start_iso=start_iso,
            end_iso=end_iso,
            txn_type="return",
            product_id=product_id,
        )
        cur.execute(
            f"""SELECT payment_method,
                      COALESCE(SUM(CASE WHEN txn_type = 'sale' THEN total ELSE -total END), 0)
               FROM jw_invoices
               WHERE ({sale_where}) OR ({return_where})
               GROUP BY payment_method""",
            tuple(sale_params + return_params),
        )
    else:
        where_clause, params = _invoice_filter_clause(
            start_iso=start_iso,
            end_iso=end_iso,
            txn_type="sale",
            product_id=product_id,
        )
        cur.execute(
            f"""SELECT payment_method, COALESCE(SUM(total), 0)
               FROM jw_invoices
               WHERE {where_clause}
               GROUP BY payment_method""",
            tuple(params),
        )
    rows = cur.fetchall()
    conn.close()
    return {row[0]: row[1] for row in rows}


def returns_aggregate(start_iso: str, end_iso: str, product_id: int | None = None) -> ReturnsAggregate:
    conn = get_conn()
    cur = conn.cursor()
    where_clause, params = _invoice_filter_clause(
        start_iso=start_iso,
        end_iso=end_iso,
        txn_type="return",
        product_id=product_id,
    )
    cur.execute(
        f"""SELECT COUNT(*), COALESCE(SUM(total), 0)
           FROM jw_invoices
           WHERE {where_clause}""",
        tuple(params),
    )
    summary = cur.fetchone()
    cur.execute(
        f"""SELECT return_reason, COUNT(*), COALESCE(SUM(total), 0)
           FROM jw_invoices
           WHERE {where_clause}
           GROUP BY return_reason
           ORDER BY COUNT(*) DESC""",
        tuple(params),
    )
    reasons = cur.fetchall()
    conn.close()
    return ReturnsAggregate(
        return_count=summary[0],
        return_total=summary[1],
        reasons=[(row[0] or "N/A", row[1], row[2]) for row in reasons],
    )


def top_products(
    start_iso: str,
    end_iso: str,
    limit: int = 5,
    product_id: int | None = None,
) -> List[ProductAggregate]:
    conn = get_conn()
    cur = conn.cursor()
    query = """SELECT product_name, product_code, COALESCE(SUM(qty), 0) AS total_qty
               FROM jw_invoice_items
               WHERE invoice_id IN (
                   SELECT id FROM jw_invoices
                   WHERE txn_type = 'sale' AND datetime BETWEEN ? AND ?
               )"""
    params: List = [start_iso, end_iso]
    if product_id is not None:
        query += " AND product_id = ?"
        params.append(product_id)
    query += """
               GROUP BY product_name, product_code
               ORDER BY total_qty DESC
               LIMIT ?"""
    params.append(limit)
    cur.execute(query, tuple(params))
    rows = cur.fetchall()
    conn.close()
    return [ProductAggregate(row[0], row[1], row[2]) for row in rows]


def lowest_products(
    start_iso: str,
    end_iso: str,
    limit: int = 5,
    product_id: int | None = None,
) -> List[ProductAggregate]:
    conn = get_conn()
    cur = conn.cursor()
    query = """SELECT product_name, product_code, COALESCE(SUM(qty), 0) AS total_qty
               FROM jw_invoice_items
               WHERE invoice_id IN (
                   SELECT id FROM jw_invoices
                   WHERE txn_type = 'sale' AND datetime BETWEEN ? AND ?
               )"""
    params: List = [start_iso, end_iso]
    if product_id is not None:
        query += " AND product_id = ?"
        params.append(product_id)
    query += """
               GROUP BY product_name, product_code
               HAVING total_qty > 0
               ORDER BY total_qty ASC
               LIMIT ?"""
    params.append(limit)
    cur.execute(query, tuple(params))
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
