"""Reporting queries for Jewelry app."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

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


@dataclass
class ExpenseCategoryAggregate:
    category: str
    count: int
    total_amount: float


@dataclass
class ExpensePurchaseRow:
    date: str
    category: str
    vendor_or_worker: str
    description: str
    amount: float
    payment_method: str


@dataclass
class MaterialPurchaseAggregate:
    material: str
    qty_purchased: float
    total_cost: float
    avg_unit_cost: float


@dataclass
class WorkerWageAggregate:
    worker: str
    period: str
    total_paid: float


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
@dataclass
class ProductionHistoryRow:
    order_no: str
    datetime: str
    status: str
    product_name: str
    material_cost: float
    extra_cost: float
    total_cost: float
    selling_price: float
    profit: float
    margin_pct: float
    qty_to_produce: float
    qty_produced: float


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
    where_clause = "i.txn_type = 'return' AND i.datetime BETWEEN ? AND ?"
    params: List = [start_iso, end_iso]
    joins = ""
    total_expression = "i.total"
    if product_id is not None:
        # Filtering at item level is essential: an invoice containing several
        # returned products must contribute only the selected product's value.
        joins = " JOIN jw_invoice_items ii ON ii.invoice_id = i.id"
        where_clause += " AND ii.product_id = ?"
        params.append(product_id)
        total_expression = "ii.line_total"
    cur.execute(
        f"""SELECT COUNT(DISTINCT i.id), COALESCE(SUM({total_expression}), 0)
           FROM jw_invoices i{joins}
           WHERE {where_clause}""",
        tuple(params),
    )
    summary = cur.fetchone()
    cur.execute(
        f"""SELECT i.return_reason, COUNT(DISTINCT i.id), COALESCE(SUM({total_expression}), 0)
           FROM jw_invoices i{joins}
           WHERE {where_clause}
           GROUP BY i.return_reason
           ORDER BY COUNT(DISTINCT i.id) DESC""",
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
    # Some callers open pre-migration databases directly.  Treat an absent
    # snapshot column exactly like a NULL legacy value rather than failing the
    # whole report; init_jewelry_db() adds both columns to normal databases.
    cur.execute("PRAGMA table_info(jw_production_orders)")
    order_columns = {row[1] for row in cur.fetchall()}
    unit_price = (
        "COALESCE(o.selling_price_per_unit_snapshot, p.price, 0)"
        if "selling_price_per_unit_snapshot" in order_columns
        else "COALESCE(p.price, 0)"
    )
    additional_cost = (
        "COALESCE(o.additional_cost_batch_snapshot, "
        "COALESCE(o.labor_cost, 0) + COALESCE(o.overhead_cost, 0))"
        if "additional_cost_batch_snapshot" in order_columns
        else "COALESCE(o.labor_cost, 0) + COALESCE(o.overhead_cost, 0)"
    )
    query = f"""SELECT o.id, o.order_no, o.datetime, o.status,
                      p.name_en || ' / ' || p.name_ar,
                      o.qty_to_produce, o.qty_produced,
                      COALESCE(SUM(c.qty_consumed * c.cost_at_time), 0) AS material_cost,
                      ({additional_cost}) AS extra_cost,
                      (COALESCE(SUM(c.qty_consumed * c.cost_at_time), 0) + ({additional_cost})) AS total_cost,
                      (COALESCE(o.qty_produced, 0) * ({unit_price})) AS selling_price
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
            order_no=row[1],
            datetime=row[2],
            status=row[3],
            product_name=row[4],
            qty_to_produce=row[5],
            qty_produced=row[6],
            material_cost=row[7],
            extra_cost=row[8],
            total_cost=row[9],
            selling_price=row[10],
            profit=row[10] - row[9],
            margin_pct=((row[10] - row[9]) / row[10] * 100.0) if row[10] > 0 else 0.0,
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


