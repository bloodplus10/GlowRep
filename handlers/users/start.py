from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, WebAppInfo

from config import settings

router = Router()

def main_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Open Catalog", web_app=WebAppInfo(url=settings.WEBAPP_URL))],
            [KeyboardButton(text="/new"), KeyboardButton(text="/search")],
            [KeyboardButton(text="/profile"), KeyboardButton(text="/favorites")],
        ],
        resize_keyboard=True,
    )

@router.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer("GLOWREP online ✅ Жми Open Catalog", reply_markup=main_menu())
