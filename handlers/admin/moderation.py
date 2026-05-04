from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from sqlalchemy import select
from database.engine import async_session
from database.models import User, Ad, Complaint
from keyboards.inline import moderation_keyboard, complaints_keyboard

router = Router()

def is_moderator(user: User) -> bool:
    return user.role in ("moderator", "admin")

@router.message(Command("moderate"))
async def moderate(message: Message):
    async with async_session() as session:
        user = await session.execute(select(User).where(User.telegram_id == message.from_user.id))
        user = user.scalar_one_or_none()
        if not user or not is_moderator(user):
            await message.answer("No access.")
            return
        ads = (await session.execute(select(Ad).where(Ad.status == "moderation").order_by(Ad.created_at.desc()))).scalars().all()
        if not ads:
            await message.answer("No ads for moderation.")
            return
        for ad in ads:
            text = f"Ad: {ad.title}\nDescription: {ad.description}\nPrice: {ad.price}\nCity: {ad.city}"
            await message.answer(text, reply_markup=moderation_keyboard(ad.id))

@router.callback_query(F.data.startswith("approve_"))
async def approve_ad(call: CallbackQuery):
    ad_id = call.data.split("_")[1]
    async with async_session() as session:
        ad = await session.get(Ad, ad_id)
        ad.status = "active"
        await session.commit()
        author = await session.get(User, ad.user_id)
        if author:
            await call.bot.send_message(author.telegram_id, f"Ad '{ad.title}' approved!")
    await call.message.edit_reply_markup(reply_markup=None)
    await call.answer("Approved")

@router.callback_query(F.data.startswith("reject_"))
async def reject_ad(call: CallbackQuery, state: FSMContext):
    ad_id = call.data.split("_")[1]
    await state.update_data(reject_ad_id=ad_id)
    await call.message.answer("Enter rejection reason:")
    await state.set_state("moderation_reject_reason")
    await call.answer()

@router.message(Command("complaints"))
async def view_complaints(message: Message):
    async with async_session() as session:
        user = await session.execute(select(User).where(User.telegram_id == message.from_user.id))
        user = user.scalar_one_or_none()
        if not user or not is_moderator(user):
            await message.answer("No access.")
            return
        complaints = (await session.execute(select(Complaint).where(Complaint.status == "open").order_by(Complaint.created_at.desc()))).scalars().all()
        if not complaints:
            await message.answer("No complaints.")
            return
        for comp in complaints:
            ad = await session.get(Ad, comp.ad_id)
            complainant = await session.get(User, comp.complainant_id)
            text = f"Complaint on '{ad.title}' from {complainant.telegram_id}\nReason: {comp.reason}"
            await message.answer(text, reply_markup=complaints_keyboard(ad.id, comp.id))

@router.callback_query(F.data.startswith("ban_"))
async def ban_author(call: CallbackQuery):
    ad_id = call.data.split("_")[1]
    async with async_session() as session:
        ad = await session.get(Ad, ad_id)
        author = await session.get(User, ad.user_id)
        author.is_banned = True
        ad.status = "rejected"
        await session.commit()
        await call.bot.send_message(author.telegram_id, "Your account has been banned.")
    await call.message.edit_reply_markup(reply_markup=None)
    await call.answer("Author banned")

@router.callback_query(F.data.startswith("delete_"))
async def delete_ad(call: CallbackQuery):
    ad_id = call.data.split("_")[1]
    async with async_session() as session:
        ad = await session.get(Ad, ad_id)
        await session.delete(ad)
        await session.commit()
    await call.message.edit_reply_markup(reply_markup=None)
    await call.answer("Ad deleted")

@router.callback_query(F.data.startswith("resolve_"))
async def resolve_complaint(call: CallbackQuery):
    complaint_id = call.data.split("_")[1]
    async with async_session() as session:
        comp = await session.get(Complaint, complaint_id)
        comp.status = "resolved"
        await session.commit()
    await call.message.edit_reply_markup(reply_markup=None)
    await call.answer("Complaint resolved")