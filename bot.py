import asyncio, logging, os, uuid
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.redis import RedisStorage
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web
from redis.asyncio import Redis
from config import settings
from database.engine import engine, async_session
from sqlalchemy import select, func
from database.models import Ad, AdPhoto, User, Favorite

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

async def on_startup(bot: Bot):
    os.makedirs('/app/photos', exist_ok=True)
    async with engine.begin() as conn:
        from database.models import Base
        await conn.run_sync(Base.metadata.create_all)
    
    # Создаём тестового пользователя если нет
    async with async_session() as session:
        from config import settings
        test_user = await session.execute(select(User).where(User.telegram_id == 1))
        if not test_user.scalar_one_or_none():
            test_user = User(telegram_id=1, first_name="Test User", username="test")
            session.add(test_user)
            await session.commit()
    
    await bot.set_webhook(f"{settings.WEBHOOK_HOST}{settings.WEBHOOK_PATH}")
    logger.info("Webhook set")

async def on_shutdown(bot: Bot):
    await bot.delete_webhook()
    await engine.dispose()

# ========== API ==========

async def api_products(request):
    async with async_session() as session:
        result = await session.execute(
            select(Ad).where(Ad.status == "active").order_by(Ad.created_at.desc()).limit(50)
        )
        ads = result.scalars().all()
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
                "created_at": ad.created_at.isoformat(),
                "photo": f"/photos/{photo.file_path}" if photo else None
            })
        return web.json_response(products)

async def api_create_product(request):
    try:
        data = await request.post()
        user_id = data.get('user_id')
        title = data.get('title')
        price = data.get('price')
        city = data.get('city', '')
        category_id = data.get('category_id', 1)
        description = data.get('description', '')
        
        if not title or not price or not description:
            return web.json_response({'success': False, 'error': 'Fill all required fields'}, status=400)
        
        async with async_session() as session:
            # Находим или создаём пользователя
            user_result = await session.execute(select(User).where(User.telegram_id == int(user_id)))
            user = user_result.scalar_one_or_none()
            if not user:
                user = User(telegram_id=int(user_id), first_name="User", username=f"user_{user_id}")
                session.add(user)
                await session.flush()
            
            # Создаём объявление
            ad = Ad(
                user_id=user.id,
                title=title,
                price=float(price),
                city=city,
                category_id=int(category_id),
                description=description,
                status="active"
            )
            session.add(ad)
            await session.flush()
            
            # Сохраняем фото
            photo_file = data.get('photo')
            if photo_file and hasattr(photo_file, 'file'):
                filename = f"{uuid.uuid4()}.jpg"
                os.makedirs('/app/photos', exist_ok=True)
                file_path = f"/app/photos/{filename}"
                content = await photo_file.read()
                with open(file_path, "wb") as f:
                    f.write(content)
                
                ad_photo = AdPhoto(ad_id=ad.id, file_path=filename, order=0)
                session.add(ad_photo)
            
            await session.commit()
        
        logger.info(f"Product created: {ad.id} by user {user_id}")
        return web.json_response({'success': True, 'ad_id': str(ad.id)})
    except Exception as e:
        logger.error(f"Error creating product: {e}")
        return web.json_response({'success': False, 'error': str(e)}, status=500)

async def api_toggle_favorite(request):
    try:
        data = await request.json()
        user_id = data.get('user_id')
        ad_id = data.get('ad_id')
        
        if not user_id or not ad_id:
            return web.json_response({'success': False, 'error': 'Missing data'}, status=400)
        
        async with async_session() as session:
            user_result = await session.execute(select(User).where(User.telegram_id == int(user_id)))
            user = user_result.scalar_one_or_none()
            if not user:
                user = User(telegram_id=int(user_id), first_name="User", username=f"user_{user_id}")
                session.add(user)
                await session.flush()
            
            fav_result = await session.execute(
                select(Favorite).where(Favorite.user_id == user.id, Favorite.ad_id == int(ad_id))
            )
            fav = fav_result.scalar_one_or_none()
            
            if fav:
                await session.delete(fav)
                action = 'removed'
            else:
                new_fav = Favorite(user_id=user.id, ad_id=int(ad_id))
                session.add(new_fav)
                action = 'added'
            
            await session.commit()
            return web.json_response({'success': True, 'action': action})
    except Exception as e:
        return web.json_response({'success': False, 'error': str(e)}, status=500)

async def api_profile(request):
    user_id = request.query.get('user_id')
    if not user_id:
        return web.json_response({}, status=200)
    
    async with async_session() as session:
        user_result = await session.execute(select(User).where(User.telegram_id == int(user_id)))
        user = user_result.scalar_one_or_none()
        
        if not user:
            return web.json_response({
                'first_name': 'User',
                'ads_count': 0,
                'favorites_count': 0
            })
        
        ads_count = await session.execute(select(func.count()).where(Ad.user_id == user.id))
        favorites_count = await session.execute(select(func.count()).where(Favorite.user_id == user.id))
        
        return web.json_response({
            'first_name': user.first_name or 'User',
            'username': user.username,
            'ads_count': ads_count.scalar() or 0,
            'favorites_count': favorites_count.scalar() or 0
        })

async def serve_miniapp(request):
    html_path = os.path.join(os.path.dirname(__file__), 'mini-app', 'index.html')
    if os.path.exists(html_path):
        return web.FileResponse(html_path, headers={'Content-Type': 'text/html; charset=utf-8'})
    else:
        html_content = """
        <!DOCTYPE html>
        <html><head><meta charset="UTF-8"><title>GLOWREP</title><script src="https://telegram.org/js/telegram-web-app.js"></script></head>
        <body><h1>GLOWREP</h1><script>const tg=window.Telegram.WebApp;tg.ready();tg.expand();</script></body></html>
        """
        return web.Response(text=html_content, content_type='text/html')

# ========== MAIN ==========

def main():
    redis = Redis(host=settings.REDIS_HOST, port=settings.REDIS_PORT, db=settings.REDIS_DB)
    storage = RedisStorage(redis=redis)
    dp = Dispatcher(storage=storage)
    
    # Подключаем роутеры
    from middlewares.logging_middleware import LoggingMiddleware
    from middlewares.ban_middleware import BanMiddleware
    dp.update.middleware(LoggingMiddleware())
    dp.update.middleware(BanMiddleware())
    
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
    
    app = web.Application()
    
    # API
    app.router.add_get('/api/products', api_products)
    app.router.add_post('/api/create-product', api_create_product)
    app.router.add_post('/api/toggle-favorite', api_toggle_favorite)
    app.router.add_get('/api/profile', api_profile)
    
    # Статика
    os.makedirs('/app/photos', exist_ok=True)
    app.router.add_static('/photos', '/app/photos')
    
    # Mini App
    app.router.add_get('/', serve_miniapp)
    app.router.add_get('/index.html', serve_miniapp)
    
    # Webhook
    webhook_requests_handler = SimpleRequestHandler(dispatcher=dp, bot=bot)
    webhook_requests_handler.register(app, path=settings.WEBHOOK_PATH)
    setup_application(app, dp, bot=bot)
    
    port = int(os.getenv("PORT", 8080))
    logger.info(f"Starting server on 0.0.0.0:{port}")
    web.run_app(app, host="0.0.0.0", port=port)

if __name__ == "__main__":
    main()