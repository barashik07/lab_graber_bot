import logging
import aiohttp
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from typing import Any, Dict, Callable, Awaitable

from services.api import APIClient

logger = logging.getLogger(__name__)

class APIClientMiddleware(BaseMiddleware):
    """Middleware для внедрения API клиента"""
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        logger.debug("Creating API client session")
        async with aiohttp.ClientSession() as session:
            data["api"] = APIClient(session)
            return await handler(event, data)