from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

def location_keyboard():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="📍 Отправить местоположение", request_location=True)],
        [KeyboardButton(text="Ввести город вручную")]
    ], resize_keyboard=True)