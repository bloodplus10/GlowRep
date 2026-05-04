from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from sqlalchemy import select
from database.engine import async_session
from database.models import Favorite, Ad, User

router = Router()

@router.callback_query(F.data.startswith("fav_"))
async def toggle_favorite(call: CallbackQuery):
    ad_id = call.data.split("_")[1]
    async with async_session() as session:
        user = await session.execute(select(User).where(User.telegram_id == call.from_user.id))
        user = user.scalar_one()
        fav = await session.execute(select(Favorite).where(Favorite.user_id == user.id, Favorite.ad_id == ad_id))
        existing = fav.scalar_one_or_none()
        if existing:
            await session.delete(existing)
            await session.commit()
            await call.answer("Удалено из избранного")
        else:
            session.add(Favorite(user_id=user.id, ad_id=ad_id))
            await session.commit()
            await call.answer("Добавлено в избранное")
    try:
        await call.message.edit_reply_markup(reply_markup=call.message.reply_markup)
    except:
        pass

@router.message(Command("favorites"))
async def list_favorites(message: Message):
    async with async_session() as session:
        user = await session.execute(select(User).where(User.telegram_id == message.from_user.id))
        user = user.scalar_one_or_none()
        if not user:
            await message.answer("Вы не зарегистрированы.")
            return
        favs = await session.execute(select(Ad).join(Favorite).where(Favorite.user_id == user.id))
        ads = favs.scalars().all()
        if not ads:
            await message.answer("Избранное пусто.")
            return
        for ad in ads:
            kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Подробнее", callback_data=f"view_{ad.id}")]])
            await message.answer(f"{ad.title}\nЦена: {ad.price}", reply_markup=kb)
