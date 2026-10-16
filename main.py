import asyncio
import logging
from datetime import datetime, timezone
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from bot.core.config import config
import sentry_sdk

# --- SENTRY INITIALIZATION FOR BOT ---
if config.SENTRY_DSN:
    sentry_sdk.init(
        dsn=config.SENTRY_DSN,
        traces_sample_rate=0.1,
        send_default_pii=False,
        environment="production",
    )

# Routers
from bot.handlers.registration import router as registration_router
from bot.handlers.start import router as start_router
from bot.handlers.admin import router as admin_router
from bot.handlers.master_account import router as master_account_router
from bot.handlers.client_order import router as client_order_router
from bot.handlers.client_cabinet import router as client_cabinet_router
from bot.handlers.support import router as support_router
from bot.handlers.payments import router as payments_router
from bot.handlers.faq import router as faq_router
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

async def order_expiry_worker(bot: Bot):
    """Closes NEW orders nobody was chosen for within ORDER_TTL_HOURS, refunds bid fees, notifies everyone."""
    from bot.services.orders import expire_stale_orders
    while True:
        try:
            if config.ORDER_TTL_HOURS > 0:
                async with async_session_maker() as session:
                    expired = await expire_stale_orders(session, config.ORDER_TTL_HOURS)
                    await session.commit()
                for item in expired:
                    logger.info(f"Order #{item.order_id} expired and was closed automatically.")
                    try:
                        await bot.send_message(
                            item.client_telegram_id,
                            f"⌛ <b>Заявка №{item.order_id} закрыта автоматически.</b>\n"
                            f"Вы не выбрали мастера в течение {config.ORDER_TTL_HOURS} ч. "
                            "Если задача всё ещё актуальна — создайте новую заявку.",
                            parse_mode="HTML",
                        )
                    except Exception as e:
                        logger.warning(f"Could not notify client {item.client_telegram_id}: {e}")
                    for n in item.notices:
                        refund = f"\n💰 <b>{n.refunded} баллов возвращены на ваш баланс.</b>" if n.refunded else ""
                        try:
                            await bot.send_message(
                                n.master_telegram_id,
                                f"⌛ Заявка №{item.order_id} закрыта: срок ожидания истёк.{refund}",
                                parse_mode="HTML",
                            )
                        except Exception as e:
                            logger.warning(f"Could not notify master {n.master_telegram_id}: {e}")
        except Exception:
            logger.exception("Error in order_expiry_worker")
        await asyncio.sleep(30 * 60)  # every 30 minutes

async def order_reminder_worker(bot: Bot):
    """Asks clients whether to re-notify masters about orders without bids and sends the reminders (working hours only)."""
    from bot.services.reminders import run_reminder_cycle
    while True:
        try:
            await run_reminder_cycle(bot, async_session_maker)
        except Exception:
            logger.exception("Error in order_reminder_worker")
        await asyncio.sleep(60)

async def build_storage():
    """FSM storage: Redis when available (state survives restarts), otherwise in-memory with a warning."""
    try:
        from redis.asyncio import Redis
        from aiogram.fsm.storage.redis import RedisStorage
        redis = Redis.from_url(config.REDIS_URL)
        await redis.ping()
        logger.info("FSM storage: Redis")
        return RedisStorage(redis)
    except Exception as e:
        logger.warning(f"Redis is unavailable ({e}); falling back to MemoryStorage — user dialogs will be lost on restart.")
        return MemoryStorage()

async def main():
    if not config.BOT_TOKEN or config.BOT_TOKEN == "123456789:YOUR_BOT_TOKEN_HERE":
        logger.error("BOT_TOKEN is not set in .env file.")
        return

    # Initialize bot and dispatcher
    bot = Bot(token=config.BOT_TOKEN)
    dp = Dispatcher(storage=await build_storage())
    
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
    dp.include_router(payments_router)
    dp.include_router(faq_router)
    dp.include_router(start_router)

    # Start background tasks
    background_tasks = [  # keep references so tasks are not garbage-collected
        asyncio.create_task(unban_worker(bot)),
        asyncio.create_task(order_expiry_worker(bot)),
        asyncio.create_task(order_reminder_worker(bot)),
    ]

    # Start polling
    logger.info("Starting UstaGo bot...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Bot stopped!")
