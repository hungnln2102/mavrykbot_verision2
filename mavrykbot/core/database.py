import psycopg2
import psycopg2.pool
import json
import os

class Database:
    def __init__(self):
        self._pool = psycopg2.pool.SimpleConnectionPool(
            minconn=1,
            maxconn=5,
            host=os.getenv("DB_HOST"),
            port=os.getenv("DB_PORT"),
            dbname=os.getenv("DB_NAME"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD"),
        )

    def execute(self, query, params=None):
        conn = self._pool.getconn()
        try:
            with conn.cursor() as cur:
                cur.execute(query, params)
                conn.commit()
        finally:
            self._pool.putconn(conn)

    def fetch_one(self, query, params=None):
        conn = self._pool.getconn()
        try:
            with conn.cursor() as cur:
                cur.execute(query, params)
                return cur.fetchone()
        finally:
            self._pool.putconn(conn)

    def fetch_all(self, query, params=None):
        conn = self._pool.getconn()
        try:
            with conn.cursor() as cur:
                cur.execute(query, params)
                return cur.fetchall()
        finally:
            self._pool.putconn(conn)

db = Database()

# -----------------------------
# Payment insert function
# -----------------------------
def insert_payment_receipt(data: dict):
    """
    Saves a Sepay webhook payment into database.
    """

    query = """
        INSERT INTO payment_receipts
            (transaction_id, amount, event_type, event_time, raw_data)
        VALUES
            (%s, %s, %s, %s, %s)
        ON CONFLICT (transaction_id) DO NOTHING;
    """

    transaction_id = data.get("transaction_id")
    amount = data.get("amount")
    event_type = data.get("type") or data.get("event_type")
    event_time = data.get("timestamp") or data.get("created_at")

    raw_json = json.dumps(data, ensure_ascii=False)

    db.execute(
        query,
        (
            transaction_id,
            amount,
            event_type,
            event_time,
            raw_json,
        ),
    )
