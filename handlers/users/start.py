from aiogram import Router, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, Contact
from aiogram.filters import Command
from sqlalchemy import select
from database.engine import async_session
from database.models import User

router = Router()

def main_menu():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="/new"), KeyboardButton(text="/search")],
        [KeyboardButton(text="/profile"), KeyboardButton(text="/favorites")]
    ], resize_keyboard=True)

@router.message(Command("start"))
async def cmd_start(message: Message):
    async with async_session() as session:
        user = await session.execute(select(User).where(User.telegram_id == message.from_user.id))
        user = user.scalar_one_or_none()
        if not user:
            kb = ReplyKeyboardMarkup(keyboard=[
                [KeyboardButton(text="Send contact", request_contact=True)]
            ], resize_keyboard=True)
            await message.answer("Welcome to GLOWREP! Send contact to register.", reply_markup=kb)
        else:
            await message.answer("Welcome back!", reply_markup=main_menu())

@router.message(F.contact)
async def contact_handler(message: Message):
    contact: Contact = message.contact
    async with async_session() as session:
        user = User(telegram_id=message.from_user.id, username=message.from_user.username, phone=contact.phone_number)
        session.add(user)
        await session.commit()
    await message.answer("Registered!", reply_markup=main_menu())