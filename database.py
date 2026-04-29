import aiosqlite

DB_NAME = "finguard_data.db"


async def init_db():
    """Создает таблицы пользователей и транзакций"""
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                balance INTEGER NOT NULL,
                days INTEGER NOT NULL,
                reserve INTEGER NOT NULL,
                goal INTEGER DEFAULT 0,
                fixed_limit REAL DEFAULT 0,
                daily_pool REAL DEFAULT 0,
                last_sync DATE DEFAULT CURRENT_DATE
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                amount INTEGER NOT NULL,
                description TEXT,
                category TEXT DEFAULT 'Прочее',
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        await db.execute('''
            CREATE TABLE IF NOT EXISTS subscriptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                amount INTEGER NOT NULL,
                description TEXT
            )
        ''')

        await db.execute('''
            CREATE TABLE IF NOT EXISTS wishlist (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                amount INTEGER NOT NULL,
                item_name TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Миграция: добавляем колонки по одной с константными значениями
        async with db.execute("PRAGMA table_info(users)") as cursor:
            columns = [row[1] for row in await cursor.fetchall()]
            if 'daily_pool' not in columns:
                await db.execute("ALTER TABLE users ADD COLUMN daily_pool REAL DEFAULT 0.0")
            if 'last_sync' not in columns:
                # SQLite не дает добавить CURRENT_DATE через ALTER TABLE, используем заглушку
                await db.execute("ALTER TABLE users ADD COLUMN last_sync DATE DEFAULT '2000-01-01'")
        
        async with db.execute("PRAGMA table_info(transactions)") as cursor:
            columns = [row[1] for row in await cursor.fetchall()]
            if 'category' not in columns:
                await db.execute("ALTER TABLE transactions ADD COLUMN category TEXT DEFAULT 'Прочее'")
        
        await db.commit()


async def log_transaction(user_id: int, amount: int, description: str, category: str = "Прочее"):
    """Логирует покупку с категорией"""
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            'INSERT INTO transactions (user_id, amount, description, category) VALUES (?, ?, ?, ?)',
            (user_id, amount, description, category)
        )
        await db.commit()


async def get_category_stats(user_id: int):
    """Возвращает агрегированную статистику по категориям (без учета регистра)"""
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute('''
            SELECT LOWER(category), SUM(amount), COUNT(id)
            FROM transactions
            WHERE user_id = ?
            GROUP BY LOWER(category)
            ORDER BY SUM(amount) DESC
        ''', (user_id,)) as cursor:
            return await cursor.fetchall()


async def get_history(user_id: int, limit: int = 5):
    """Возвращает историю последних трат"""
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute(
            'SELECT amount, description, timestamp FROM transactions WHERE user_id = ? ORDER BY timestamp DESC LIMIT ?',
            (user_id, limit)
        ) as cursor:
            return await cursor.fetchall()


async def save_user(
    user_id: int,
    balance: int,
    days: int,
    reserve: int,
    goal: int = 0,
    fixed_limit: float = 0,
    daily_pool: float = 0
):
    """
    Сохраняет или обновляет пользователя (Upsert)
    """
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute('''
            INSERT INTO users (user_id, balance, days, reserve, goal, fixed_limit, daily_pool, last_sync)
            VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_DATE)
            ON CONFLICT(user_id) DO UPDATE SET
                balance = excluded.balance,
                days = excluded.days,
                reserve = excluded.reserve,
                goal = excluded.goal,
                fixed_limit = excluded.fixed_limit,
                daily_pool = excluded.daily_pool,
                last_sync = excluded.last_sync
        ''', (user_id, balance, days, reserve, goal, fixed_limit, daily_pool))
        await db.commit()


async def get_user(user_id: int):
    """
    Получает данные пользователя
    """
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute('''
            SELECT balance, days, reserve, goal, fixed_limit, daily_pool, last_sync
            FROM users 
            WHERE user_id = ?
        ''', (user_id,)) as cursor:

            row = await cursor.fetchone()

            if row:
                return {
                    "balance": row[0],
                    "days": row[1],
                    "reserve": row[2],
                    "goal": row[3],
                    "fixed_limit": row[4],
                    "daily_pool": row[5],
                    "last_sync": row[6]
                }

            return None


async def update_daily_pool(user_id: int, new_pool: float):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            'UPDATE users SET daily_pool = ?, last_sync = CURRENT_DATE WHERE user_id = ?',
            (new_pool, user_id)
        )
        await db.commit()


async def update_balance(user_id: int, new_balance: int):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            'UPDATE users SET balance = ? WHERE user_id = ?',
            (new_balance, user_id)
        )
        await db.commit()


async def update_goal(user_id: int, new_goal: int):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            'UPDATE users SET goal = ? WHERE user_id = ?',
            (new_goal, user_id)
        )
        await db.commit()


async def get_all_users():
    """Возвращает список ID всех пользователей"""
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute('SELECT user_id FROM users') as cursor:
            rows = await cursor.fetchall()
            return [row[0] for row in rows]


async def pop_last_transaction(user_id: int):
    """
    Находит последнюю транзакцию пользователя, удаляет её и возвращает сумму.
    """
    async with aiosqlite.connect(DB_NAME) as db:
        # 1. Находим последнюю транзакцию
        async with db.execute(
            'SELECT id, amount, description FROM transactions WHERE user_id = ? ORDER BY timestamp DESC LIMIT 1',
            (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if not row:
                return None
            
            t_id, amount, desc = row
            
            # 2. Удаляем её
            await db.execute('DELETE FROM transactions WHERE id = ?', (t_id,))
            await db.commit()
            
            return {"amount": amount, "description": desc}


async def add_wish(user_id: int, amount: int, item_name: str):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            'INSERT INTO wishlist (user_id, amount, item_name) VALUES (?, ?, ?)',
            (user_id, amount, item_name)
        )
        await db.commit()


async def get_wishlist(user_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute(
            'SELECT id, amount, item_name, timestamp FROM wishlist WHERE user_id = ?',
            (user_id,)
        ) as cursor:
            return await cursor.fetchall()


async def delete_wish(wish_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute('DELETE FROM wishlist WHERE id = ?', (wish_id,))
        await db.commit()


async def delete_user_data(user_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        # Удаляем основные данные пользователя
        await db.execute('DELETE FROM users WHERE user_id = ?', (user_id,))
        # Удаляем все его подписки
        await db.execute('DELETE FROM subscriptions WHERE user_id = ?', (user_id,))
        # Удаляем всю историю его транзакций (чтобы график очистился)
        await db.execute('DELETE FROM transactions WHERE user_id = ?', (user_id,))
        # Удаляем список желаний
        await db.execute('DELETE FROM wishlist WHERE user_id = ?', (user_id,))
        
        await db.commit()


async def add_subscription(user_id: int, amount: int, description: str):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            'INSERT INTO subscriptions (user_id, amount, description) VALUES (?, ?, ?)',
            (user_id, amount, description)
        )
        await db.commit()


async def get_subscriptions(user_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute(
            'SELECT id, amount, description FROM subscriptions WHERE user_id = ?',
            (user_id,)
        ) as cursor:
            return await cursor.fetchall()


async def delete_subscription(sub_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute('DELETE FROM subscriptions WHERE id = ?', (sub_id,))
        await db.commit()


async def get_total_subscriptions(user_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute(
            'SELECT SUM(amount) FROM subscriptions WHERE user_id = ?',
            (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return row[0] if row[0] else 0