# beirut_pos/services/reports.py
from ..core.db import get_conn

def z_report(iso_date: str):
    """
    Daily totals for ISO date 'YYYY-MM-DD'.

    Discounts are derived as:
      discount = max( sum(price_cents*qty) - sum(payments.amount_cents) , 0 )
    for each paid order that day, then summed.
    """
    start = f"{iso_date}T00:00:00"
    end   = f"{iso_date}T23:59:59"
    conn = get_conn(); c = conn.cursor()

    # 1) totals by payment method
    by_method_rows = c.execute("""
      SELECT method, SUM(amount_cents) AS amt
      FROM payments
      WHERE paid_at BETWEEN ? AND ?
      GROUP BY method
    """, (start, end)).fetchall()
    by_method = [(r["method"], int(r["amt"] or 0)) for r in by_method_rows]
    total_rev = sum(amt for _, amt in by_method)

    # 2) count paid orders for the day
    orders_count = c.execute("""
      SELECT COUNT(*) AS cnt
      FROM orders
      WHERE status='paid' AND closed_at BETWEEN ? AND ?
    """, (start, end)).fetchone()["cnt"] or 0
    orders_count = int(orders_count)

    # 3) sum derived discounts for those paid orders
    # subtotal_cents uses ROUND() to avoid float artifacts from qty REAL
    total_disc_row = c.execute("""
      WITH paid_orders AS (
        SELECT id
        FROM orders
        WHERE status='paid' AND closed_at BETWEEN ? AND ?
      ),
      subtotals AS (
        SELECT oi.order_id,
               CAST(ROUND(SUM(oi.price_cents * oi.qty)) AS INTEGER) AS subtotal_cents
        FROM order_items oi
        WHERE oi.order_id IN (SELECT id FROM paid_orders)
        GROUP BY oi.order_id
      ),
      paid AS (
        SELECT p.order_id,
               CAST(SUM(p.amount_cents) AS INTEGER) AS paid_cents
        FROM payments p
        WHERE p.order_id IN (SELECT id FROM paid_orders)
        GROUP BY p.order_id
      )
      SELECT CAST(SUM(
               CASE
                 WHEN COALESCE(s.subtotal_cents,0) > COALESCE(p.paid_cents,0)
                 THEN COALESCE(s.subtotal_cents,0) - COALESCE(p.paid_cents,0)
                 ELSE 0
               END
             ) AS INTEGER) AS total_disc
      FROM paid_orders o
      LEFT JOIN subtotals s ON s.order_id=o.id
      LEFT JOIN paid      p ON p.order_id=o.id
    """, (start, end)).fetchone()
    total_disc = int(total_disc_row["total_disc"] or 0)

    # 4) PS items count (heuristic: product contains 'PS ')
    ps_items_count = c.execute("""
      SELECT COUNT(*) AS cnt
      FROM order_items
      WHERE order_id IN (
        SELECT id FROM orders WHERE status='paid' AND closed_at BETWEEN ? AND ?
      )
      AND (product_name LIKE 'PS %' OR product_name LIKE '% PS %')
    """, (start, end)).fetchone()["cnt"] or 0
    ps_items_count = int(ps_items_count)

    conn.close()
    return {
        "date": iso_date,
        "by_method": by_method,
        "total_cents": int(total_rev),
        "discount_cents": int(total_disc),
        "orders_count": orders_count,
        "ps_items_count": ps_items_count,
    }

def format_z_text(data, company="Beirut Coffee", currency="EGP"):
    lines = [
        f"*** DAILY Z-REPORT ***",
        f"Company: {company}",
        f"Date: {data['date']}",
        "-"*32,
        "By Method:"
    ]
    for method, amt in data["by_method"]:
        lines.append(f"  {method:<10} : {amt/100:.2f} {currency}")
    lines += [
        "-"*32,
        f"Orders      : {data['orders_count']}",
        f"PS Items    : {data['ps_items_count']}",
        f"Discounts   : {data['discount_cents']/100:.2f} {currency}",
        f"TOTAL       : {data['total_cents']/100:.2f} {currency}",
        "-"*32
    ]
    return "\n".join(lines)
