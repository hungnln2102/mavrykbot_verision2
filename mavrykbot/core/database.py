from __future__ import annotations

import logging
import os
import threading
from datetime import datetime
from typing import Any, Dict, Iterable, Optional, Sequence, Tuple

import psycopg2
import psycopg2.pool
from psycopg2 import InterfaceError, OperationalError

from mavrykbot.core.db_schema import PAYMENT_RECEIPT_TABLE, PaymentReceiptColumns


logger = logging.getLogger(__name__)


class Database:
    """Lightweight PostgreSQL helper built on psycopg2's SimpleConnectionPool."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._pool = self._create_pool()

    def _create_pool(self) -> psycopg2.pool.SimpleConnectionPool:
        return psycopg2.pool.SimpleConnectionPool(
            minconn=1,
            maxconn=5,
            host=os.getenv("DB_HOST"),
            port=os.getenv("DB_PORT"),
            dbname=os.getenv("DB_NAME"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD"),
            keepalives=1,
            keepalives_idle=30,
            keepalives_interval=10,
            keepalives_count=5,
        )

    def _reset_pool(self) -> None:
        # When PostgreSQL restarts, the pool keeps stale connections; rebuild it once.
        with self._lock:
            try:
                if self._pool:
                    self._pool.closeall()
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning("Failed closing old DB pool: %s", exc)
            self._pool = self._create_pool()
            logger.info("Recreated PostgreSQL connection pool after failure.")

    def _borrow_connection(self):
        conn = self._pool.getconn()
        if conn and conn.closed:
            # Drop closed/stale connection and borrow a fresh one.
            try:
                self._pool.putconn(conn, close=True)
            except Exception:
                pass
            conn = self._pool.getconn()
        return conn

    def _safe_putconn(self, conn, close: bool = False) -> None:
        try:
            self._pool.putconn(conn, close=close)
        except Exception:
            pass

    def _with_reconnect(self, query_fn):
        """
        Run a query with one automatic reconnect attempt when the server drops connections.
        """
        conn = None
        try:
            conn = self._borrow_connection()
            return query_fn(conn)
        except (OperationalError, InterfaceError):
            if conn:
                self._safe_putconn(conn, close=True)
            self._reset_pool()
            conn = self._borrow_connection()
            return query_fn(conn)
        finally:
            if conn:
                self._safe_putconn(conn)

    def execute(self, query: str, params: Optional[Sequence[Any]] = None) -> None:
        def _run(conn):
            with conn.cursor() as cur:
                cur.execute(query, params)
                conn.commit()

        self._with_reconnect(_run)

    def fetch_one(
        self, query: str, params: Optional[Sequence[Any]] = None
    ) -> Optional[Tuple[Any, ...]]:
        def _run(conn):
            with conn.cursor() as cur:
                cur.execute(query, params)
                return cur.fetchone()

        return self._with_reconnect(_run)

    def fetch_all(
        self, query: str, params: Optional[Sequence[Any]] = None
    ) -> Iterable[Tuple[Any, ...]]:
        def _run(conn):
            with conn.cursor() as cur:
                cur.execute(query, params)
                return cur.fetchall()

        return self._with_reconnect(_run)


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
