import asyncio, logging
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.redis import RedisStorage
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web
from redis.asyncio import Redis
from config import settings
from database.engine import engine
from services.s3_client import ensure_bucket

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

async def on_startup(bot: Bot):
    async with engine.begin() as conn:
        from database.models import Base
        await conn.run_sync(Base.metadata.create_all)
    await ensure_bucket()
    await bot.set_webhook(f"{settings.WEBHOOK_HOST}{settings.WEBHOOK_PATH}")
    logger.info("Webhook set")

async def on_shutdown(bot: Bot):
    await bot.delete_webhook()
    await engine.dispose()

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
    webhook_requests_handler = SimpleRequestHandler(dispatcher=dp, bot=bot)
    webhook_requests_handler.register(app, path=settings.WEBHOOK_PATH)
    setup_application(app, dp, bot=bot)
    web.run_app(app, host=settings.WEB_SERVER_HOST, port=settings.WEB_SERVER_PORT)

if __name__ == "__main__":
    main()
