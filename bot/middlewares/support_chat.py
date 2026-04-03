import logging
from typing import Any, Awaitable, Callable, Dict
from aiogram import BaseMiddleware
from aiogram.types import Message, TelegramObject, Update
from database.engine import async_session_maker
from database.models import SupportChat
from sqlalchemy import select, and_
from bot.states import SupportStates

logger = logging.getLogger(__name__)

class SupportChatMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        # Resolve message from update if needed
        message = None
        if isinstance(event, Message):
            message = event
        elif isinstance(event, Update) and event.message:
            message = event.message
            
        if not message or not message.text:
            return await handler(event, data)
            
        # Ignore commands and main menu/exit buttons
        if message.text.startswith("/") or message.text == "❌ Завершить диалог" or message.text == "📩 Обратная связь":
            return await handler(event, data)
            
        user_tid = message.from_user.id
        
        async with async_session_maker() as session:
            chat = (await session.execute(
                select(SupportChat).where(
                    and_(
                        SupportChat.is_active == True,
                        (SupportChat.user_tid == user_tid) | (SupportChat.admin_tid == user_tid)
                    )
                )
            )).scalar_one_or_none()
            
            if chat:
                state = data.get("state")
                if state:
                    current_state = await state.get_state()
                    if current_state != SupportStates.active_chat:
                        logger.info(f"SupportChatMiddleware: Forcing active_chat state for user {user_tid}")
                        await state.set_state(SupportStates.active_chat)
                        data["raw_state"] = await state.get_state()
                
        return await handler(event, data)
