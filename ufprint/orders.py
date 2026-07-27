"""SQLite order persistence."""

import json
import os
import sqlite3
from datetime import datetime

from ufprint.paths import get_app_dir

DB_NAME = os.path.join(get_app_dir(), "card_printing.db")


def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_name TEXT,
            customer_phone TEXT,
            customer_email TEXT,
            company_name TEXT,
            print_specs TEXT,
            side_a_path TEXT,
            side_b_path TEXT,
            created_at TEXT,
            status TEXT
        )
        """
    )
    conn.commit()
    conn.close()


def encode_print_specs(specs_dict):
    return json.dumps(specs_dict, ensure_ascii=False)


def decode_print_specs(json_str):
    if not json_str:
        return {}
    try:
        return json.loads(json_str)
    except (TypeError, json.JSONDecodeError):
        return {}


def insert_order(
    customer_name,
    customer_phone,
    customer_email,
    company_name,
    print_specs,
    side_a_path,
    side_b_path,
    created_at=None,
    status="Черновик",
):
    if created_at is None:
        created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(print_specs, dict):
        print_specs = encode_print_specs(print_specs)

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO orders (
            customer_name, customer_phone, customer_email,
            company_name, print_specs, side_a_path, side_b_path,
            created_at, status
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            customer_name,
            customer_phone,
            customer_email,
            company_name,
            print_specs,
            side_a_path,
            side_b_path,
            created_at,
            status,
        ),
    )
    order_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return order_id


def list_orders():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, customer_name, company_name, created_at, print_specs, status "
        "FROM orders ORDER BY created_at DESC"
    )
    orders = cursor.fetchall()
    conn.close()
    return orders


def get_order(order_id):
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM orders WHERE id = ?", (order_id,))
    order = cursor.fetchone()
    conn.close()
    return order
