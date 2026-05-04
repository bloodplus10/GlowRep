from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, User
from sqlalchemy import select
from database.engine import async_session
from database.models import User as DBUser

class BanMiddleware(BaseMiddleware):
    async def __call__(self, handler, event: TelegramObject, data: dict):
        user: User = data.get("event_from_user")
        if user:
            async with async_session() as session:
                result = await session.execute(select(DBUser).where(DBUser.telegram_id == user.id))
                db_user = result.scalar_one_or_none()
                if db_user and db_user.is_banned:
                    return
        return await handler(event, data)
