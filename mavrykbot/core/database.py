from __future__ import annotations

import os
from datetime import datetime
from typing import Any, Dict, Iterable, Optional, Sequence, Tuple

import psycopg2
import psycopg2.pool

from mavrykbot.core.db_schema import PAYMENT_RECEIPT_TABLE, PaymentReceiptColumns


class Database:
    """Lightweight PostgreSQL helper built on psycopg2's SimpleConnectionPool."""

    def __init__(self) -> None:
        self._pool = psycopg2.pool.SimpleConnectionPool(
            minconn=1,
            maxconn=5,
            host=os.getenv("DB_HOST"),
            port=os.getenv("DB_PORT"),
            dbname=os.getenv("DB_NAME"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD"),
        )

    def execute(self, query: str, params: Optional[Sequence[Any]] = None) -> None:
        conn = self._pool.getconn()
        try:
            with conn.cursor() as cur:
                cur.execute(query, params)
                conn.commit()
        finally:
            self._pool.putconn(conn)

    def fetch_one(
        self, query: str, params: Optional[Sequence[Any]] = None
    ) -> Optional[Tuple[Any, ...]]:
        conn = self._pool.getconn()
        try:
            with conn.cursor() as cur:
                cur.execute(query, params)
                return cur.fetchone()
        finally:
            self._pool.putconn(conn)

    def fetch_all(
        self, query: str, params: Optional[Sequence[Any]] = None
    ) -> Iterable[Tuple[Any, ...]]:
        conn = self._pool.getconn()
        try:
            with conn.cursor() as cur:
                cur.execute(query, params)
                return cur.fetchall()
        finally:
            self._pool.putconn(conn)


db = Database()


def _split_transaction_content(content: str) -> Tuple[str, str]:
    """
    Split Sepay's `transaction_content` into (order_code, sender).
    Falls back to a single token when we cannot reliably detect two parts.
    """
    parts = (content or "").strip().split()
    if not parts:
        raise ValueError("transaction_content is empty")
    if len(parts) == 1:
        return parts[0], parts[0]
    return parts[-1], parts[0]


def insert_payment_receipt(transaction_data: Dict[str, Any]) -> None:
    """
    Persist Sepay webhook data to the canonical payment_receipt table.
    """

    order_code, sender = _split_transaction_content(
        transaction_data.get("transaction_content", "")
    )
    transaction_date = transaction_data.get("transaction_date", "")
    try:
        paid_date = datetime.strptime(transaction_date, "%Y-%m-%d %H:%M:%S").date()
    except ValueError:
        paid_date = datetime.utcnow().date()

    amount_raw = transaction_data.get("amount_in", "0")
    amount = int(str(amount_raw).split(".")[0] or 0)

    sql = f"""
        INSERT INTO {PAYMENT_RECEIPT_TABLE} (
            {PaymentReceiptColumns.MA_DON_HANG},
            {PaymentReceiptColumns.NGAY_THANH_TOAN},
            {PaymentReceiptColumns.SO_TIEN},
            {PaymentReceiptColumns.NGUOI_GUI},
            {PaymentReceiptColumns.NOI_DUNG_CK}
        ) VALUES (%s, %s, %s, %s, %s)
    """
    db.execute(
        sql,
        (
            order_code,
            paid_date,
            amount,
            sender,
            transaction_data.get("transaction_content", ""),
        ),
    )
