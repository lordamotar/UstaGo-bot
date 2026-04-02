import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from bot.core.config import config
from bot.handlers.registration import router as registration_router
from bot.handlers.start import router as start_router
from bot.handlers.admin import router as admin_router
from bot.handlers.master_account import router as master_account_router
from bot.handlers.client_order import router as client_order_router
from bot.handlers.client_cabinet import router as client_cabinet_router

from bot.middlewares.logging import LoggingMiddleware

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def main():
    if not config.BOT_TOKEN or config.BOT_TOKEN == "123456789:YOUR_BOT_TOKEN_HERE":
        logger.error("BOT_TOKEN is not set in .env file.")
        return

    # Initialize bot and dispatcher
    bot = Bot(token=config.BOT_TOKEN)
    
    # Using MemoryStorage for MVP instead of Redis for ease of local testing.
    # We can easily swap to RedisStorage(redis=Redis.from_url(config.REDIS_URL)) later
    dp = Dispatcher(storage=MemoryStorage())
    
    # Register middlewares
    dp.update.outer_middleware(LoggingMiddleware())

    # Include routers
    dp.include_router(admin_router)
    dp.include_router(master_account_router)
    dp.include_router(client_order_router)
    dp.include_router(client_cabinet_router)
    dp.include_router(registration_router)
    dp.include_router(start_router)

    # Start polling
    logger.info("Starting UstaGo bot...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Bot stopped!")
