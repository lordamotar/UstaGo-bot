from typing import Any, Awaitable, Callable, Dict
from aiogram import BaseMiddleware
from aiogram.types import Message, TelegramObject, CallbackQuery
from database.engine import async_session_maker
from database.models import User
from sqlalchemy import select
from datetime import datetime, timezone

class BanCheckMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        user_id = None
        if isinstance(event, Message):
            user_id = event.from_user.id
        elif isinstance(event, CallbackQuery):
            user_id = event.from_user.id

        if user_id:
            async with async_session_maker() as session:
                user = (await session.execute(select(User).where(User.telegram_id == user_id))).scalar_one_or_none()
                if user and user.banned_until:
                    now = datetime.now(timezone.utc).replace(tzinfo=None)
                    if user.banned_until > now:
                        ban_text = f"🚫 <b>Ваш аккаунт заблокирован.</b>\nДо: {user.banned_until.strftime('%d.%m.%Y %H:%M')}\n\nПожалуйста, дождитесь окончания срока бана."
                        if isinstance(event, Message):
                            await event.answer(ban_text, parse_mode="HTML")
                        elif isinstance(event, CallbackQuery):
                            await event.answer(ban_text, show_alert=True)
                        return # Stop propagation
        
        return await handler(event, data)
