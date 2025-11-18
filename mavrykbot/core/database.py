"""Simple PostgreSQL helper built on top of psycopg2."""
from __future__ import annotations

import psycopg2
from psycopg2 import pool
from contextlib import contextmanager
from typing import Any, Iterable, Optional

from mavrykbot.core.config import load_database_config


class Database:
    """Lazy connection pool used by the bot handlers."""

    def __init__(self) -> None:
        cfg = load_database_config()
        self._pool = pool.SimpleConnectionPool(
            minconn=1,
            maxconn=5,
            host=cfg.host,
            port=cfg.port,
            database=cfg.name,
            user=cfg.user,
            password=cfg.password,
        )

    @contextmanager
    def _get_connection(self):
        # Lấy kết nối từ pool
        conn = self._pool.getconn()
        try:
            yield conn
            conn.commit()
        except:
            conn.rollback()
            raise
        finally:
            # Trả lại kết nối vào pool
            self._pool.putconn(conn)

    def execute(self, query: str, params: Optional[Iterable[Any]] = None) -> None:
        with self._get_connection() as conn, conn.cursor() as cursor:
            cursor.execute(query, params or ())

    def fetch_one(
        self, query: str, params: Optional[Iterable[Any]] = None
    ) -> Optional[tuple[Any, ...]]:
        with self._get_connection() as conn, conn.cursor() as cursor:
            cursor.execute(query, params or ())
            return cursor.fetchone()

    def fetch_all(
        self, query: str, params: Optional[Iterable[Any]] = None
    ) -> list[tuple[Any, ...]]:
        with self._get_connection() as conn, conn.cursor() as cursor:
            cursor.execute(query, params or ())
            return cursor.fetchall()


# Shared instance that bot handlers can import
db = Database()