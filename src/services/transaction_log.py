from pathlib import Path
import sqlite3
from threading import Lock
from typing import Dict, List


class TransactionLog:
    """Thread-safe SQLite-backed transaction store for persistent metrics/logging."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS transactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp_utc TEXT NOT NULL DEFAULT (datetime('now')),
                    amount REAL NOT NULL,
                    distance REAL NOT NULL,
                    time_delta REAL NOT NULL,
                    is_fraudulent INTEGER NOT NULL,
                    risk_level TEXT NOT NULL,
                    risk_score REAL NOT NULL
                );
                """
            )
            conn.commit()

    def add(self, record: Dict) -> None:
        with self._lock:
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO transactions (
                        amount, distance, time_delta, is_fraudulent, risk_level, risk_score
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        float(record["amount"]),
                        float(record["distance"]),
                        float(record["time_delta"]),
                        int(bool(record["is_fraudulent"])),
                        str(record["risk_level"]),
                        float(record["risk_score"]),
                    ),
                )
                conn.commit()

    def recent(self, limit: int = 50) -> List[Dict]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT timestamp_utc, amount, distance, time_delta, is_fraudulent, risk_level, risk_score
                FROM transactions
                ORDER BY id DESC
                LIMIT ?
                """,
                (int(limit),),
            ).fetchall()

        return [
            {
                "timestamp_utc": row["timestamp_utc"],
                "amount": row["amount"],
                "distance": row["distance"],
                "time_delta": row["time_delta"],
                "is_fraudulent": bool(row["is_fraudulent"]),
                "risk_level": row["risk_level"],
                "risk_score": row["risk_score"],
            }
            for row in rows
        ]

    def metrics(self) -> Dict:
        with self._connect() as conn:
            total_row = conn.execute("SELECT COUNT(*) AS c FROM transactions").fetchone()
            fraud_row = conn.execute(
                "SELECT COUNT(*) AS c FROM transactions WHERE is_fraudulent = 1"
            ).fetchone()

        total = int(total_row["c"]) if total_row else 0
        fraud = int(fraud_row["c"]) if fraud_row else 0
        ratio = (fraud / total) if total > 0 else 0.0
        return {
            "total_transactions_logged": total,
            "fraud_transactions_logged": fraud,
            "fraud_ratio": round(ratio, 4),
            "storage": "sqlite",
            "db_path": str(self.db_path),
        }
