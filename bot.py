import asyncio, logging, os, uuid, json, hashlib, hmac
from urllib.parse import unquote, parse_qs
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.redis import RedisStorage
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web
from redis.asyncio import Redis
from config import settings
from database.engine import engine, async_session
from sqlalchemy import select, func
from database.models import Ad, AdPhoto, User, Favorite, Base

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


# ========== HELPERS ==========

async def get_or_create_user(session, telegram_id: int, username: str | None = None) -> User:
    """Находит пользователя по telegram_id или создаёт нового."""
    result = await session.execute(select(User).where(User.telegram_id == telegram_id))
    user = result.scalar_one_or_none()
    if user:
        # Обновляем username если изменился
        if username and user.username != username:
            user.username = username
            await session.flush()
        return user
    user = User(telegram_id=telegram_id, username=username)
    session.add(user)
    await session.flush()
    logger.info(f"Created new user: telegram_id={telegram_id}")
    return user


def validate_init_data(init_data: str, bot_token: str) -> dict | None:
    """Валидирует Telegram initData. Возвращает данные пользователя или None."""
    try:
        if not init_data:
            return None
        parsed = dict(pair.split("=", 1) for pair in unquote(init_data).split("&") if "=" in pair)
        check_hash = parsed.pop("hash", None)
        if not check_hash:
            return None
        data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(parsed.items()))
        secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
        computed = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(computed, check_hash):
            logger.warning("initData hash mismatch")
            return None
        user_data = json.loads(parsed.get("user", "{}"))
        return user_data
    except Exception as e:
        logger.error(f"initData validation error: {e}")
        return None


async def get_user_from_request(request) -> dict | None:
    """Извлекает и валидирует пользователя из заголовка X-Telegram-Init-Data."""
    init_data = request.headers.get("X-Telegram-Init-Data", "")
    if not init_data:
        return None
    user_data = validate_init_data(init_data, settings.BOT_TOKEN)
    return user_data


# ========== STARTUP / SHUTDOWN ==========

