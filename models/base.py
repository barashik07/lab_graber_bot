import aiosqlite
import logging
from settings import settings

logger = logging.getLogger(__name__)

async def init_db() -> None:
    """Инициализация базы данных"""
    logger.info("Initializing database")
    async with aiosqlite.connect(settings.db_path) as db:
        await db.execute("PRAGMA journal_mode=WAL;")
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS students (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER UNIQUE,
                surname TEXT,
                name TEXT,
                patronymic TEXT,
                group_code TEXT,
                github TEXT,
                courses TEXT DEFAULT '[]', 
                created_at TEXT,
                updated_at TEXT,
                UNIQUE(surname, name, group_code, github)
            )
            """
        )
        await db.commit()
        logger.info("Database initialized successfully")