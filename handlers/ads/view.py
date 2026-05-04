from aiogram import Router, F
from aiogram.types import CallbackQuery
from sqlalchemy import select
from database.engine import async_session
from database.models import Ad, AdPhoto, Favorite, User, Complaint
from keyboards.inline import ad_detail_keyboard

router = Router()

@router.callback_query(F.data.startswith("view_"))
async def view_ad(call: CallbackQuery):
    ad_id = call.data.split("_")[1]
    async with async_session() as session:
        ad = await session.get(Ad, ad_id)
        if not ad:
            await call.answer("Ad not found")
            return
        user = await session.execute(select(User).where(User.telegram_id == call.from_user.id))
        user = user.scalar_one_or_none()
        fav = False
        if user:
            fav_result = await session.execute(select(Favorite).where(Favorite.user_id == user.id, Favorite.ad_id == ad.id))
            fav = fav_result.scalar_one_or_none() is not None
        photos_count = (await session.execute(select(AdPhoto).where(AdPhoto.ad_id == ad.id))).scalars().all()
        text = f"{ad.title}\n\n{ad.description}\n\nPrice: {ad.price}\nCity: {ad.city}\nDate: {ad.created_at.strftime('%d.%m.%Y')}\nPhotos: {len(photos_count)} pcs."
        await call.message.answer(text, reply_markup=ad_detail_keyboard(ad.id, fav))
    await call.answer()

@router.callback_query(F.data.startswith("complaint_"))
async def make_complaint(call: CallbackQuery):
    ad_id = call.data.split("_")[1]
    async with async_session() as session:
        user = await session.execute(select(User).where(User.telegram_id == call.from_user.id))
        user = user.scalar_one_or_none()
        if not user:
            await call.answer("Register first.")
            return
        complaint = Complaint(ad_id=ad_id, complainant_id=user.id, reason="User complaint")
        session.add(complaint)
        await session.commit()
    await call.answer("Complaint sent. Thank you!")