"""Order read-model: look up invoices by customer email or invoice id."""
from __future__ import annotations

from ..database.db import get_conn


def find_customer(email: str) -> dict | None:
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT customer_id, first_name, last_name, email FROM customers"
            " WHERE lower(email) = lower(?)",
            (email.strip(),),
        ).fetchone()
    finally:
        conn.close()
    return dict(row) if row else None


def orders_for_email(email: str) -> list[dict]:
    customer = find_customer(email)
    if not customer:
        return []
    conn = get_conn()
    try:
        rows = conn.execute(
            """SELECT invoice_id, invoice_date, status, total_cents
               FROM invoices WHERE customer_id = ?
               ORDER BY invoice_date DESC""",
            (customer["customer_id"],),
        ).fetchall()
    finally:
        conn.close()
    return [
        {
            "invoice_id": r["invoice_id"],
            "date": r["invoice_date"],
            "status": r["status"],
            "total": f"${r['total_cents'] / 100:.2f}",
            "customer": f"{customer['first_name']} {customer['last_name']}",
        }
        for r in rows
    ]


def order_detail(invoice_id: int) -> dict | None:
    conn = get_conn()
    try:
        inv = conn.execute(
            """SELECT i.invoice_id, i.invoice_date, i.status, i.total_cents,
                      c.first_name, c.last_name, c.email
               FROM invoices i JOIN customers c ON c.customer_id = i.customer_id
               WHERE i.invoice_id = ?""",
            (invoice_id,),
        ).fetchone()
        if inv is None:
            return None
        lines = conn.execute(
            """SELECT t.title, a.name AS artist, l.unit_price_cents
               FROM invoice_lines l
               JOIN tracks t ON t.track_id = l.track_id
               JOIN albums al ON al.album_id = t.album_id
               JOIN artists a ON a.artist_id = al.artist_id
               WHERE l.invoice_id = ? ORDER BY t.title""",
            (invoice_id,),
        ).fetchall()
    finally:
        conn.close()
    return {
        "invoice_id": inv["invoice_id"],
        "date": inv["invoice_date"],
        "status": inv["status"],
        "total": f"${inv['total_cents'] / 100:.2f}",
        "customer": f"{inv['first_name']} {inv['last_name']} <{inv['email']}>",
        "items": [
            {"title": r["title"], "artist": r["artist"],
             "price": f"${r['unit_price_cents'] / 100:.2f}"}
            for r in lines
        ],
    }


STORE_POLICIES = {
    "returns": (
        "Digital tracks can be refunded within 14 days of purchase if not "
        "downloaded. Contact support with your invoice number."
    ),
    "delivery": (
        "Downloads are available instantly after purchase; physical album "
        "orders ship within 3 business days and are tracked by invoice number."
    ),
    "payments": "We accept all major credit cards and PayPal.",
    "account": (
        "Your purchase history is tied to the email you used at checkout. "
        "Give that email to support and we can look up any invoice."
    ),
}


def policy_answer(topic: str) -> str:
    return STORE_POLICIES.get(
        topic.lower(),
        "I don't have a policy page for that — a human agent can help. "
        "Type 'human' to be handed off.",
    )
