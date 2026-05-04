from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy import select
from database.engine import async_session
from database.models import User, Ad, AdPhoto
from services.s3_client import upload_photo
from keyboards.inline import categories_keyboard, photo_continue_keyboard, confirm_keyboard
from keyboards.reply import location_keyboard
from utils.validators import is_valid_price, contains_url, contains_banned_words
from config import settings
import aiohttp

router = Router()

class CreateAdStates(StatesGroup):
    category = State()
    photos = State()
    title = State()
    description = State()
    price = State()
    location = State()
    waiting_city = State()
    confirm = State()

@router.message(F.text == "/new")
async def new_ad(message: Message, state: FSMContext):
    async with async_session() as session:
        user = await session.execute(select(User).where(User.telegram_id == message.from_user.id))
        if not user.scalar_one_or_none():
            await message.answer("Сначала зарегистрируйтесь через /start")
            return
    await message.answer("Выберите категорию:", reply_markup=categories_keyboard())
    await state.set_state(CreateAdStates.category)

@router.callback_query(CreateAdStates.category, F.data.startswith("cat_"))
async def category_chosen(call: CallbackQuery, state: FSMContext):
    cat_id = int(call.data.split("_")[1])
    await state.update_data(category_id=cat_id)
    await call.message.answer("Отправьте до 3 фото товара. Когда закончите, нажмите 'Готово'.")
    await state.set_state(CreateAdStates.photos)
    await call.answer()

@router.message(CreateAdStates.photos, F.photo)
async def photo_upload(message: Message, state: FSMContext):
    data = await state.get_data()
    photos = data.get("photos", [])
    if len(photos) >= 3:
        await message.answer("Максимум 3 фото. Нажмите 'Готово'.")
        return
    file_id = message.photo[-1].file_id
    photos.append(file_id)
    await state.update_data(photos=photos)
    await message.answer(f"Фото получено ({len(photos)}/3). Отправить ещё?", reply_markup=photo_continue_keyboard())

@router.callback_query(CreateAdStates.photos, F.data == "upload_done")
async def photos_done(call: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    if "photos" not in data or len(data["photos"]) < 1:
        await call.answer("Добавьте хотя бы одно фото!", show_alert=True)
        return
    await call.message.answer("Введите название товара (до 100 символов):")
    await state.set_state(CreateAdStates.title)
    await call.answer()

@router.callback_query(CreateAdStates.photos, F.data == "add_more")
async def add_more(call: CallbackQuery):
    await call.message.answer("Отправьте ещё фото.")
    await call.answer()

@router.message(CreateAdStates.title)
async def title_entered(message: Message, state: FSMContext):
    title = message.text.strip()
    if len(title) > 100:
        await message.answer("Слишком длинное название. Укоротите.")
        return
    await state.update_data(title=title)
    await message.answer("Введите описание (до 2000 символов):")
    await state.set_state(CreateAdStates.description)

@router.message(CreateAdStates.description)
async def description_entered(message: Message, state: FSMContext):
    desc = message.text.strip()
    if len(desc) > 2000:
        await message.answer("Описание слишком длинное. Укоротите.")
        return
    if contains_url(desc) or contains_banned_words(desc, settings.BANNED_WORDS):
        await message.answer("Объявление содержит запрещённый контент и отклонено.")
        await state.clear()
        return
    await state.update_data(description=desc)
    await message.answer("Введите цену (число или 0, если даром):")
    await state.set_state(CreateAdStates.price)

@router.message(CreateAdStates.price)
async def price_entered(message: Message, state: FSMContext):
    price_text = message.text.strip()
    if not is_valid_price(price_text):
        await message.answer("Введите корректную цену (число).")
        return
    await state.update_data(price=float(price_text))
    await message.answer("Укажите город: отправьте геопозицию или нажмите кнопку для ввода вручную.", reply_markup=location_keyboard())
    await state.set_state(CreateAdStates.location)

@router.message(CreateAdStates.location, F.location)
async def location_received(message: Message, state: FSMContext):
    lat, lon = message.location.latitude, message.location.longitude
    await state.update_data(latitude=lat, longitude=lon, city=None)
    data = await state.get_data()
    summary = (
        f"Проверьте объявление:\n\n"
        f"Название: {data['title']}\n"
        f"Описание: {data['description']}\n"
        f"Цена: {data['price']}\n"
        f"Местоположение: {lat}, {lon}\n"
        f"Фото: {len(data.get('photos', []))} шт."
    )
    await message.answer(summary, reply_markup=confirm_keyboard())
    await state.set_state(CreateAdStates.confirm)

@router.message(CreateAdStates.location, F.text.in_(["Ввести город вручную", "✍️ Ввести город вручную"]))
async def ask_city(message: Message, state: FSMContext):
    await message.answer("Введите название города:")
    await state.set_state(CreateAdStates.waiting_city)

@router.message(CreateAdStates.waiting_city)
async def city_entered(message: Message, state: FSMContext):
    city = message.text.strip()
    await state.update_data(city=city, latitude=None, longitude=None)
    data = await state.get_data()
    summary = (
        f"Проверьте объявление:\n\n"
        f"Название: {data['title']}\n"
        f"Описание: {data['description']}\n"
        f"Цена: {data['price']}\n"
        f"Город: {city}\n"
        f"Фото: {len(data.get('photos', []))} шт."
    )
    await message.answer(summary, reply_markup=confirm_keyboard())
    await state.set_state(CreateAdStates.confirm)

@router.callback_query(CreateAdStates.confirm, F.data == "publish")
async def publish_ad(call: CallbackQuery, state: FSMContext, bot):
    data = await state.get_data()
    async with async_session() as session:
        user = await session.execute(select(User).where(User.telegram_id == call.from_user.id))
        user = user.scalar_one()
        async with aiohttp.ClientSession() as http_session:
            photo_paths = []
            for file_id in data.get("photos", []):
                file = await bot.get_file(file_id)
                async with http_session.get(f"https://api.telegram.org/file/bot{bot.token}/{file.file_path}") as resp:
                    img_bytes = await resp.read()
                path = await upload_photo(img_bytes, "jpg")
                photo_paths.append(path)
        city = data.get("city")
        if not city:
            if data.get("latitude") and data.get("longitude"):
                city = f"{data['latitude']}, {data['longitude']}"
            else:
                city = "Не указан"
        ad = Ad(
            user_id=user.id,
            category_id=data["category_id"],
            title=data["title"],
            description=data["description"],
            price=data["price"],
            city=city,
            latitude=data.get("latitude"),
            longitude=data.get("longitude"),
            status="moderation"
        )
        session.add(ad)
        await session.flush()
        for i, path in enumerate(photo_paths, start=1):
            session.add(AdPhoto(ad_id=ad.id, file_path=path, order=i))
        await session.commit()
        admins = [int(x.strip()) for x in settings.ADMIN_IDS.strip("[]").split(",") if x.strip()]
        for admin_id in admins:
            try:
                await bot.send_message(admin_id, f"Новое объявление GLOWREP на модерации:\n{ad.title}")
            except:
                pass
    await call.message.answer("Объявление отправлено на модерацию! После проверки оно появится в поиске.")
    await state.clear()
    await call.message.delete()

@router.callback_query(CreateAdStates.confirm, F.data == "cancel_ad")
async def cancel_ad(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.answer("Публикация отменена.")
    await call.message.delete()