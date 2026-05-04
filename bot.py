import asyncio, logging, os
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.redis import RedisStorage
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web
from redis.asyncio import Redis
from config import settings
from database.engine import engine, async_session
from services.s3_client import ensure_bucket
from sqlalchemy import select
from database.models import Ad, AdPhoto, Category

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

async def on_startup(bot: Bot):
    # Создаём папку для фото
    os.makedirs('/app/photos', exist_ok=True)
    
    async with engine.begin() as conn:
        from database.models import Base
        await conn.run_sync(Base.metadata.create_all)
    await ensure_bucket()
    await bot.set_webhook(f"{settings.WEBHOOK_HOST}{settings.WEBHOOK_PATH}")
    logger.info("Webhook set")

async def on_shutdown(bot: Bot):
    await bot.delete_webhook()
    await engine.dispose()

# API-обработчик для Mini App
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
                "city": ad.city,
                "description": ad.description,
                "category_id": ad.category_id,
                "created_at": ad.created_at.isoformat(),
                "photo": f"/photos/{photo.file_path}" if photo else None
            })
        return web.json_response(products)

def main():
    redis = Redis(host=settings.REDIS_HOST, port=settings.REDIS_PORT, db=settings.REDIS_DB)
    storage = RedisStorage(redis=redis)
    dp = Dispatcher(storage=storage)
    
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
    
    # API для Mini App
    app.router.add_get('/api/products', api_products)
    
    # Статика для фото
    os.makedirs('/app/photos', exist_ok=True)
    app.router.add_static('/photos', '/app/photos')
    
    # ========== ОТДАЁМ MINI APP ПО КОРНЕВОМУ ПУТИ ==========
    async def serve_miniapp(request):
        # Путь к index.html
        html_path = os.path.join(os.path.dirname(__file__), 'mini-app', 'index.html')
        
        # Диагностика в логах
        logger.info(f"Looking for Mini App at: {html_path}")
        logger.info(f"File exists: {os.path.exists(html_path)}")
        logger.info(f"Current directory: {os.path.dirname(__file__)}")
        
        if os.path.exists(html_path):
            return web.FileResponse(html_path, headers={
                'Content-Type': 'text/html; charset=utf-8'
            })
        else:
            # Если файла нет, показываем простую заглушку
            html_content = """
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="UTF-8">
                <title>GLOWREP</title>
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <script src="https://telegram.org/js/telegram-web-app.js"></script>
            </head>
            <body>
                <h1>🔥 GLOWREP</h1>
                <p>Mini App загрузился, но index.html не найден.</p>
                <p>Создайте файл mini-app/index.html в репозитории.</p>
                <button onclick="window.Telegram.WebApp.close()">Закрыть</button>
                <script>
                    const tg = window.Telegram.WebApp;
                    tg.ready();
                    tg.expand();
                    tg.MainButton.setText('Тест').show();
                </script>
            </body>
            </html>
            """
            return web.Response(text=html_content, content_type='text/html')
    
    # Регистрируем обработчики корневых путей (ДО вебхука!)
    app.router.add_get('/', serve_miniapp)
    app.router.add_get('/index.html', serve_miniapp)
    # ====================================================
    
    # Настройка вебхука (должна быть ПОСЛЕ обработчиков)
    webhook_requests_handler = SimpleRequestHandler(dispatcher=dp, bot=bot)
    webhook_requests_handler.register(app, path=settings.WEBHOOK_PATH)
    setup_application(app, dp, bot=bot)
    
    port = int(os.getenv("PORT", 8080))
    logger.info(f"Starting server on 0.0.0.0:{port}")
    web.run_app(app, host="0.0.0.0", port=port)

if __name__ == "__main__":
    main()