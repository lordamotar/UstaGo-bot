import logging
from typing import Any, Awaitable, Callable, Dict
from aiogram import BaseMiddleware
from aiogram.types import Update

logger = logging.getLogger(__name__)

class LoggingMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[Update, Dict[str, Any]], Awaitable[Any]],
        event: Update,
        data: Dict[str, Any]
    ) -> Any:
        logger.debug(f"Received update: {event.update_id}")
        if event.message:
            logger.info(f"Message from {event.message.from_user.id}: {event.message.text}")
        elif event.callback_query:
            logger.info(f"Callback query from {event.callback_query.from_user.id}: {event.callback_query.data}")
            
        result = await handler(event, data)
        return result
