from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, WebAppInfo

from config import settings

router = Router()

def main_menu(user_id: int):
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Open Catalog", web_app=WebAppInfo(url=f"{settings.WEBAPP_URL}?user_id={user_id}"))],
            [KeyboardButton(text="/new"), KeyboardButton(text="/search")],
            [KeyboardButton(text="/profile"), KeyboardButton(text="/favorites")],
        ],
        resize_keyboard=True,
    )

@router.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer(
        "GLOWREP online ✨ Жми Open Catalog",
        reply_markup=main_menu(message.from_user.id)
    )
