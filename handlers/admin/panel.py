from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command
from sqlalchemy import select, func
from database.engine import async_session
from database.models import User, Ad
from config import settings

router = Router()

@router.message(Command("admin"))
async def admin_panel(message: Message):
    async with async_session() as session:
        total_users = (await session.execute(select(func.count(User.id)))).scalar()
        total_ads = (await session.execute(select(func.count(Ad.id)))).scalar()
        active_ads = (await session.execute(select(func.count(Ad.id)).where(Ad.status == "active"))).scalar()
        text = (
            f"GLOWREP — Админ-панель\n\n"
            f"Пользователей: {total_users}\n"
            f"Всего объявлений: {total_ads}\n"
            f"Активных: {active_ads}\n\n"
            f"Команды:\n"
            f"/promote ID — назначить модератора\n"
            f"/demote ID — разжаловать"
        )
        await message.answer(text)

@router.message(Command("promote"))
async def promote(message: Message):
    try:
        tid = int(message.text.split()[1])
    except:
        await message.answer("Использование: /promote telegram_id")
        return
    async with async_session() as session:
        user = await session.execute(select(User).where(User.telegram_id == tid))
        user = user.scalar_one()
        user.role = "moderator"
        await session.commit()
        await message.answer(f"Пользователь {tid} назначен модератором.")

@router.message(Command("demote"))
async def demote(message: Message):
    try:
        tid = int(message.text.split()[1])
    except:
        await message.answer("Использование: /demote telegram_id")
        return
    async with async_session() as session:
        user = await session.execute(select(User).where(User.telegram_id == tid))
        user = user.scalar_one()
        user.role = "user"
        await session.commit()
        await message.answer(f"Пользователь {tid} разжалован.")