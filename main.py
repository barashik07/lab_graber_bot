import logging
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram_sqlite_storage.sqlitestore import SQLStorage
from aiogram.client.default import DefaultBotProperties

from settings import settings
from handlers import common, student, admin
from middlewares.api_client import APIClientMiddleware
from middlewares.db import DBSessionMiddleware
from models.base import init_db

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

logger.info("Initializing bot and dispatcher")
storage = SQLStorage(settings.db_path)
bot = Bot(
    token=settings.bot_token,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML),
)
dp = Dispatcher(storage=storage)

logger.info("Including routers")
dp.include_router(common.router)
dp.include_router(student.router)
dp.include_router(admin.router)

logger.info("Setting up middlewares")
dp.update.middleware(APIClientMiddleware())
dp.update.middleware(DBSessionMiddleware())

if __name__ == "__main__":
    import asyncio

    logger.info("Starting bot")
    asyncio.run(init_db())
    logger.info("Database initialized, starting polling")
    dp.run_polling(bot)