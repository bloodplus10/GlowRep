import logging
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

class LoggingMiddleware(BaseMiddleware):
    async def __call__(self, handler, event: TelegramObject, data: dict):
        logging.info(f"Update: {event}")
        return await handler(event, data)
