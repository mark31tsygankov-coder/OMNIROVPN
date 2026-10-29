import aiosqlite
import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from contextlib import asynccontextmanager

from config import config

logger = logging.getLogger(__name__)


class Database:
    def __init__(self, db_path: str = None):
        self.db_path = db_path or config.DATABASE_PATH

    @asynccontextmanager
    async def connection(self):
        conn = await aiosqlite.connect(self.db_path)
        conn.row_factory = aiosqlite.Row
        try:
            yield conn
            await conn.commit()
        except Exception:
            await conn.rollback()
            raise
        finally:
            await conn.close()

    async def init(self):
        async with self.connection() as conn:
            await conn.executescript("""
                CREATE TABLE IF NOT EXISTS users (
                    telegram_id INTEGER PRIMARY KEY,
                    username TEXT,
                    full_name TEXT,
                    balance REAL DEFAULT 0.0,
                    is_blocked INTEGER DEFAULT 0,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS tariffs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    duration_days INTEGER NOT NULL,
                    price REAL NOT NULL,
                    description TEXT DEFAULT '',
                    is_active INTEGER DEFAULT 1,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS subscriptions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    tariff_id INTEGER,
                    tariff_name TEXT,
                    start_date TEXT,
                    end_date TEXT,
                    is_active INTEGER DEFAULT 1,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(telegram_id),
                    FOREIGN KEY (tariff_id) REFERENCES tariffs(id)
                );

                CREATE TABLE IF NOT EXISTS orders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    tariff_id INTEGER,
                    amount REAL NOT NULL,
                    status TEXT DEFAULT 'pending',
                    promo_code TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    paid_at TEXT,
                    FOREIGN KEY (user_id) REFERENCES users(telegram_id),
                    FOREIGN KEY (tariff_id) REFERENCES tariffs(id)
                );

                CREATE TABLE IF NOT EXISTS connections (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    subscription_id INTEGER,
                    status TEXT DEFAULT 'active',
                    config_data TEXT,
                    expires_at TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(telegram_id),
                    FOREIGN KEY (subscription_id) REFERENCES subscriptions(id)
                );

                CREATE TABLE IF NOT EXISTS tickets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    subject TEXT,
                    status TEXT DEFAULT 'open',
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    closed_at TEXT,
                    FOREIGN KEY (user_id) REFERENCES users(telegram_id)
                );

                CREATE TABLE IF NOT EXISTS ticket_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticket_id INTEGER NOT NULL,
                    sender_id INTEGER NOT NULL,
                    is_admin INTEGER DEFAULT 0,
                    message TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (ticket_id) REFERENCES tickets(id)
                );

                CREATE TABLE IF NOT EXISTS promo_codes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    code TEXT UNIQUE NOT NULL,
                    discount_type TEXT NOT NULL,
                    discount_value REAL NOT NULL,
                    max_uses INTEGER DEFAULT 0,
                    used_count INTEGER DEFAULT 0,
                    expires_at TEXT,
                    is_active INTEGER DEFAULT 1,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS promo_uses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    promo_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    used_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (promo_id) REFERENCES promo_codes(id),
                    FOREIGN KEY (user_id) REFERENCES users(telegram_id)
                );

                CREATE TABLE IF NOT EXISTS balance_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    amount REAL NOT NULL,
                    reason TEXT,
                    admin_id INTEGER,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(telegram_id)
                );

                CREATE TABLE IF NOT EXISTS broadcasts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    admin_id INTEGER NOT NULL,
                    message_text TEXT NOT NULL,
                    total INTEGER DEFAULT 0,
                    success INTEGER DEFAULT 0,
                    failed INTEGER DEFAULT 0,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT
                );
            """)

            # Safe migration for existing databases.
            cursor = await conn.execute("PRAGMA table_info(orders)")
            order_columns = {row[1] for row in await cursor.fetchall()}
            if "provider_payment_id" not in order_columns:
                await conn.execute("ALTER TABLE orders ADD COLUMN provider_payment_id TEXT")

            # Seed default tariffs if empty
            cursor = await conn.execute("SELECT COUNT(*) as cnt FROM tariffs")
            row = await cursor.fetchone()
            if row["cnt"] == 0:
                await conn.executemany(
                    "INSERT INTO tariffs (name, duration_days, price, description, is_active) VALUES (?, ?, ?, ?, ?)",
                    [
                        ("1 месяц", 30, 50.0, "Базовый тариф на 1 месяц", 1),
                        ("3 месяца", 90, 150.0, "Тариф на 3 месяца", 1),
                        ("6 месяцев", 180, 250.0, "Тариф на 6 месяцев", 1),
                        ("12 месяцев", 365, 500.0, "Тариф на 12 месяцев", 1),
                    ],
                )
                logger.info("Default tariffs seeded")

    # ─── Users ───────────────────────────────────────────────

    async def get_or_create_user(self, telegram_id: int, username: str = None, full_name: str = None) -> Dict:
        async with self.connection() as conn:
            cursor = await conn.execute(
                "SELECT * FROM users WHERE telegram_id = ?", (telegram_id,)
            )
            row = await cursor.fetchone()
            if row:
                # Update username/name if changed
                await conn.execute(
                    "UPDATE users SET username = ?, full_name = ? WHERE telegram_id = ?",
                    (username, full_name, telegram_id),
                )
                cursor = await conn.execute(
                    "SELECT * FROM users WHERE telegram_id = ?", (telegram_id,)
                )
                row = await cursor.fetchone()
                return dict(row)

            await conn.execute(
                "INSERT INTO users (telegram_id, username, full_name) VALUES (?, ?, ?)",
                (telegram_id, username, full_name),
            )
            cursor = await conn.execute(
                "SELECT * FROM users WHERE telegram_id = ?", (telegram_id,)
            )
            row = await cursor.fetchone()
            return dict(row)

    async def get_user(self, telegram_id: int) -> Optional[Dict]:
        async with self.connection() as conn:
            cursor = await conn.execute(
                "SELECT * FROM users WHERE telegram_id = ?", (telegram_id,)
            )
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def update_balance(self, telegram_id: int, amount: float, reason: str = "", admin_id: int = None):
        async with self.connection() as conn:
            await conn.execute(
                "UPDATE users SET balance = balance + ? WHERE telegram_id = ?",
                (amount, telegram_id),
            )
            await conn.execute(
                "INSERT INTO balance_history (user_id, amount, reason, admin_id) VALUES (?, ?, ?, ?)",
                (telegram_id, amount, reason, admin_id),
            )

    async def set_balance(self, telegram_id: int, balance: float):
        async with self.connection() as conn:
            await conn.execute(
                "UPDATE users SET balance = ? WHERE telegram_id = ?",
                (balance, telegram_id),
            )

    async def block_user(self, telegram_id: int, blocked: bool = True):
        async with self.connection() as conn:
            await conn.execute(
                "UPDATE users SET is_blocked = ? WHERE telegram_id = ?",
                (1 if blocked else 0, telegram_id),
            )

    async def get_all_users(self) -> List[Dict]:
        async with self.connection() as conn:
            cursor = await conn.execute("SELECT * FROM users ORDER BY created_at DESC")
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

    async def get_users_count(self) -> int:
        async with self.connection() as conn:
            cursor = await conn.execute("SELECT COUNT(*) as cnt FROM users")
            row = await cursor.fetchone()
            return row["cnt"]

    # ─── Tariffs ─────────────────────────────────────────────

    async def get_active_tariffs(self) -> List[Dict]:
        async with self.connection() as conn:
            cursor = await conn.execute(
                "SELECT * FROM tariffs WHERE is_active = 1 ORDER BY duration_days"
            )
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

    async def get_all_tariffs(self) -> List[Dict]:
        async with self.connection() as conn:
            cursor = await conn.execute("SELECT * FROM tariffs ORDER BY duration_days")
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

    async def get_tariff(self, tariff_id: int) -> Optional[Dict]:
        async with self.connection() as conn:
            cursor = await conn.execute("SELECT * FROM tariffs WHERE id = ?", (tariff_id,))
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def create_tariff(self, name: str, duration_days: int, price: float, description: str = "") -> int:
        async with self.connection() as conn:
            cursor = await conn.execute(
                "INSERT INTO tariffs (name, duration_days, price, description) VALUES (?, ?, ?, ?)",
                (name, duration_days, price, description),
            )
            return cursor.lastrowid

    async def update_tariff(self, tariff_id: int, **kwargs):
        allowed = {"name", "duration_days", "price", "description", "is_active"}
        fields = {k: v for k, v in kwargs.items() if k in allowed}
        if not fields:
            return
        sets = ", ".join(f"{k} = ?" for k in fields)
        values = list(fields.values()) + [tariff_id]
        async with self.connection() as conn:
            await conn.execute(f"UPDATE tariffs SET {sets} WHERE id = ?", values)

    async def delete_tariff(self, tariff_id: int):
        async with self.connection() as conn:
            await conn.execute("DELETE FROM tariffs WHERE id = ?", (tariff_id,))

    # ─── Subscriptions ───────────────────────────────────────

    async def get_active_subscription(self, user_id: int) -> Optional[Dict]:
        async with self.connection() as conn:
            cursor = await conn.execute(
                """SELECT * FROM subscriptions
                   WHERE user_id = ? AND is_active = 1 AND end_date > datetime('now')
                   ORDER BY end_date DESC LIMIT 1""",
                (user_id,),
            )
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def get_subscription(self, user_id: int) -> Optional[Dict]:
        """Get latest subscription (active or not)"""
        async with self.connection() as conn:
            cursor = await conn.execute(
                """SELECT * FROM subscriptions
                   WHERE user_id = ?
                   ORDER BY end_date DESC LIMIT 1""",
                (user_id,),
            )
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def activate_subscription(self, user_id: int, tariff: Dict, extend: bool = False) -> Dict:
        async with self.connection() as conn:
            now = datetime.utcnow()
            duration = timedelta(days=tariff["duration_days"])

            if extend:
                cursor = await conn.execute(
                    """SELECT * FROM subscriptions
                       WHERE user_id = ? AND is_active = 1
                       ORDER BY end_date DESC LIMIT 1""",
                    (user_id,),
                )
                existing = await cursor.fetchone()
                if existing and existing["end_date"]:
                    try:
                        end = datetime.fromisoformat(existing["end_date"])
                        if end > now:
                            start = end
                        else:
                            start = now
                    except ValueError:
                        start = now
                else:
                    start = now
            else:
                start = now
                # Deactivate previous
                await conn.execute(
                    "UPDATE subscriptions SET is_active = 0 WHERE user_id = ?",
                    (user_id,),
                )

            end_date = start + duration

            cursor = await conn.execute(
                """INSERT INTO subscriptions
                   (user_id, tariff_id, tariff_name, start_date, end_date, is_active)
                   VALUES (?, ?, ?, ?, ?, 1)""",
                (
                    user_id,
                    tariff["id"],
                    tariff["name"],
                    start.isoformat(),
                    end_date.isoformat(),
                ),
            )
            sub_id = cursor.lastrowid

            cursor = await conn.execute(
                "SELECT * FROM subscriptions WHERE id = ?", (sub_id,)
            )
            row = await cursor.fetchone()
            return dict(row)

    async def deactivate_subscription(self, user_id: int):
        async with self.connection() as conn:
            await conn.execute(
                "UPDATE subscriptions SET is_active = 0 WHERE user_id = ?",
                (user_id,),
            )

    async def get_active_subscriptions_count(self) -> int:
        async with self.connection() as conn:
            cursor = await conn.execute(
                """SELECT COUNT(*) as cnt FROM subscriptions
                   WHERE is_active = 1 AND end_date > datetime('now')"""
            )
            row = await cursor.fetchone()
            return row["cnt"]

    async def get_expired_subscriptions_count(self) -> int:
        async with self.connection() as conn:
            cursor = await conn.execute(
                """SELECT COUNT(*) as cnt FROM subscriptions
                   WHERE end_date <= datetime('now') OR is_active = 0"""
            )
            row = await cursor.fetchone()
            return row["cnt"]

    # ─── Orders ──────────────────────────────────────────────

    async def create_order(self, user_id: int, tariff_id: int, amount: float, promo_code: str = None) -> int:
        async with self.connection() as conn:
            cursor = await conn.execute(
                """INSERT INTO orders (user_id, tariff_id, amount, status, promo_code)
                   VALUES (?, ?, ?, 'pending', ?)""",
                (user_id, tariff_id, amount, promo_code),
            )
            return cursor.lastrowid

    async def get_order(self, order_id: int) -> Optional[Dict]:
        async with self.connection() as conn:
            cursor = await conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,))
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def complete_order(self, order_id: int) -> bool:
        # Atomic transition prevents repeated webhooks from activating the same order twice.
        async with self.connection() as conn:
            cursor = await conn.execute(
                "UPDATE orders SET status = 'paid', paid_at = datetime('now') WHERE id = ? AND status != 'paid'",
                (order_id,),
            )
            return cursor.rowcount == 1

    async def set_order_payment_id(self, order_id: int, payment_id: str):
        async with self.connection() as conn:
            await conn.execute("UPDATE orders SET provider_payment_id = ? WHERE id = ?", (payment_id, order_id))

    async def get_total_payments(self) -> float:
        async with self.connection() as conn:
            cursor = await conn.execute(
                "SELECT COALESCE(SUM(amount), 0) as total FROM orders WHERE status = 'paid'"
            )
            row = await cursor.fetchone()
            return row["total"]

    async def get_user_orders(self, user_id: int) -> List[Dict]:
        async with self.connection() as conn:
            cursor = await conn.execute(
                "SELECT * FROM orders WHERE user_id = ? ORDER BY created_at DESC",
                (user_id,),
            )
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

    # ─── Connections ─────────────────────────────────────────

    async def create_connection(self, user_id: int, subscription_id: int, expires_at: str, config_data: str = None) -> int:
        async with self.connection() as conn:
            cursor = await conn.execute(
                """INSERT INTO connections (user_id, subscription_id, status, config_data, expires_at)
                   VALUES (?, ?, 'active', ?, ?)""",
                (user_id, subscription_id, config_data or "TEST_CONFIG_PLACEHOLDER", expires_at),
            )
            return cursor.lastrowid

    async def get_user_connections(self, user_id: int) -> List[Dict]:
        async with self.connection() as conn:
            cursor = await conn.execute(
                """SELECT * FROM connections
                   WHERE user_id = ? AND status = 'active'
                   ORDER BY created_at DESC""",
                (user_id,),
            )
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

    async def get_connection(self, conn_id: int) -> Optional[Dict]:
        async with self.connection() as conn:
            cursor = await conn.execute("SELECT * FROM connections WHERE id = ?", (conn_id,))
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def deactivate_connection(self, conn_id: int):
        async with self.connection() as conn:
            await conn.execute(
                "UPDATE connections SET status = 'inactive' WHERE id = ?",
                (conn_id,),
            )

    # ─── Tickets ─────────────────────────────────────────────

    async def create_ticket(self, user_id: int, subject: str, message: str) -> int:
        async with self.connection() as conn:
            cursor = await conn.execute(
                "INSERT INTO tickets (user_id, subject, status) VALUES (?, ?, 'open')",
                (user_id, subject),
            )
            ticket_id = cursor.lastrowid
            await conn.execute(
                "INSERT INTO ticket_messages (ticket_id, sender_id, is_admin, message) VALUES (?, ?, 0, ?)",
                (ticket_id, user_id, message),
            )
            return ticket_id

    async def get_ticket(self, ticket_id: int) -> Optional[Dict]:
        async with self.connection() as conn:
            cursor = await conn.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,))
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def get_user_tickets(self, user_id: int) -> List[Dict]:
        async with self.connection() as conn:
            cursor = await conn.execute(
                "SELECT * FROM tickets WHERE user_id = ? ORDER BY created_at DESC",
                (user_id,),
            )
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

    async def get_open_tickets(self) -> List[Dict]:
        async with self.connection() as conn:
            cursor = await conn.execute(
                "SELECT * FROM tickets WHERE status = 'open' ORDER BY created_at DESC"
            )
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

    async def get_all_tickets(self) -> List[Dict]:
        async with self.connection() as conn:
            cursor = await conn.execute("SELECT * FROM tickets ORDER BY created_at DESC")
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

    async def add_ticket_message(self, ticket_id: int, sender_id: int, message: str, is_admin: bool = False):
        async with self.connection() as conn:
            await conn.execute(
                "INSERT INTO ticket_messages (ticket_id, sender_id, is_admin, message) VALUES (?, ?, ?, ?)",
                (ticket_id, sender_id, 1 if is_admin else 0, message),
            )
            if is_admin:
                await conn.execute(
                    "UPDATE tickets SET status = 'answered' WHERE id = ?",
                    (ticket_id,),
                )

    async def get_ticket_messages(self, ticket_id: int) -> List[Dict]:
        async with self.connection() as conn:
            cursor = await conn.execute(
                "SELECT * FROM ticket_messages WHERE ticket_id = ? ORDER BY created_at",
                (ticket_id,),
            )
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

    async def close_ticket(self, ticket_id: int):
        async with self.connection() as conn:
            await conn.execute(
                "UPDATE tickets SET status = 'closed', closed_at = datetime('now') WHERE id = ?",
                (ticket_id,),
            )

    async def delete_ticket(self, ticket_id: int):
        async with self.connection() as conn:
            await conn.execute("DELETE FROM ticket_messages WHERE ticket_id = ?", (ticket_id,))
            await conn.execute("DELETE FROM tickets WHERE id = ?", (ticket_id,))

    async def get_tickets_count(self) -> int:
        async with self.connection() as conn:
            cursor = await conn.execute("SELECT COUNT(*) as cnt FROM tickets")
            row = await cursor.fetchone()
            return row["cnt"]

    # ─── Promo codes ─────────────────────────────────────────

    async def create_promo(
        self,
        code: str,
        discount_type: str,
        discount_value: float,
        max_uses: int = 0,
        expires_at: str = None,
    ) -> int:
        async with self.connection() as conn:
            cursor = await conn.execute(
                """INSERT INTO promo_codes (code, discount_type, discount_value, max_uses, expires_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (code.upper(), discount_type, discount_value, max_uses, expires_at),
            )
            return cursor.lastrowid

    async def get_promo(self, code: str) -> Optional[Dict]:
        async with self.connection() as conn:
            cursor = await conn.execute(
                "SELECT * FROM promo_codes WHERE code = ? AND is_active = 1",
                (code.upper(),),
            )
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def get_all_promos(self) -> List[Dict]:
        async with self.connection() as conn:
            cursor = await conn.execute("SELECT * FROM promo_codes ORDER BY created_at DESC")
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

    async def use_promo(self, promo_id: int, user_id: int):
        async with self.connection() as conn:
            await conn.execute(
                "UPDATE promo_codes SET used_count = used_count + 1 WHERE id = ?",
                (promo_id,),
            )
            await conn.execute(
                "INSERT INTO promo_uses (promo_id, user_id) VALUES (?, ?)",
                (promo_id, user_id),
            )

    async def deactivate_promo(self, promo_id: int):
        async with self.connection() as conn:
            await conn.execute(
                "UPDATE promo_codes SET is_active = 0 WHERE id = ?",
                (promo_id,),
            )

    # ─── Broadcasts ──────────────────────────────────────────

    async def create_broadcast(self, admin_id: int, message_text: str) -> int:
        async with self.connection() as conn:
            cursor = await conn.execute(
                "INSERT INTO broadcasts (admin_id, message_text) VALUES (?, ?)",
                (admin_id, message_text),
            )
            return cursor.lastrowid

    async def update_broadcast_stats(self, broadcast_id: int, total: int, success: int, failed: int):
        async with self.connection() as conn:
            await conn.execute(
                "UPDATE broadcasts SET total = ?, success = ?, failed = ? WHERE id = ?",
                (total, success, failed, broadcast_id),
            )

    # ─── Stats ───────────────────────────────────────────────

    async def get_total_user_balance(self) -> float:
        async with self.connection() as conn:
            cursor = await conn.execute("SELECT COALESCE(SUM(balance), 0) as total FROM users")
            row = await cursor.fetchone()
            return row["total"]


db = Database()
