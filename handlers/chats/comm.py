from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from sqlalchemy import select
from database.engine import async_session
from database.models import Ad, Chat, Message as DBMessage, User
import uuid

router = Router()

@router.callback_query(F.data.startswith("msg_"))
async def start_chat(call: CallbackQuery, state: FSMContext):
    ad_id = call.data.split("_")[1]
    async with async_session() as session:
        buyer = await session.execute(select(User).where(User.telegram_id == call.from_user.id))
        buyer = buyer.scalar_one_or_none()
        if not buyer:
            await call.answer("????????????????? ????? /start")
            return
        ad = await session.get(Ad, ad_id)
        if not ad:
            await call.answer("?????????? ?? ???????")
            return
        if buyer.id == ad.user_id:
            await call.answer("?????? ???????? ?????? ????")
            return
        existing = await session.execute(select(Chat).where(Chat.ad_id == ad.id, Chat.buyer_id == buyer.id))
        chat = existing.scalar_one_or_none()
        if not chat:
            chat = Chat(id=uuid.uuid4(), ad_id=ad.id, buyer_id=buyer.id, seller_id=ad.user_id)
            session.add(chat)
            await session.commit()
        chat_id = chat.id
    await state.update_data(current_chat_id=str(chat_id))
    await call.message.answer("???????? ???? ????????? ????????. ??? ???????? ??? ????????.")
    await call.answer()

@router.message(F.text, F.chat.type == "private", ~F.text.startswith("/"))
async def buyer_message(message: Message, state: FSMContext, bot):
    data = await state.get_data()
    chat_id = data.get("current_chat_id")
    if not chat_id:
        return
    async with async_session() as session:
        chat = await session.get(Chat, chat_id)
        if not chat:
            await message.answer("?????? ?? ??????.")
            return
        buyer = await session.execute(select(User).where(User.telegram_id == message.from_user.id))
        buyer = buyer.scalar_one()
        msg_obj = DBMessage(chat_id=chat_id, sender_id=buyer.id, text=message.text)
        session.add(msg_obj)
        await session.commit()
        seller = await session.get(User, chat.seller_id)
        if seller:
            ad = await session.get(Ad, chat.ad_id)
            sent = await bot.send_message(seller.telegram_id, f"?? ?????????? ?? ?????????? ?{ad.title}?:\n{message.text}")
            try:
                await state.storage.redis.set(f"reply_msg_{sent.message_id}", str(chat_id))
            except:
                pass
    await message.answer("????????? ?????????? ????????.")

@router.message(F.reply_to_message, F.chat.type == "private")
async def seller_reply(message: Message, bot, state: FSMContext):
    if not message.reply_to_message.from_user.id == bot.id:
        return
    try:
        chat_id_bytes = await state.storage.redis.get(f"reply_msg_{message.reply_to_message.message_id}")
        if not chat_id_bytes:
            return
        chat_id = chat_id_bytes.decode()
    except:
        return
    async with async_session() as session:
        chat = await session.get(Chat, chat_id)
        if not chat:
            await message.answer("?????? ?? ??????.")
            return
        seller = await session.execute(select(User).where(User.telegram_id == message.from_user.id))
        seller = seller.scalar_one_or_none()
        if not seller or seller.id != chat.seller_id:
            await message.answer("?? ?? ???????? ? ???? ???????.")
            return
        buyer = await session.get(User, chat.buyer_id)
        if buyer:
            await bot.send_message(buyer.telegram_id, f"?? ????????:\n{message.text}")
        msg_obj = DBMessage(chat_id=chat_id, sender_id=seller.id, text=message.text)
        session.add(msg_obj)
        await session.commit()
    await message.answer("????? ????????? ??????????.")
