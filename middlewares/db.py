import logging
import aiosqlite
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from typing import Callable, Awaitable, Any, Dict

from settings import settings
from services.student import StudentRepository

logger = logging.getLogger(__name__)

class DBSessionMiddleware(BaseMiddleware):
    """Middleware для внедрения подключения к БД и репозитория"""
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        logger.debug("Creating database connection")
        async with aiosqlite.connect(settings.db_path) as db:
            db.row_factory = aiosqlite.Row
            data["db"] = db
            data["students_repo"] = StudentRepository(db)
            return await handler(event, data)