import asyncio
import logging
from datetime import datetime, timezone
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from bot.core.config import config

# Routers
from bot.handlers.registration import router as registration_router
from bot.handlers.start import router as start_router
from bot.handlers.admin import router as admin_router
from bot.handlers.master_account import router as master_account_router
from bot.handlers.client_order import router as client_order_router
from bot.handlers.client_cabinet import router as client_cabinet_router
from bot.handlers.support import router as support_router

# Middlewares
from bot.middlewares.logging import LoggingMiddleware
from bot.middlewares.ban_check import BanCheckMiddleware
from bot.middlewares.support_chat import SupportChatMiddleware

# Database for worker
from database.engine import async_session_maker
from database.models import User
from sqlalchemy import select

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def unban_worker(bot: Bot):
    """Background task to notify users when their ban expires."""
    while True:
        try:
            async with async_session_maker() as session:
                now = datetime.now(timezone.utc).replace(tzinfo=None)
                # Find users who were banned but the period is OVER, and we haven't cleared banned_until yet
                stmt = select(User).where(User.banned_until <= now)
                res = await session.execute(stmt)
                users_to_unban = res.scalars().all()
                
                for user in users_to_unban:
                    try:
                        user.banned_until = None
                        await bot.send_message(
                            user.telegram_id,
                            "⚡️ <b>Ограничения с вашего аккаунта сняты.</b>\nПожалуйста, соблюдайте правила сервиса в будущем!",
                            parse_mode="HTML"
                        )
                        logger.info(f"User {user.telegram_id} was automatically unbanned.")
                    except Exception as e:
                        logger.error(f"Failed to notify unbanned user {user.telegram_id}: {e}")
                
                await session.commit()
        except Exception as e:
            logger.error(f"Error in unban_worker: {e}")
            
        await asyncio.sleep(600) # Check every 10 minutes

async def main():
    if not config.BOT_TOKEN or config.BOT_TOKEN == "123456789:YOUR_BOT_TOKEN_HERE":
        logger.error("BOT_TOKEN is not set in .env file.")
        return

    # Initialize bot and dispatcher
    bot = Bot(token=config.BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())
    
    # Register middlewares
    dp.update.outer_middleware(LoggingMiddleware())
    dp.update.outer_middleware(BanCheckMiddleware())
    dp.update.outer_middleware(SupportChatMiddleware())

    # Include routers
    dp.include_router(admin_router)
    dp.include_router(master_account_router)
    dp.include_router(client_order_router)
    dp.include_router(client_cabinet_router)
    dp.include_router(registration_router)
    dp.include_router(support_router)
    dp.include_router(start_router)

    # Start background tasks
    asyncio.create_task(unban_worker(bot))

    # Start polling
    logger.info("Starting UstaGo bot...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Bot stopped!")