async def on_startup(bot: Bot):
    os.makedirs("/app/photos", exist_ok=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Тестовый пользователь — только поля, которые есть в модели User
    async with async_session() as session:
        await get_or_create_user(session, telegram_id=1, username="test")
        await session.commit()
        logger.info("Test user ensured")

    await bot.set_webhook(f"{settings.WEBHOOK_HOST}{settings.WEBHOOK_PATH}")
    logger.info("Webhook set")


async def on_shutdown(bot: Bot):
    await bot.delete_webhook()
    await engine.dispose()


# ========== CORS middleware ==========

@web.middleware
async def cors_middleware(request, handler):
    if request.method == "OPTIONS":
        resp = web.Response()
    else:
        resp = await handler(request)
    resp.headers["Access-Control-Allow-Origin"] = "*"
    resp.headers["Access-Control-Allow-Headers"] = "Content-Type, X-Telegram-Init-Data"
    resp.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    return resp


# ========== API ==========

async def api_products(request):
    """GET /api/products — каталог товаров."""
    category_id = request.query.get("category_id")
    search_q = request.query.get("q", "").strip().lower()

    async with async_session() as session:
        query = select(Ad).where(Ad.status == "active").order_by(Ad.created_at.desc()).limit(50)
        if category_id and category_id.isdigit():
            query = query.where(Ad.category_id == int(category_id))

        result = await session.execute(query)
        ads = result.scalars().all()

        # Фильтрация по поиску
        if search_q:
            ads = [a for a in ads if search_q in (a.title or "").lower() or search_q in (a.description or "").lower()]

        products = []
        for ad in ads:
            photo = (await session.execute(
                select(AdPhoto).where(AdPhoto.ad_id == ad.id).order_by(AdPhoto.order).limit(1)
            )).scalar_one_or_none()

            products.append({
                "id": str(ad.id),
                "title": ad.title,
                "price": float(ad.price) if ad.price else 0,
                "city": ad.city or "",
                "description": ad.description or "",
                "category_id": ad.category_id,
                "size": getattr(ad, "size", None) or "",
                "condition": getattr(ad, "condition", None) or "",
                "created_at": ad.created_at.isoformat() if ad.created_at else "",
                "photo": f"/photos/{photo.file_path}" if photo else None,
                "user_id": str(ad.user_id),
            })
        return web.json_response(products)


async def api_product_detail(request):
    """GET /api/products/{id} — детали товара."""
    ad_id = request.match_info.get("id")
    async with async_session() as session:
        ad = (await session.execute(select(Ad).where(Ad.id == ad_id))).scalar_one_or_none()
        if not ad:
            return web.json_response({"error": "Not found"}, status=404)

        photos_result = await session.execute(
            select(AdPhoto).where(AdPhoto.ad_id == ad.id).order_by(AdPhoto.order)
        )
        photos = [f"/photos/{p.file_path}" for p in photos_result.scalars().all()]

        seller = (await session.execute(select(User).where(User.id == ad.user_id))).scalar_one_or_none()

        return web.json_response({
            "id": str(ad.id),
            "title": ad.title,
            "price": float(ad.price) if ad.price else 0,
            "city": ad.city or "",
            "description": ad.description or "",
            "category_id": ad.category_id,
            "size": getattr(ad, "size", None) or "",
            "condition": getattr(ad, "condition", None) or "",
            "created_at": ad.created_at.isoformat() if ad.created_at else "",
            "photos": photos,
            "seller": {
                "username": seller.username if seller else None,
                "telegram_id": seller.telegram_id if seller else None,
            },
        })


async def api_create_product(request):
    """POST /api/create-product — создание объявления."""
    try:
        data = await request.post()
        telegram_id = data.get("user_id")
        title = data.get("title", "").strip()
        price = data.get("price", "").strip()
        city = data.get("city", "").strip()
        category_id = data.get("category_id", "1")
        description = data.get("description", "").strip()
        condition = data.get("condition", "")
        size = data.get("size", "")

        if not title or not price or not description or not telegram_id:
            return web.json_response({"success": False, "error": "Заполните все обязательные поля"}, status=400)

        async with async_session() as session:
            user = await get_or_create_user(session, telegram_id=int(telegram_id))

            ad_kwargs = dict(
                user_id=user.id,
                title=title,
                price=float(price),
                city=city,
                category_id=int(category_id),
                description=description,
                status="active",
            )
            # Добавляем поля только если они существуют в модели Ad
            from sqlalchemy import inspect as sa_inspect
            ad_columns = {c.key for c in sa_inspect(Ad).mapper.column_attrs}
            if "condition" in ad_columns:
                ad_kwargs["condition"] = condition
            if "size" in ad_columns:
                ad_kwargs["size"] = size

            ad = Ad(**ad_kwargs)
            session.add(ad)
            await session.flush()

            # Сохраняем фото (до 3)
            os.makedirs("/app/photos", exist_ok=True)
            for i in range(3):
                key = f"photo_{i}" if i > 0 else "photo"
                photo_file = data.get(key)
                if photo_file and hasattr(photo_file, "file"):
                    filename = f"{uuid.uuid4()}.jpg"
                    content = photo_file.file.read()
                    with open(f"/app/photos/{filename}", "wb") as f:
                        f.write(content)
                    session.add(AdPhoto(ad_id=ad.id, file_path=filename, order=i))

            await session.commit()

        logger.info(f"Product created: {ad.id} by telegram_id={telegram_id}")
        return web.json_response({"success": True, "ad_id": str(ad.id)})
    except Exception as e:
        logger.error(f"Error creating product: {e}", exc_info=True)
        return web.json_response({"success": False, "error": str(e)}, status=500)


async def api_toggle_favorite(request):
    """POST /api/toggle-favorite — добавить/убрать из избранного."""
    try:
        data = await request.json()
        telegram_id = data.get("user_id")
        ad_id = data.get("ad_id")
        if not telegram_id or not ad_id:
            return web.json_response({"success": False, "error": "Missing data"}, status=400)

        async with async_session() as session:
            user = await get_or_create_user(session, telegram_id=int(telegram_id))

            fav = (await session.execute(
                select(Favorite).where(Favorite.user_id == user.id, Favorite.ad_id == ad_id)
            )).scalar_one_or_none()

            if fav:
                await session.delete(fav)
                action = "removed"
            else:
                session.add(Favorite(user_id=user.id, ad_id=ad_id))
                action = "added"

            await session.commit()
            return web.json_response({"success": True, "action": action})
    except Exception as e:
        logger.error(f"Error toggling favorite: {e}", exc_info=True)
        return web.json_response({"success": False, "error": str(e)}, status=500)


async def api_favorites(request):
    """GET /api/favorites?user_id=<tg_id> — список избранного."""
    telegram_id = request.query.get("user_id")
    if not telegram_id:
        return web.json_response([])

    async with async_session() as session:
        user = (await session.execute(
            select(User).where(User.telegram_id == int(telegram_id))
        )).scalar_one_or_none()
        if not user:
            return web.json_response([])

        favs = (await session.execute(
            select(Favorite.ad_id).where(Favorite.user_id == user.id)
        )).scalars().all()
        return web.json_response([str(f) for f in favs])


async def api_profile(request):
    """GET /api/profile?user_id=<tg_id> — профиль."""
    telegram_id = request.query.get("user_id")
    if not telegram_id:
        return web.json_response({"username": "Пользователь", "ads_count": 0, "favorites_count": 0})

    async with async_session() as session:
        user = (await session.execute(
            select(User).where(User.telegram_id == int(telegram_id))
        )).scalar_one_or_none()

        if not user:
            return web.json_response({"username": "Пользователь", "ads_count": 0, "favorites_count": 0})

        ads_count = (await session.execute(
            select(func.count()).select_from(Ad).where(Ad.user_id == user.id)
        )).scalar() or 0

        favorites_count = (await session.execute(
            select(func.count()).select_from(Favorite).where(Favorite.user_id == user.id)
        )).scalar() or 0

        return web.json_response({
            "username": user.username or "Пользователь",
            "telegram_id": user.telegram_id,
            "city": user.city or "",
            "ads_count": ads_count,
            "favorites_count": favorites_count,
            "created_at": user.created_at.isoformat() if user.created_at else "",
        })


async def api_my_ads(request):
    """GET /api/my-ads?user_id=<tg_id> — объявления пользователя."""
    telegram_id = request.query.get("user_id")
    if not telegram_id:
        return web.json_response([])

    async with async_session() as session:
        user = (await session.execute(
            select(User).where(User.telegram_id == int(telegram_id))
        )).scalar_one_or_none()
        if not user:
            return web.json_response([])

        ads = (await session.execute(
            select(Ad).where(Ad.user_id == user.id).order_by(Ad.created_at.desc())
        )).scalars().all()

        result = []
        for ad in ads:
            photo = (await session.execute(
                select(AdPhoto).where(AdPhoto.ad_id == ad.id).order_by(AdPhoto.order).limit(1)
            )).scalar_one_or_none()
            result.append({
                "id": str(ad.id),
                "title": ad.title,
                "price": float(ad.price) if ad.price else 0,
                "status": ad.status,
                "photo": f"/photos/{photo.file_path}" if photo else None,
            })
        return web.json_response(result)


async def serve_miniapp(request):
    html_path = os.path.join(os.path.dirname(__file__), "mini-app", "index.html")
    if os.path.exists(html_path):
        return web.FileResponse(html_path, headers={"Content-Type": "text/html; charset=utf-8"})
    return web.Response(text="<h1>GLOWREP</h1><p>Mini App not found</p>", content_type="text/html")


# ========== MAIN ==========

def main():
    redis = Redis(host=settings.REDIS_HOST, port=settings.REDIS_PORT, db=settings.REDIS_DB, password=settings.REDIS_PASSWORD)
    storage = RedisStorage(redis=redis)
    dp = Dispatcher(storage=storage)

    # Middlewares
    from middlewares.logging_middleware import LoggingMiddleware
    from middlewares.ban_middleware import BanMiddleware
    dp.update.middleware(LoggingMiddleware())
    dp.update.middleware(BanMiddleware())

    # Routers
    from handlers.users.start import router as start_router
    from handlers.users.profile import router as profile_router
    from handlers.ads.create import router as create_router
    from handlers.ads.search import router as search_router
    from handlers.ads.view import router as view_router
    from handlers.chats.comm import router as chat_router
    from handlers.favorites.fav import router as fav_router
    from handlers.admin.moderation import router as moderation_router
    from handlers.admin.panel import router as panel_router

    dp.include_router(start_router)
    dp.include_router(profile_router)
    dp.include_router(create_router)
    dp.include_router(search_router)
    dp.include_router(view_router)
    dp.include_router(chat_router)
    dp.include_router(fav_router)
    dp.include_router(moderation_router)
    dp.include_router(panel_router)

    bot = Bot(token=settings.BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
    dp["bot"] = bot
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    app = web.Application(middlewares=[cors_middleware])

    # API routes
    app.router.add_get("/api/products", api_products)
    app.router.add_get("/api/products/{id}", api_product_detail)
    app.router.add_post("/api/create-product", api_create_product)
    app.router.add_post("/api/toggle-favorite", api_toggle_favorite)
    app.router.add_get("/api/favorites", api_favorites)
    app.router.add_get("/api/profile", api_profile)
    app.router.add_get("/api/my-ads", api_my_ads)

    # Static
    os.makedirs("/app/photos", exist_ok=True)
    app.router.add_static("/photos", "/app/photos")

    # Mini App
    app.router.add_get("/", serve_miniapp)
    app.router.add_get("/index.html", serve_miniapp)

    # Webhook
    webhook_requests_handler = SimpleRequestHandler(dispatcher=dp, bot=bot)
    webhook_requests_handler.register(app, path=settings.WEBHOOK_PATH)
    setup_application(app, dp, bot=bot)

    port = int(os.getenv("PORT", 8080))
    logger.info(f"Starting GLOWREP on 0.0.0.0:{port}")
    web.run_app(app, host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
