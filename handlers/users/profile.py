from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy import select, func
from database.engine import async_session
from database.models import User, Ad
from keyboards.inline import get_profile_kb

router = Router()

class ProfileStates(StatesGroup):
    waiting_city = State()

@router.message(Command("profile"))
async def profile(message: Message):
    async with async_session() as session:
        result = await session.execute(select(User).where(User.telegram_id == message.from_user.id))
        user = result.scalar_one_or_none()
        if not user:
            await message.answer("Вы не зарегистрированы. Нажмите /start")
            return
        cnt = await session.execute(select(func.count(Ad.id)).where(Ad.user_id == user.id, Ad.status == "active"))
        ads_count = cnt.scalar()
        text = f"Профиль GLOWREP\n\nTelegram ID: {user.telegram_id}\nТелефон: {user.phone}\nГород: {user.city or 'не указан'}\nАктивных объявлений: {ads_count}"
        await message.answer(text, reply_markup=get_profile_kb())

@router.callback_query(F.data == "change_city")
async def change_city_start(call: CallbackQuery, state: FSMContext):
    await call.message.answer("Введите ваш город:")
    await state.set_state(ProfileStates.waiting_city)
    await call.answer()

@router.message(ProfileStates.waiting_city)
async def process_city(message: Message, state: FSMContext):
    city = message.text.strip()
    async with async_session() as session:
        user = await session.execute(select(User).where(User.telegram_id == message.from_user.id))
        user = user.scalar_one()
        user.city = city
        await session.commit()
    await message.answer(f"Город обновлён: {city}")
    await state.clear()