def expense_report_data(start_iso: str, end_iso: str, *, category: Optional[str] = None, vendor_worker_term: str = "", payment_method: Optional[str] = None) -> dict:
    conn = get_conn()
    cur = conn.cursor()
    date_from = start_iso[:10]
    date_to = end_iso[:10]
    filters: List[str] = ["p.date BETWEEN ? AND ?"]
    params: List[object] = [date_from, date_to]
    if category:
        filters.append("p.category = ?")
        params.append(category)
    if payment_method:
        filters.append("LOWER(COALESCE(p.payment_method, '')) = ?")
        params.append(payment_method.strip().lower())
    if vendor_worker_term.strip():
        term = f"%{vendor_worker_term.strip().lower()}%"
        filters.append("(LOWER(COALESCE(p.vendor, '')) LIKE ? OR LOWER(COALESCE(w.name, '')) LIKE ?)")
        params.extend([term, term])
    where_sql = " AND ".join(filters)

    cur.execute(f"""SELECT p.category, COUNT(*), COALESCE(SUM(p.amount), 0)
                     FROM jw_purchases p
                     LEFT JOIN jw_workers w ON w.id = p.worker_id
                     WHERE {where_sql}
                     GROUP BY p.category
                     ORDER BY 3 DESC""", tuple(params))
    by_category = [ExpenseCategoryAggregate(str(r[0] or ""), int(r[1] or 0), float(r[2] or 0)) for r in cur.fetchall()]

    cur.execute(f"""SELECT p.date, p.category, COALESCE(NULLIF(TRIM(w.name), ''), NULLIF(TRIM(p.vendor), ''), ''),
                          COALESCE(p.description, ''), COALESCE(p.amount, 0), COALESCE(p.payment_method, '')
                   FROM jw_purchases p
                   LEFT JOIN jw_workers w ON w.id = p.worker_id
                   WHERE {where_sql}
                   ORDER BY p.date DESC, p.id DESC""", tuple(params))
    purchases = [ExpensePurchaseRow(str(r[0] or ""), str(r[1] or ""), str(r[2] or ""), str(r[3] or ""), float(r[4] or 0), str(r[5] or "")) for r in cur.fetchall()]

    cur.execute(f"""SELECT COALESCE(NULLIF(TRIM(m.name_en), ''), NULLIF(TRIM(m.name_ar), ''), 'N/A'),
                          COALESCE(SUM(p.material_qty), 0),
                          COALESCE(SUM(p.amount), 0)
                   FROM jw_purchases p
                   LEFT JOIN jw_materials m ON m.id = p.linked_material_id
                   LEFT JOIN jw_workers w ON w.id = p.worker_id
                   WHERE {where_sql} AND p.category = 'Material Purchase' AND p.linked_material_id IS NOT NULL
                   GROUP BY p.linked_material_id, m.name_en, m.name_ar
                   ORDER BY 3 DESC""", tuple(params))
    material_rows = []
    for name, qty, total in cur.fetchall():
        q = float(qty or 0)
        t = float(total or 0)
        material_rows.append(MaterialPurchaseAggregate(str(name or ""), q, t, (t / q) if q else 0.0))

    cur.execute(f"""SELECT COALESCE(NULLIF(TRIM(w.name), ''), NULLIF(TRIM(p.vendor), ''), 'N/A'),
                          COALESCE(NULLIF(TRIM(p.wage_period), ''), 'N/A'),
                          COALESCE(SUM(p.amount), 0)
                   FROM jw_purchases p
                   LEFT JOIN jw_workers w ON w.id = p.worker_id
                   WHERE {where_sql} AND p.category = 'Worker Wage'
                   GROUP BY 1, 2
                   ORDER BY 3 DESC""", tuple(params))
    wages = [WorkerWageAggregate(str(r[0] or ""), str(r[1] or "N/A"), float(r[2] or 0)) for r in cur.fetchall()]

    conn.close()
    total_expenses = sum(r.amount for r in purchases)
    return {
        "by_category": by_category,
        "purchases": purchases,
        "material_purchases": material_rows,
        "worker_wages": wages,
        "total_expenses": total_expenses,
        "material_expenses": sum(r.total_cost for r in material_rows),
        "bills_expenses": sum(r.total_amount for r in by_category if "bill" in r.category.lower()),
        "wages_expenses": sum(r.total_paid for r in wages),
    }
