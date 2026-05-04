from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from sqlalchemy import select
from database.engine import async_session
from database.models import Ad, AdPhoto, Category
from services.s3_client import get_public_url

router = Router()

@router.message(Command("search"))
async def start_search(message: Message):
    async with async_session() as session:
        cats = (await session.execute(select(Category).where(Category.parent_id == None))).scalars().all()
        kb = InlineKeyboardMarkup(inline_keyboard=[])
        for cat in cats:
            kb.inline_keyboard.append([InlineKeyboardButton(text=cat.name, callback_data=f"searchcat_{cat.id}_0")])
        await message.answer("Выберите категорию для поиска:", reply_markup=kb)

@router.callback_query(F.data.startswith("searchcat_"))
async def search_in_category(call: CallbackQuery):
    parts = call.data.split("_")
    cat_id = int(parts[1])
    page = int(parts[2]) if len(parts) > 2 else 0
    async with async_session() as session:
        ads = (await session.execute(select(Ad).where(Ad.category_id == cat_id, Ad.status == "active").order_by(Ad.created_at.desc()).limit(3).offset(page * 3))).scalars().all()
    if not ads:
        await call.message.answer("Объявлений не найдено.")
        await call.answer()
        return
    for ad in ads:
        async with async_session() as session:
            photo = (await session.execute(select(AdPhoto).where(AdPhoto.ad_id == ad.id).order_by(AdPhoto.order).limit(1))).scalar_one_or_none()
        text = f"{ad.title}\nЦена: {ad.price}\nГород: {ad.city}"
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Подробнее", callback_data=f"view_{ad.id}")]])
        if photo:
            try:
                photo_url = get_public_url(photo.file_path)
                await call.message.answer_photo(photo=photo_url, caption=text, reply_markup=kb)
            except:
                await call.message.answer(text, reply_markup=kb)
        else:
            await call.message.answer(text, reply_markup=kb)
    next_kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Далее", callback_data=f"searchcat_{cat_id}_{page+1}")]])
    await call.message.answer("Следующая страница:", reply_markup=next_kb)
    await call.answer()
