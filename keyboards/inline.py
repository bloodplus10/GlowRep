from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def categories_keyboard(parent_id=None):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👕 Одежда", callback_data="cat_1")],
        [InlineKeyboardButton(text="👟 Обувь", callback_data="cat_2")],
        [InlineKeyboardButton(text="👜 Аксессуары", callback_data="cat_3")],
        [InlineKeyboardButton(text="💎 Украшения", callback_data="cat_4")]
    ])

def photo_continue_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить ещё", callback_data="add_more")],
        [InlineKeyboardButton(text="✅ Готово", callback_data="upload_done")]
    ])

def confirm_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Опубликовать", callback_data="publish")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_ad")]
    ])

def get_profile_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏙 Изменить город", callback_data="change_city")]
    ])

def ad_detail_keyboard(ad_id, fav=False):
    fav_text = "💔 Убрать из избранного" if fav else "❤️ В избранное"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💬 Написать продавцу", callback_data=f"msg_{ad_id}")],
        [InlineKeyboardButton(text=fav_text, callback_data=f"fav_{ad_id}")],
        [InlineKeyboardButton(text="⚠️ Пожаловаться", callback_data=f"complaint_{ad_id}")]
    ])

def moderation_keyboard(ad_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Одобрить", callback_data=f"approve_{ad_id}")],
        [InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_{ad_id}")]
    ])

def complaints_keyboard(ad_id, complaint_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚫 Забанить автора", callback_data=f"ban_{ad_id}")],
        [InlineKeyboardButton(text="🗑 Удалить объявление", callback_data=f"delete_{ad_id}")],
        [InlineKeyboardButton(text="✅ Закрыть жалобу", callback_data=f"resolve_{complaint_id}")]
    ])
