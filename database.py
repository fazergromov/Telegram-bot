import aiosqlite
from typing import Optional, List, Dict, Any
import logging
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)


class Database:
    """Класс для работы с базой данных aiosqlite."""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._connection: Optional[aiosqlite.Connection] = None
    
    async def connect(self) -> None:
        """Устанавливает соединение с БД."""
        self._connection = await aiosqlite.connect(self.db_path)
        await self._create_tables()
        logger.info(f"Подключено к базе данных: {self.db_path}")
    
    async def close(self) -> None:
        """Закрывает соединение с БД."""
        if self._connection:
            await self._connection.close()
            logger.info("Соединение с базой данных закрыто")
    
    @asynccontextmanager
    async def get_cursor(self):
        """Контекстный менеджер для получения курсора."""
        if not self._connection:
            await self.connect()
        cursor = await self._connection.cursor()
        try:
            yield cursor
        finally:
            await cursor.close()
    
    async def _create_tables(self) -> None:
        """Создает таблицы в базе данных."""
        async with self.get_cursor() as cursor:
            # Таблица пользователей
            await cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    balance INTEGER DEFAULT 0,
                    referral_count INTEGER DEFAULT 0,
                    referred_by INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (referred_by) REFERENCES users(user_id)
                )
            """)
            
            # Добавляем колонку is_subscribed если она не существует
            try:
                await cursor.execute("ALTER TABLE users ADD COLUMN is_subscribed BOOLEAN DEFAULT FALSE")
            except Exception:
                # Колонка уже существует
                pass
            
            # Таблица промокодов (с сайта игры)
            await cursor.execute("""
                CREATE TABLE IF NOT EXISTS promocodes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    code TEXT UNIQUE NOT NULL,
                    description TEXT,
                    source_url TEXT,
                    usage_limit INTEGER DEFAULT NULL,
                    activation_count TEXT DEFAULT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_sent BOOLEAN DEFAULT FALSE
                )
            """)
            
            # Таблица промокодов бота (с наградой голдов)
            await cursor.execute("""
                CREATE TABLE IF NOT EXISTS bot_promocodes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    code TEXT UNIQUE NOT NULL,
                    gold_reward INTEGER NOT NULL,
                    usage_limit INTEGER DEFAULT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_active BOOLEAN DEFAULT TRUE
                )
            """)
            
            # Таблица использованных промокодов бота
            await cursor.execute("""
                CREATE TABLE IF NOT EXISTS bot_promo_usage (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    promo_id INTEGER NOT NULL,
                    used_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(user_id),
                    FOREIGN KEY (promo_id) REFERENCES bot_promocodes(id),
                    UNIQUE(user_id, promo_id)
                )
            """)
            
            # Таблица заявок на вывод
            await cursor.execute("""
                CREATE TABLE IF NOT EXISTS withdrawal_requests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    amount INTEGER NOT NULL,
                    wallet_address TEXT,
                    status TEXT DEFAULT 'pending',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(user_id)
                )
            """)
            
            # Таблица рассылок
            await cursor.execute("""
                CREATE TABLE IF NOT EXISTS broadcasts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    message TEXT NOT NULL,
                    sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    recipients_count INTEGER DEFAULT 0
                )
            """)
            
            # Таблица ежедневных бонусов
            await cursor.execute("""
                CREATE TABLE IF NOT EXISTS daily_bonuses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    bonus_date DATE NOT NULL,
                    amount INTEGER NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(user_id),
                    UNIQUE(user_id, bonus_date)
                )
            """)
            
            await self._connection.commit()
            logger.info("Таблицы базы данных созданы/проверены")
    
    # ========== Методы для работы с пользователями ==========
    
    async def add_user(self, user_id: int, username: str = None, referred_by: int = None) -> bool:
        """Добавляет нового пользователя."""
        async with self.get_cursor() as cursor:
            try:
                await cursor.execute(
                    "INSERT OR IGNORE INTO users (user_id, username, referred_by) VALUES (?, ?, ?)",
                    (user_id, username, referred_by)
                )
                await self._connection.commit()
                
                # Если пользователь был добавлен (не проигнорирован), обновляем счетчик рефералов
                if referred_by:
                    await cursor.execute(
                        "UPDATE users SET referral_count = referral_count + 1 WHERE user_id = ?",
                        (referred_by,)
                    )
                    await self._connection.commit()
                
                return True
            except Exception as e:
                logger.error(f"Ошибка при добавлении пользователя: {e}")
                return False
    
    async def get_user(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Получает информацию о пользователе."""
        async with self.get_cursor() as cursor:
            await cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
            row = await cursor.fetchone()
            if row:
                columns = [desc[0] for desc in cursor.description]
                return dict(zip(columns, row))
            return None
    
    async def update_balance(self, user_id: int, amount: int) -> bool:
        """Обновляет баланс пользователя."""
        async with self.get_cursor() as cursor:
            try:
                await cursor.execute(
                    "UPDATE users SET balance = balance + ? WHERE user_id = ?",
                    (amount, user_id)
                )
                await self._connection.commit()
                return True
            except Exception as e:
                logger.error(f"Ошибка при обновлении баланса: {e}")
                return False
    
    async def get_all_users(self) -> List[Dict[str, Any]]:
        """Получает список всех пользователей."""
        async with self.get_cursor() as cursor:
            await cursor.execute("SELECT * FROM users")
            rows = await cursor.fetchall()
            columns = [desc[0] for desc in cursor.description]
            return [dict(zip(columns, row)) for row in rows]
    
    async def set_user_subscribed(self, user_id: int, subscribed: bool = True) -> bool:
        """Устанавливает статус подписки пользователя."""
        async with self.get_cursor() as cursor:
            try:
                await cursor.execute(
                    "UPDATE users SET is_subscribed = ? WHERE user_id = ?",
                    (subscribed, user_id)
                )
                await self._connection.commit()
                return True
            except Exception as e:
                logger.error(f"Ошибка при обновлении статуса подписки: {e}")
                return False
    
    async def is_user_subscribed(self, user_id: int) -> bool:
        """Проверяет, подписан ли пользователь на канал."""
        async with self.get_cursor() as cursor:
            await cursor.execute("SELECT is_subscribed FROM users WHERE user_id = ?", (user_id,))
            row = await cursor.fetchone()
            if row:
                return bool(row[0])
            return False
    
    # ========== Методы для работы с промокодами ==========
    
    async def add_promocode(self, code: str, description: str = None, source_url: str = None, usage_limit: int = None, activation_count: str = None) -> bool:
        """Добавляет новый промокод."""
        async with self.get_cursor() as cursor:
            try:
                await cursor.execute(
                    "INSERT OR IGNORE INTO promocodes (code, description, source_url, usage_limit, activation_count) VALUES (?, ?, ?, ?, ?)",
                    (code, description, source_url, usage_limit, activation_count)
                )
                await self._connection.commit()
                return True
            except Exception as e:
                logger.error(f"Ошибка при добавлении промокода: {e}")
                return False
    
    async def update_promocode_activation_count(self, code: str, activation_count: str) -> bool:
        """Обновляет количество активаций для существующего промокода."""
        async with self.get_cursor() as cursor:
            try:
                await cursor.execute(
                    "UPDATE promocodes SET activation_count = ? WHERE code = ?",
                    (activation_count, code)
                )
                await self._connection.commit()
                return True
            except Exception as e:
                logger.error(f"Ошибка при обновлении количества активаций: {e}")
                return False
    
    async def get_unsent_promocodes(self) -> List[Dict[str, Any]]:
        """Получает список неотправленных промокодов."""
        async with self.get_cursor() as cursor:
            await cursor.execute("SELECT * FROM promocodes WHERE is_sent = FALSE")
            rows = await cursor.fetchall()
            columns = [desc[0] for desc in cursor.description]
            return [dict(zip(columns, row)) for row in rows]
    
    async def mark_promocode_sent(self, promocode_id: int) -> bool:
        """Отмечает промокод как отправленный."""
        async with self.get_cursor() as cursor:
            try:
                await cursor.execute(
                    "UPDATE promocodes SET is_sent = TRUE WHERE id = ?",
                    (promocode_id,)
                )
                await self._connection.commit()
                return True
            except Exception as e:
                logger.error(f"Ошибка при отметке промокода: {e}")
                return False
    
    async def get_all_promocodes(self) -> List[Dict[str, Any]]:
        """Получает список всех промокодов с сайта."""
        async with self.get_cursor() as cursor:
            await cursor.execute("SELECT * FROM promocodes ORDER BY created_at DESC")
            rows = await cursor.fetchall()
            columns = [desc[0] for desc in cursor.description]
            return [dict(zip(columns, row)) for row in rows]
    
    # ========== Методы для работы с промокодами бота ==========
    
    async def add_bot_promocode(self, code: str, gold_reward: int, usage_limit: int = None) -> bool:
        """Добавляет новый промокод бота."""
        async with self.get_cursor() as cursor:
            try:
                await cursor.execute(
                    "INSERT OR IGNORE INTO bot_promocodes (code, gold_reward, usage_limit) VALUES (?, ?, ?)",
                    (code, gold_reward, usage_limit)
                )
                await self._connection.commit()
                return True
            except Exception as e:
                logger.error(f"Ошибка при добавлении промокода бота: {e}")
                return False
    
    async def get_bot_promocode(self, code: str) -> Dict[str, Any] | None:
        """Получает промокод бота по коду."""
        async with self.get_cursor() as cursor:
            await cursor.execute("SELECT * FROM bot_promocodes WHERE code = ? AND is_active = TRUE", (code,))
            row = await cursor.fetchone()
            if row:
                columns = [desc[0] for desc in cursor.description]
                return dict(zip(columns, row))
            return None
    
    async def get_all_bot_promocodes(self) -> List[Dict[str, Any]]:
        """Получает список всех промокодов бота."""
        async with self.get_cursor() as cursor:
            await cursor.execute("SELECT * FROM bot_promocodes ORDER BY created_at DESC")
            rows = await cursor.fetchall()
            columns = [desc[0] for desc in cursor.description]
            return [dict(zip(columns, row)) for row in rows]
    
    async def has_user_used_promo(self, user_id: int, promo_id: int) -> bool:
        """Проверяет, использовал ли пользователь промокод."""
        async with self.get_cursor() as cursor:
            await cursor.execute(
                "SELECT * FROM bot_promo_usage WHERE user_id = ? AND promo_id = ?",
                (user_id, promo_id)
            )
            row = await cursor.fetchone()
            return row is not None
    
    async def use_bot_promocode(self, user_id: int, promo_id: int) -> bool:
        """Отмечает использование промокода пользователем."""
        async with self.get_cursor() as cursor:
            try:
                await cursor.execute(
                    "INSERT OR IGNORE INTO bot_promo_usage (user_id, promo_id) VALUES (?, ?)",
                    (user_id, promo_id)
                )
                await self._connection.commit()
                return True
            except Exception as e:
                logger.error(f"Ошибка при отметке использования промокода: {e}")
                return False
    
    async def get_promo_usage_count(self, promo_id: int) -> int:
        """Получает количество использований промокода."""
        async with self.get_cursor() as cursor:
            await cursor.execute(
                "SELECT COUNT(*) FROM bot_promo_usage WHERE promo_id = ?",
                (promo_id,)
            )
            row = await cursor.fetchone()
            return row[0] if row else 0
    
    # ========== Методы для работы с заявками на вывод ==========
    
    async def create_withdrawal_request(self, user_id: int, amount: int, wallet_address: str = None) -> bool:
        """Создает заявку на вывод."""
        async with self.get_cursor() as cursor:
            try:
                await cursor.execute(
                    "INSERT INTO withdrawal_requests (user_id, amount, wallet_address) VALUES (?, ?, ?)",
                    (user_id, amount, wallet_address)
                )
                await self._connection.commit()
                return True
            except Exception as e:
                logger.error(f"Ошибка при создании заявки на вывод: {e}")
                return False
    
    async def get_pending_withdrawals(self) -> List[Dict[str, Any]]:
        """Получает список ожидающих заявок на вывод."""
        async with self.get_cursor() as cursor:
            await cursor.execute("SELECT * FROM withdrawal_requests WHERE status = 'pending'")
            rows = await cursor.fetchall()
            columns = [desc[0] for desc in cursor.description]
            return [dict(zip(columns, row)) for row in rows]
    
    async def update_withdrawal_status(self, request_id: int, status: str) -> bool:
        """Обновляет статус заявки на вывод."""
        async with self.get_cursor() as cursor:
            try:
                await cursor.execute(
                    "UPDATE withdrawal_requests SET status = ? WHERE id = ?",
                    (status, request_id)
                )
                await self._connection.commit()
                return True
            except Exception as e:
                logger.error(f"Ошибка при обновлении статуса заявки: {e}")
                return False
    
    # ========== Методы для работы с ежедневными бонусами ==========
    
    async def can_get_daily_bonus(self, user_id: int) -> bool:
        """Проверяет, может ли пользователь получить ежедневный бонус сегодня."""
        from datetime import date
        today = date.today()
        
        async with self.get_cursor() as cursor:
            await cursor.execute(
                "SELECT id FROM daily_bonuses WHERE user_id = ? AND bonus_date = ?",
                (user_id, today)
            )
            result = await cursor.fetchone()
            return result is None
    
    async def record_daily_bonus(self, user_id: int, amount: int = 200) -> bool:
        """Записывает получение ежедневного бонуса."""
        from datetime import date
        today = date.today()
        
        async with self.get_cursor() as cursor:
            try:
                await cursor.execute(
                    "INSERT INTO daily_bonuses (user_id, bonus_date, amount) VALUES (?, ?, ?)",
                    (user_id, today, amount)
                )
                await self._connection.commit()
                return True
            except Exception as e:
                logger.error(f"Ошибка при записи ежедневного бонуса: {e}")
                return False
